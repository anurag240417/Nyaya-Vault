from __future__ import annotations

import hashlib
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid() -> str:
    return str(uuid.uuid4())


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else -1.0


class FakeGateway:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {
            "profiles": [], "cases": [], "case_assignments": [], "documents": [],
            "document_versions": [], "document_entities": [], "document_chunks": [],
            "document_embeddings": [], "redaction_suggestions": [], "audit_logs": [],
            "integrity_anchors": [], "document_processing_jobs": [],
            "case_timeline_statements": [], "case_location_travel_minutes": [], "case_timeline_conflicts": [],
        }
        self.storage: dict[str, bytes] = {}
        self.tokens: dict[str, str] = {}
        self.audit_sequence = 0

    def add_user(
        self, *, email: str, username: str, role: str, clearance: str,
        department: str | None = None, active: bool = True, token: str | None = None,
    ) -> dict[str, Any]:
        user_id = uid()
        row = {
            "id": user_id, "email": email, "username": username, "role": role,
            "clearance_level": clearance, "department": department, "is_active": active,
            "created_at": now_iso(), "updated_at": now_iso(),
        }
        self.tables["profiles"].append(row)
        self.tokens[token or username] = user_id
        return row

    async def close(self) -> None: pass

    async def auth_user(self, token: str) -> dict[str, Any]:
        user_id = self.tokens.get(token)
        if not user_id: raise RuntimeError("bad token")
        profile = next(r for r in self.tables["profiles"] if r["id"] == user_id)
        return {"id": user_id, "email": profile["email"]}

    @staticmethod
    def _matches(row: dict[str, Any], params: dict[str, Any] | None) -> bool:
        if not params: return True
        ignored = {"select", "order", "limit", "offset"}
        for key, expr in params.items():
            if key in ignored: continue
            if isinstance(expr, str) and expr.startswith("eq."):
                raw = expr[3:]
                want: Any = raw
                if raw == "true": want = True
                elif raw == "false": want = False
                elif raw == "null": want = None
                if str(row.get(key)) != str(want) and row.get(key) != want: return False
            elif isinstance(expr, str) and expr.startswith("in.(") and expr.endswith(")"):
                vals = {v for v in expr[4:-1].split(",") if v}
                if str(row.get(key)) not in vals: return False
            else:
                if str(row.get(key)) != str(expr): return False
        return True

    async def service_table(self, method: str, table: str, *, params=None, body=None, prefer=None):
        rows = self.tables[table]
        method = method.upper()
        if method == "GET":
            out = [deepcopy(r) for r in rows if self._matches(r, params)]
            order = (params or {}).get("order")
            if order:
                field, _, direction = order.partition(".")
                out.sort(key=lambda x: (x.get(field) is None, x.get(field)), reverse=direction == "desc")
            limit = (params or {}).get("limit")
            if limit: out = out[:int(limit)]
            select = (params or {}).get("select")
            if select and select != "*":
                fields = [f.strip() for f in select.split(",") if f.strip() and "(" not in f]
                out = [{k: r.get(k) for k in fields} for r in out]
            return out

        if method == "POST":
            payloads = body if isinstance(body, list) else [body]
            created = []
            for payload in payloads:
                r = deepcopy(payload or {})
                r.setdefault("id", uid())
                r.setdefault("created_at", now_iso())
                if table == "cases":
                    r.setdefault("updated_at", now_iso())
                    r.setdefault("primary_investigator_id", None)
                    r.setdefault("status", "UNDER_INVESTIGATION")
                if table == "case_assignments": r.setdefault("assigned_at", now_iso())
                if table == "documents": r.setdefault("current_version_number", 1)
                if table == "document_versions":
                    r.setdefault("processing_status", "UPLOADED"); r.setdefault("processing_error", None); r.setdefault("extracted_text", None); r.setdefault("ocr_used", None)
                if table == "document_entities": r.setdefault("confirmed", False)
                if table == "redaction_suggestions": r.setdefault("approved", False)
                rows.append(r); created.append(deepcopy(r))
                if table == "cases":
                    assignment = {"id": uid(), "case_id": r["id"], "user_id": r["created_by"], "assigned_by": r["created_by"], "assigned_at": now_iso()}
                    self.tables["case_assignments"].append(assignment)
                    await self.append_audit_service(actor_user_id=r["created_by"], case_id=r["id"], document_id=None, action="CASE_CREATED", metadata={"case_number": r["case_number"], "title": r["title"]})
            return created if prefer == "return=representation" else None

        if method == "PATCH":
            changed = []
            for r in rows:
                if self._matches(r, params):
                    r.update(deepcopy(body or {}))
                    if table in {"profiles", "cases"}: r["updated_at"] = now_iso()
                    changed.append(deepcopy(r))
            return changed if prefer == "return=representation" else None

        if method == "DELETE":
            keep, deleted = [], []
            for r in rows:
                (deleted if self._matches(r, params) else keep).append(r)
            self.tables[table] = keep
            return deepcopy(deleted) if prefer == "return=representation" else None
        raise NotImplementedError(method)

    async def upload_service(self, bucket: str, storage_key: str, data: bytes, mime_type: str, *, upsert: bool = False) -> None:
        if storage_key in self.storage and not upsert: raise RuntimeError("exists")
        self.storage[storage_key] = data

    async def download_service(self, bucket: str, storage_key: str) -> bytes:
        return self.storage[storage_key]

    async def delete_service(self, bucket: str, storage_key: str) -> None:
        self.storage.pop(storage_key, None)

    async def append_audit_service(self, *, actor_user_id, case_id, document_id, action, result="SUCCESS", reason=None, metadata=None):
        self.audit_sequence += 1
        prev = self.tables["audit_logs"][-1]["entry_hash"] if self.tables["audit_logs"] else "0" * 64
        entry = hashlib.sha256(f"{self.audit_sequence}|{actor_user_id}|{case_id}|{document_id}|{action}|{result}|{prev}".encode()).hexdigest()
        row = {
            "id": uid(), "sequence": self.audit_sequence, "actor_user_id": actor_user_id,
            "case_id": case_id, "document_id": document_id, "action": action, "result": result,
            "reason": reason, "metadata": metadata or {}, "prev_hash": prev, "entry_hash": entry,
            "timestamp": now_iso(),
        }
        self.tables["audit_logs"].append(row)
        return deepcopy(row)

    async def rpc_service(self, function: str, payload: dict[str, Any] | None = None):
        p = payload or {}
        if function == "append_audit_entry":
            return await self.append_audit_service(
                actor_user_id=p.get("p_actor_user_id"), case_id=p.get("p_case_id"), document_id=p.get("p_document_id"),
                action=p["p_action"], result=p.get("p_result", "SUCCESS"), reason=p.get("p_reason"), metadata=p.get("p_metadata") or {},
            )
        if function == "backend_admin_create_case":
            actor = next(r for r in self.tables["profiles"] if r["id"] == p["p_actor_user_id"])
            if actor["role"] != "ADMIN" or not actor["is_active"]:
                raise RuntimeError("Only an active admin may create and assign cases.")
            primary_id = p.get("p_primary_investigator_id")
            if primary_id:
                primary = next(r for r in self.tables["profiles"] if r["id"] == primary_id)
                if not primary["is_active"] or primary["role"] != "INVESTIGATING_OFFICER":
                    raise RuntimeError("Primary investigator must be an active INVESTIGATING_OFFICER.")
            collaborator_ids = list(dict.fromkeys(p.get("p_collaborator_ids") or []))
            for target_id in collaborator_ids:
                target = next(r for r in self.tables["profiles"] if r["id"] == target_id)
                if not target["is_active"]:
                    raise RuntimeError("Every collaborator must be an active user.")
            case = {
                "id": uid(), "case_number": p["p_case_number"], "title": p["p_title"],
                "description": p.get("p_description"), "created_by": actor["id"],
                "primary_investigator_id": primary_id, "status": "UNDER_INVESTIGATION",
                "created_at": now_iso(), "updated_at": now_iso(),
            }
            self.tables["cases"].append(case)
            ids = list(dict.fromkeys([actor["id"], primary_id, *collaborator_ids]))
            ids = [x for x in ids if x]
            for target_id in ids:
                self.tables["case_assignments"].append({"id": uid(), "case_id": case["id"], "user_id": target_id, "assigned_by": actor["id"], "assigned_at": now_iso()})
            await self.append_audit_service(actor_user_id=actor["id"], case_id=case["id"], document_id=None, action="CASE_CREATED", metadata={"case_number": case["case_number"], "title": case["title"]})
            for target_id in ids:
                if target_id != actor["id"]:
                    await self.append_audit_service(actor_user_id=actor["id"], case_id=case["id"], document_id=None, action="CASE_ASSIGNED", metadata={"assigned_user_id": target_id, "primary_investigator": target_id == primary_id, "source": "admin_case_management"})
            return {"ok": True, "case_id": case["id"]}
        if function == "backend_admin_replace_case_assignments":
            actor = next(r for r in self.tables["profiles"] if r["id"] == p["p_actor_user_id"])
            if actor["role"] != "ADMIN" or not actor["is_active"]:
                raise RuntimeError("Only an active admin may reassign cases.")
            case = next(r for r in self.tables["cases"] if r["id"] == p["p_case_id"])
            primary_id = p.get("p_primary_investigator_id")
            if primary_id:
                primary = next(r for r in self.tables["profiles"] if r["id"] == primary_id)
                if not primary["is_active"] or primary["role"] != "INVESTIGATING_OFFICER":
                    raise RuntimeError("Primary investigator must be an active INVESTIGATING_OFFICER.")
            collaborator_ids = list(dict.fromkeys(p.get("p_collaborator_ids") or []))
            for target_id in collaborator_ids:
                target = next(r for r in self.tables["profiles"] if r["id"] == target_id)
                if not target["is_active"]:
                    raise RuntimeError("Every collaborator must be an active user.")
            old_ids = {r["user_id"] for r in self.tables["case_assignments"] if r["case_id"] == case["id"]}
            new_ids = {case["created_by"], *collaborator_ids}
            if primary_id: new_ids.add(primary_id)
            for removed in sorted(old_ids - new_ids):
                await self.append_audit_service(actor_user_id=actor["id"], case_id=case["id"], document_id=None, action="CASE_UNASSIGNED", metadata={"unassigned_user_id": removed, "source": "admin_case_management"})
            self.tables["case_assignments"] = [r for r in self.tables["case_assignments"] if r["case_id"] != case["id"] or r["user_id"] in new_ids]
            existing = {r["user_id"] for r in self.tables["case_assignments"] if r["case_id"] == case["id"]}
            for added in sorted(new_ids - existing):
                self.tables["case_assignments"].append({"id": uid(), "case_id": case["id"], "user_id": added, "assigned_by": actor["id"], "assigned_at": now_iso()})
                await self.append_audit_service(actor_user_id=actor["id"], case_id=case["id"], document_id=None, action="CASE_ASSIGNED", metadata={"assigned_user_id": added, "primary_investigator": added == primary_id, "source": "admin_case_management"})
            if case.get("primary_investigator_id") != primary_id:
                old_primary = case.get("primary_investigator_id")
                case["primary_investigator_id"] = primary_id
                case["updated_at"] = now_iso()
                await self.append_audit_service(actor_user_id=actor["id"], case_id=case["id"], document_id=None, action="CASE_UPDATED", metadata={"field": "primary_investigator_id", "previous_user_id": old_primary, "new_user_id": primary_id, "source": "admin_case_management"})
            return {"ok": True, "case_id": case["id"]}
        if function == "backend_register_document_upload":
            doc = {
                "id": p["p_document_id"], "case_id": p["p_case_id"], "title": p["p_title"], "document_type": p.get("p_document_type"),
                "clearance_level": p["p_clearance"], "department": p.get("p_department") or "GENERAL",
                "current_version_number": 1, "created_by": p["p_actor_user_id"], "created_at": now_iso(),
            }
            version_id = uid()
            ver = {
                "id": version_id, "document_id": doc["id"], "version_number": 1, "storage_key": p["p_storage_key"], "sha256": p["p_sha256"],
                "size_bytes": p["p_size_bytes"], "mime_type": p["p_mime_type"], "change_summary": None, "processing_status": "UPLOADED",
                "processing_error": None, "extracted_text": None, "ocr_used": None, "created_by": p["p_actor_user_id"], "created_at": now_iso(),
            }
            self.tables["documents"].append(doc); self.tables["document_versions"].append(ver)
            await self.append_audit_service(actor_user_id=p["p_actor_user_id"], case_id=doc["case_id"], document_id=doc["id"], action="DOCUMENT_UPLOADED", metadata={"version": 1, "version_id": version_id})
            return {"ok": True, "document_id": doc["id"], "version_id": version_id, "version_number": 1}
        if function == "backend_register_document_version":
            doc = next(r for r in self.tables["documents"] if r["id"] == p["p_document_id"])
            nxt = int(doc["current_version_number"]) + 1; doc["current_version_number"] = nxt
            version_id = uid()
            ver = {
                "id": version_id, "document_id": doc["id"], "version_number": nxt, "storage_key": p["p_storage_key"], "sha256": p["p_sha256"],
                "size_bytes": p["p_size_bytes"], "mime_type": p["p_mime_type"], "change_summary": p.get("p_change_summary"), "processing_status": "UPLOADED",
                "processing_error": None, "extracted_text": None, "ocr_used": None, "created_by": p["p_actor_user_id"], "created_at": now_iso(),
            }
            self.tables["document_versions"].append(ver)
            await self.append_audit_service(actor_user_id=p["p_actor_user_id"], case_id=doc["case_id"], document_id=doc["id"], action="DOCUMENT_VERSION_CREATED", metadata={"version": nxt, "version_id": version_id})
            return {"ok": True, "version_id": version_id, "version_number": nxt}
        if function == "claim_document_processing": return True
        if function == "finish_document_processing": return True
        if function == "backend_recent_activity":
            allowed = p.get("p_case_ids"); actor = p.get("p_actor_user_id"); limit = int(p.get("p_limit", 12))
            profiles = {r["id"]: r["username"] for r in self.tables["profiles"]}
            cases = {r["id"]: r["case_number"] for r in self.tables["cases"]}
            rows = []
            for row in sorted(self.tables["audit_logs"], key=lambda r: r["sequence"], reverse=True):
                if allowed is not None and row.get("actor_user_id") != actor and row.get("case_id") not in allowed: continue
                rows.append({"sequence": row["sequence"], "case_id": row.get("case_id"), "case_number": cases.get(row.get("case_id")), "document_id": row.get("document_id"), "action": row["action"], "actor_username": profiles.get(row.get("actor_user_id"), "system"), "result": row["result"], "timestamp": row["timestamp"]})
                if len(rows) >= limit: break
            return rows
        if function == "backend_verify_audit_chain":
            return [{"valid": True, "total_entries": len(self.tables["audit_logs"]), "first_invalid_sequence": None, "detail": "Audit chain verified."}]
        if function == "backend_record_integrity_anchor":
            actor = next((r for r in self.tables["profiles"] if r["id"] == p["p_actor_user_id"]), None)
            if not actor or not actor["is_active"]:
                return {"ok": False, "error": "Actor profile is missing or inactive."}
            entry_hash = str(p["p_audit_entry_hash"]).lower()
            row = next((r for r in self.tables["audit_logs"] if r["sequence"] == p["p_audit_sequence"]), None)
            if not row:
                return {"ok": False, "error": "No audit entry exists at that sequence."}
            if row["entry_hash"] != entry_hash:
                return {"ok": False, "error": "Entry hash does not match the audit log at that sequence."}
            anchor_id = uid()
            anchor = {
                "id": anchor_id, "case_id": None, "audit_sequence": p["p_audit_sequence"], "audit_entry_hash": entry_hash,
                "anchor_provider": p["p_anchor_provider"], "anchor_reference": p["p_anchor_reference"],
                "chain_id": p.get("p_chain_id"), "tx_status": p.get("p_tx_status") or "PENDING",
                "explorer_url": p.get("p_explorer_url"), "anchored_at": now_iso(), "created_by": actor["id"],
            }
            self.tables["integrity_anchors"].append(anchor)
            failed = p.get("p_tx_status") == "FAILED"
            await self.append_audit_service(
                actor_user_id=actor["id"], case_id=None, document_id=None,
                action="AUDIT_CHAIN_ANCHOR_FAILED" if failed else "AUDIT_CHAIN_ANCHORED",
                result="FAILED" if failed else "SUCCESS",
                metadata={"anchor_id": anchor_id, "audit_sequence": p["p_audit_sequence"], "anchor_provider": p["p_anchor_provider"], "anchor_reference": p["p_anchor_reference"]},
            )
            return {"ok": True, "anchor_id": anchor_id}
        if function == "backend_search_casevault":
            q = str(p["p_query"]).lower(); allowed = p.get("p_case_ids"); clearance = p.get("p_clearance", "PUBLIC")
            ranks = {"PUBLIC": 1, "RESTRICTED": 2, "CONFIDENTIAL": 3, "SECRET": 4}
            out = []
            for doc in self.tables["documents"]:
                if allowed is not None and doc["case_id"] not in allowed: continue
                if ranks[doc["clearance_level"]] > ranks[clearance]: continue
                case = next(r for r in self.tables["cases"] if r["id"] == doc["case_id"])
                latest = next((v for v in self.tables["document_versions"] if v["document_id"] == doc["id"] and v["version_number"] == doc["current_version_number"]), None)
                chunks = [c for c in self.tables["document_chunks"] if latest and c["document_version_id"] == latest["id"]]
                matched = False
                for ch in chunks:
                    if q in ch["chunk_text"].lower():
                        out.append({"document_id": doc["id"], "case_id": doc["case_id"], "case_number": case["case_number"], "title": doc["title"], "page_number": ch.get("page_number"), "snippet": ch["chunk_text"][:320], "rank": 1.0}); matched = True; break
                if not matched and (q in doc["title"].lower() or q in case["case_number"].lower() or q in case["title"].lower()):
                    out.append({"document_id": doc["id"], "case_id": doc["case_id"], "case_number": case["case_number"], "title": doc["title"], "page_number": None, "snippet": "Document title or case metadata match", "rank": 0.2})
            return out[:int(p.get("p_limit", 50))]
        if function == "backend_list_chunk_embeddings":
            out = [
                {
                    "document_chunk_id": row["chunk"]["id"], "document_id": row["doc"]["id"],
                    "case_id": row["doc"]["case_id"], "case_number": row["case"]["case_number"],
                    "title": row["doc"]["title"], "page_number": row["chunk"].get("page_number"),
                    "chunk_text": row["chunk"]["chunk_text"], "embedding_json": row["embedding_row"]["embedding_json"],
                }
                for row in self._matching_chunk_rows(p.get("p_case_ids"), p.get("p_clearance", "PUBLIC"))
                if row["embedding_row"] is not None
            ]
            return out[:int(p.get("p_limit", 2000))]
        if function == "backend_semantic_search_casevault":
            import ast
            query_vector = [float(x) for x in ast.literal_eval(p["p_query_embedding"])]
            out = []
            for row in self._matching_chunk_rows(p.get("p_case_ids"), p.get("p_clearance", "PUBLIC")):
                emb = row["embedding_row"]
                if emb is None or emb.get("embedding") is None:
                    continue  # mirrors `where de.embedding is not null` - native column required
                out.append({
                    "document_id": row["doc"]["id"], "case_id": row["doc"]["case_id"],
                    "case_number": row["case"]["case_number"], "title": row["doc"]["title"],
                    "page_number": row["chunk"].get("page_number"), "snippet": row["chunk"]["chunk_text"][:320],
                    "similarity": _cosine(query_vector, emb["embedding_json"]),
                })
            out.sort(key=lambda r: r["similarity"], reverse=True)
            return out[:int(p.get("p_limit", 50))]
        raise NotImplementedError(function)

    def _matching_chunk_rows(self, allowed: list[str] | None, clearance: str):
        """Shared access-scoped join used by both semantic-search fakes -
        mirrors the real SQL functions' `latest` CTE + clearance filter."""
        ranks = {"PUBLIC": 1, "RESTRICTED": 2, "CONFIDENTIAL": 3, "SECRET": 4}
        for doc in self.tables["documents"]:
            if allowed is not None and doc["case_id"] not in allowed:
                continue
            if ranks[doc["clearance_level"]] > ranks[clearance]:
                continue
            case = next(r for r in self.tables["cases"] if r["id"] == doc["case_id"])
            latest = next(
                (v for v in self.tables["document_versions"]
                 if v["document_id"] == doc["id"] and v["version_number"] == doc["current_version_number"]),
                None,
            )
            chunks = [c for c in self.tables["document_chunks"] if latest and c["document_version_id"] == latest["id"]]
            for chunk in chunks:
                embedding_row = next(
                    (e for e in self.tables["document_embeddings"] if e["document_chunk_id"] == chunk["id"]), None,
                )
                yield {"doc": doc, "case": case, "chunk": chunk, "embedding_row": embedding_row}