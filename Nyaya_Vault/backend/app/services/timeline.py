from __future__ import annotations

from datetime import datetime
from typing import Any

from ortools.sat.python import cp_model

from app.core.config import Settings
from app.core.exceptions import AuthorizationError
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
            params={"case_id": f"eq.{case_id}", "person_name": f"eq.{person_name}", "select": "*"},
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