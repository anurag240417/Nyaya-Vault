from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from ortools.sat.python import cp_model

from app.core.config import Settings
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.core.models import CurrentUser
from app.integrations.supabase import SupabaseGateway
from app.services.authorization import AuthorizationService

# Every pair of statements at different locations must leave at least this
# many minutes free even when no explicit travel time is on file for that
# location pair. Zero would still catch a plain double-booking (same
# person, two different places, fully overlapping windows) but a small
# default buffer avoids flagging back-to-back statements that are only
# adjacent by a minute due to rounding, which isn't a real contradiction.
_DEFAULT_TRAVEL_MINUTES = 0

# Suggestion generation caps - a page with an unusually large number of one
# entity type (e.g. a witness list) should not explode into a combinatorial
# number of suggested statements.
_MAX_ENTITIES_PER_TYPE_PER_PAGE = 3

_DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")


def _parse_date_entity(value: str) -> datetime | None:
    """Parses ner.py's DATE pattern (dd/mm/yyyy or dd-mm-yyyy, day-first per
    Indian convention, matching how this project's other date handling
    assumes dd/mm). Returns None rather than raising - a date we can't
    confidently parse should be skipped, not guessed at."""
    m = _DATE_RE.search(value)
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if year < 100:
        year += 2000
    try:
        return datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None


def _to_minutes(dt: datetime, epoch: datetime) -> int:
    return int((dt - epoch).total_seconds() // 60)


def _solve_person_timeline(
    statements: list[dict[str, Any]],
    travel_minutes: dict[tuple[str, str], int],
) -> bool:
    """Returns True if the statements are mutually consistent (no contradiction).

    Models each statement as an interval variable whose start can float
    anywhere within its reported window. For every pair of statements at
    different locations, exactly one must come first, and whichever does
    must finish early enough to reach the other location in time. If the
    solver can't find ANY such assignment, the statements are contradictory
    - this person could not have been where they were reported to be.
    """
    if len(statements) < 2:
        return True

    epoch = min(s["window_start"] for s in statements)
    model = cp_model.CpModel()
    starts: dict[str, Any] = {}
    ends: dict[str, Any] = {}
    intervals: dict[str, Any] = {}

    for s in statements:
        sid = s["id"]
        win_start = _to_minutes(s["window_start"], epoch)
        win_end = _to_minutes(s["window_end"], epoch)
        duration = min(s["duration_minutes"], max(win_end - win_start, 1))
        latest_start = max(win_start, win_end - duration)
        start_var = model.NewIntVar(win_start, latest_start, f"start_{sid}")
        end_var = model.NewIntVar(win_start + duration, win_end, f"end_{sid}")
        model.Add(end_var == start_var + duration)
        starts[sid] = start_var
        ends[sid] = end_var
        intervals[sid] = model.NewIntervalVar(start_var, duration, end_var, f"iv_{sid}")

    for i, a in enumerate(statements):
        for b in statements[i + 1:]:
            if a["location_name"] == b["location_name"]:
                continue  # same place - no travel constraint, overlap is fine
            t_ab = travel_minutes.get((a["location_name"], b["location_name"]), _DEFAULT_TRAVEL_MINUTES)
            t_ba = travel_minutes.get((b["location_name"], a["location_name"]), _DEFAULT_TRAVEL_MINUTES)
            a_before_b = model.NewBoolVar(f"{a['id']}_before_{b['id']}")
            model.Add(starts[b["id"]] >= ends[a["id"]] + t_ab).OnlyEnforceIf(a_before_b)
            model.Add(starts[a["id"]] >= ends[b["id"]] + t_ba).OnlyEnforceIf(a_before_b.Not())

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    status = solver.Solve(model)
    return status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


class TimelineService:
    def __init__(self, gateway: SupabaseGateway, settings: Settings) -> None:
        self.gateway = gateway
        self.settings = settings
        self.authz = AuthorizationService(gateway)

    async def add_statement(self, user: CurrentUser, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        await self.authz.require_case_access(user, case_id)
        row = {
            "case_id": case_id,
            "document_version_id": payload.get("document_version_id"),
            "person_name": payload["person_name"].strip(),
            "location_name": payload["location_name"].strip(),
            "window_start": payload["window_start"].isoformat(),
            "window_end": payload["window_end"].isoformat(),
            "duration_minutes": payload.get("duration_minutes", 30),
            "source_excerpt": (payload.get("source_excerpt") or "").strip() or None,
            "created_by": user.id,
            "status": "CONFIRMED",
        }
        created = await self.gateway.service_table(
            "POST", "case_timeline_statements", body=row, prefer="return=representation",
        )
        statement = created[0]
        conflict = await self._recheck_person(user, case_id, statement["person_name"])
        await self.gateway.append_audit_service(
            actor_user_id=user.id,
            case_id=case_id,
            document_id=payload.get("document_version_id"),
            action="TIMELINE_STATEMENT_ADDED",
            metadata={"person_name": statement["person_name"], "location_name": statement["location_name"]},
        )
        return {"statement": statement, "contradiction_detected": conflict is not None, "conflict": conflict}

    async def list_statements(self, user: CurrentUser, case_id: str) -> list[dict[str, Any]]:
        await self.authz.require_case_access(user, case_id)
        return await self.gateway.service_table(
            "GET", "case_timeline_statements",
            params={"case_id": f"eq.{case_id}", "select": "*", "order": "window_start.asc"},
        ) or []

    async def list_conflicts(self, user: CurrentUser, case_id: str) -> list[dict[str, Any]]:
        await self.authz.require_case_access(user, case_id)
        return await self.gateway.service_table(
            "GET", "case_timeline_conflicts",
            params={"case_id": f"eq.{case_id}", "select": "*", "order": "detected_at.desc"},
        ) or []

    async def generate_suggestions_from_documents(self, user: CurrentUser, case_id: str) -> list[dict[str, Any]]:
        """Proposes candidate timeline statements from entities already
        confirmed on this case's documents (never from unconfirmed/raw
        extractions - a human has already vetted these as accurate text).

        Heuristic: a PERSON, a LOCATION, and a DATE entity that all appear
        on the SAME PAGE of the SAME document version are proposed as one
        candidate statement. This is a co-occurrence heuristic, not real
        relation extraction - it does not know these three facts are
        actually about the same event, only that they're physically close
        together in the source text. That's exactly why the result lands
        as status=SUGGESTED, never CONFIRMED: a human must look at the
        source excerpt and confirm the pairing actually makes sense before
        it can ever contribute to a contradiction finding.

        Since only a DATE (not a time) is extracted, the window defaults to
        the entire day - maximally uncertain on purpose, rather than
        fabricating a specific time the source document never stated.
        """
        await self.authz.require_case_access(user, case_id)

        documents = await self.gateway.service_table(
            "GET", "documents",
            params={"case_id": f"eq.{case_id}", "select": "id,title,current_version_number"},
        ) or []
        if not documents:
            return []

        doc_ids = [d["id"] for d in documents]
        versions = await self.gateway.service_table(
            "GET", "document_versions",
            params={"document_id": f"in.({','.join(doc_ids)})", "select": "id,document_id,version_number"},
        ) or []
        current_version_by_doc = {d["id"]: d["current_version_number"] for d in documents}
        title_by_doc = {d["id"]: d["title"] for d in documents}
        version_id_to_doc_title: dict[str, str] = {}
        version_ids: list[str] = []
        for v in versions:
            if v["version_number"] == current_version_by_doc.get(v["document_id"]):
                version_ids.append(v["id"])
                version_id_to_doc_title[v["id"]] = title_by_doc.get(v["document_id"], "Untitled document")
        if not version_ids:
            return []

        entities = await self.gateway.service_table(
            "GET", "document_entities",
            params={
                "document_version_id": f"in.({','.join(version_ids)})",
                "confirmed": "eq.true", "select": "*",
            },
        ) or []

        groups: dict[tuple[str, int | None], dict[str, list[str]]] = {}
        for e in entities:
            if e["entity_type"] not in ("PERSON", "LOCATION", "DATE"):
                continue
            key = (e["document_version_id"], e.get("page_number"))
            groups.setdefault(key, {"PERSON": [], "LOCATION": [], "DATE": []})
            bucket = groups[key][e["entity_type"]]
            if e["value"] not in bucket and len(bucket) < _MAX_ENTITIES_PER_TYPE_PER_PAGE:
                bucket.append(e["value"])

        existing = await self.gateway.service_table(
            "GET", "case_timeline_statements",
            params={"case_id": f"eq.{case_id}", "select": "person_name,location_name,window_start,document_version_id"},
        ) or []
        already_seen = {
            (s["person_name"], s["location_name"], s["window_start"][:10], s["document_version_id"])
            for s in existing
        }

        created: list[dict[str, Any]] = []
        for (version_id, page_number), bucket in groups.items():
            for person in bucket["PERSON"]:
                for location in bucket["LOCATION"]:
                    for date_value in bucket["DATE"]:
                        parsed = _parse_date_entity(date_value)
                        if parsed is None:
                            continue
                        window_start = parsed
                        window_end = parsed.replace(hour=23, minute=59, second=0)
                        dedupe_key = (person, location, window_start.date().isoformat(), version_id)
                        if dedupe_key in already_seen:
                            continue
                        already_seen.add(dedupe_key)
                        doc_title = version_id_to_doc_title.get(version_id, "Untitled document")
                        page_note = f", page {page_number}" if page_number else ""
                        row = {
                            "case_id": case_id,
                            "document_version_id": version_id,
                            "person_name": person,
                            "location_name": location,
                            "window_start": window_start.isoformat(),
                            "window_end": window_end.isoformat(),
                            "duration_minutes": 60,
                            "source_excerpt": (
                                f"Auto-suggested: \"{person}\" + \"{location}\" + \"{date_value}\" "
                                f"found on the same page of \"{doc_title}\"{page_note}. Unverified pairing - "
                                f"confirm this reflects what the document actually says."
                            ),
                            "created_by": user.id,
                            "status": "SUGGESTED",
                            "page_number": page_number,
                        }
                        result = await self.gateway.service_table(
                            "POST", "case_timeline_statements", body=row, prefer="return=representation",
                        )
                        created.append(result[0])

        if created:
            await self.gateway.append_audit_service(
                actor_user_id=user.id, case_id=case_id, document_id=None,
                action="TIMELINE_SUGGESTIONS_GENERATED",
                metadata={"count": len(created)},
            )
        return created

    async def confirm_suggestion(self, user: CurrentUser, case_id: str, statement_id: str) -> dict[str, Any]:
        await self.authz.require_case_access(user, case_id)
        rows = await self.gateway.service_table(
            "GET", "case_timeline_statements",
            params={"id": f"eq.{statement_id}", "case_id": f"eq.{case_id}", "select": "*"},
        ) or []
        if not rows:
            raise NotFoundError("Timeline statement not found.")
        statement = rows[0]
        if statement["status"] != "SUGGESTED":
            raise ConflictError("Only a suggested statement can be confirmed.")

        updated = await self.gateway.service_table(
            "PATCH", "case_timeline_statements",
            params={"id": f"eq.{statement_id}"},
            body={"status": "CONFIRMED"},
            prefer="return=representation",
        )
        statement = updated[0]
        conflict = await self._recheck_person(user, case_id, statement["person_name"])
        await self.gateway.append_audit_service(
            actor_user_id=user.id, case_id=case_id, document_id=statement.get("document_version_id"),
            action="TIMELINE_SUGGESTION_CONFIRMED",
            metadata={"person_name": statement["person_name"], "location_name": statement["location_name"]},
        )
        return {"statement": statement, "contradiction_detected": conflict is not None, "conflict": conflict}

    async def reject_suggestion(self, user: CurrentUser, case_id: str, statement_id: str) -> None:
        await self.authz.require_case_access(user, case_id)
        rows = await self.gateway.service_table(
            "GET", "case_timeline_statements",
            params={"id": f"eq.{statement_id}", "case_id": f"eq.{case_id}", "select": "*"},
        ) or []
        if not rows:
            raise NotFoundError("Timeline statement not found.")
        if rows[0]["status"] != "SUGGESTED":
            raise ConflictError("Only a suggested statement can be rejected.")
        await self.gateway.service_table(
            "DELETE", "case_timeline_statements", params={"id": f"eq.{statement_id}"},
        )
        await self.gateway.append_audit_service(
            actor_user_id=user.id, case_id=case_id, document_id=rows[0].get("document_version_id"),
            action="TIMELINE_SUGGESTION_REJECTED",
            metadata={"person_name": rows[0]["person_name"], "location_name": rows[0]["location_name"]},
        )

    async def set_travel_minutes(self, user: CurrentUser, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        await self.authz.require_case_editor(user, case_id)
        location_a, location_b = payload["location_a"].strip(), payload["location_b"].strip()
        row = {
            "case_id": case_id, "location_a": location_a, "location_b": location_b,
            "minutes": payload["minutes"], "created_by": user.id,
        }
        await self.gateway.service_table(
            "POST", "case_location_travel_minutes", body=row, prefer="return=minimal",
        )
        # Recheck every person who has statements at either of these two
        # locations - a newly-added travel time can resolve an existing
        # false-positive contradiction just as easily as create a new one.
        statements = await self.gateway.service_table(
            "GET", "case_timeline_statements",
            params={"case_id": f"eq.{case_id}", "select": "person_name,location_name"},
        ) or []
        affected = {
            s["person_name"] for s in statements
            if s["location_name"] in (location_a, location_b)
        }
        for person_name in affected:
            await self._recheck_person(user, case_id, person_name)
        return {"ok": True}

    async def _recheck_person(self, user: CurrentUser, case_id: str, person_name: str) -> dict[str, Any] | None:
        rows = await self.gateway.service_table(
            "GET", "case_timeline_statements",
            params={
                "case_id": f"eq.{case_id}", "person_name": f"eq.{person_name}",
                "status": "eq.CONFIRMED", "select": "*",
            },
        ) or []
        statements = [
            {
                **s,
                "window_start": datetime.fromisoformat(s["window_start"]),
                "window_end": datetime.fromisoformat(s["window_end"]),
            }
            for s in rows
        ]

        travel_rows = await self.gateway.service_table(
            "GET", "case_location_travel_minutes",
            params={"case_id": f"eq.{case_id}", "select": "location_a,location_b,minutes"},
        ) or []
        travel_minutes = {(t["location_a"], t["location_b"]): t["minutes"] for t in travel_rows}

        consistent = _solve_person_timeline(statements, travel_minutes)

        existing_open = await self.gateway.service_table(
            "GET", "case_timeline_conflicts",
            params={
                "case_id": f"eq.{case_id}", "person_name": f"eq.{person_name}",
                "status": "eq.OPEN", "select": "*",
            },
        ) or []

        if consistent:
            return None

        if existing_open:
            return existing_open[0]

        conflict_row = {
            "case_id": case_id,
            "person_name": person_name,
            "statement_ids": [s["id"] for s in statements],
            "status": "OPEN",
        }
        created = await self.gateway.service_table(
            "POST", "case_timeline_conflicts", body=conflict_row, prefer="return=representation",
        )
        conflict = created[0]
        await self.gateway.append_audit_service(
            actor_user_id=user.id,
            case_id=case_id,
            document_id=None,
            action="TIMELINE_CONFLICT_DETECTED",
            metadata={"person_name": person_name, "statement_ids": conflict_row["statement_ids"]},
        )
        return conflict