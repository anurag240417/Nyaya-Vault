from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any

from app.core.config import Settings
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, SupabaseError
from app.core.models import CLEARANCE_RANK, ClearanceLevel, CurrentUser, Department, UserRole
from app.integrations.supabase import SupabaseGateway
from app.services.authorization import AuthorizationService
from app.services.certificate_builder import build_section63_certificate_pdf

_ALLOWED_MIME = {
    "application/pdf", "image/jpeg", "image/png", "image/tiff",
    "video/mp4", "video/quicktime", "video/webm",
}
_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]")

# Document types where a case should have exactly one PRIMARY document -
# a second upload of the same type is almost always meant to be an update
# to the existing one (a corrected FIR, a revised chargesheet), not a
# genuinely separate piece of evidence. Matched after stripping everything
# but letters and uppercasing, so "FIR", "F.I.R.", "First Information
# Report" and "Charge Sheet" / "Charge-Sheet" / "ChargeSheet" all resolve
# to the same canonical key regardless of how an officer happens to type it.
_SINGLETON_TYPE_ALIASES: dict[str, str] = {
    "FIR": "FIR",
    "FIRSTINFORMATIONREPORT": "FIR",
    "CHARGESHEET": "CHARGESHEET",
    "CHARGE SHEET".replace(" ", ""): "CHARGESHEET",
}


def _singleton_type_key(document_type: str | None) -> str | None:
    if not document_type:
        return None
    normalized = re.sub(r"[^A-Za-z]", "", document_type).upper()
    return _SINGLETON_TYPE_ALIASES.get(normalized)


class CaseVaultService:
    def __init__(self, gateway: SupabaseGateway, settings: Settings) -> None:
        self.gateway = gateway
        self.settings = settings
        self.authz = AuthorizationService(gateway)

    @staticmethod
    def _safe_name(name: str) -> str:
        return _SAFE_NAME.sub("_", name or "evidence")[-180:] or "evidence"

    async def _audit_denied(
        self,
        user: CurrentUser,
        *,
        case_id: str | None,
        document_id: str | None,
        operation: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        try:
            await self.gateway.append_audit_service(
                actor_user_id=user.id,
                case_id=case_id,
                document_id=document_id,
                action="ACCESS_DENIED",
                result="DENIED",
                reason=reason,
                metadata={"operation": operation, **(metadata or {})},
            )
        except Exception:
            # Authorization must not become dependent on audit availability.
            pass

    async def record_login(self, user: CurrentUser) -> dict[str, bool]:
        await self.gateway.append_audit_service(
            actor_user_id=user.id,
            case_id=None,
            document_id=None,
            action="LOGIN",
            metadata={},
        )
        return {"ok": True}

    # ---------- cases ----------
    async def list_cases(self, user: CurrentUser) -> list[dict[str, Any]]:
        case_ids = await self.authz.accessible_case_ids(user)
        if case_ids is not None and not case_ids:
            return []
        params: dict[str, Any] = {"select": "*", "order": "created_at.desc"}
        if case_ids is not None:
            params["id"] = f"in.({','.join(case_ids)})"
        return await self.gateway.service_table("GET", "cases", params=params) or []

    async def get_case(self, user: CurrentUser, case_id: str) -> dict[str, Any]:
        return await self.authz.require_case_access(user, case_id)

    async def create_case(self, user: CurrentUser, payload: dict[str, Any]) -> dict[str, Any]:
        await self.authz.require_role(user, UserRole.ADMIN, UserRole.INVESTIGATING_OFFICER)
        rows = await self.gateway.service_table(
            "POST",
            "cases",
            body={
                "case_number": payload["case_number"].strip(),
                "title": payload["title"].strip(),
                "description": (payload.get("description") or "").strip() or None,
                "created_by": user.id,
            },
            prefer="return=representation",
        )
        if not rows:
            raise SupabaseError("Case creation returned no record.")
        # cases_after_insert trigger handles creator assignment + CASE_CREATED audit.
        return rows[0]

    async def update_case(self, user: CurrentUser, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        await self.authz.require_case_editor(user, case_id)
        body = {key: value for key, value in payload.items() if value is not None}
        if "title" in body:
            body["title"] = body["title"].strip()
        if "description" in body:
            body["description"] = body["description"].strip() or None
        if not body:
            return await self.get_case(user, case_id)
        rows = await self.gateway.service_table(
            "PATCH",
            "cases",
            params={"id": f"eq.{case_id}"},
            body=body,
            prefer="return=representation",
        )
        if not rows:
            raise NotFoundError("Case not found.")
        await self.gateway.append_audit_service(
            actor_user_id=user.id,
            case_id=case_id,
            document_id=None,
            action="CASE_UPDATED",
            metadata={"fields": sorted(body.keys())},
        )
        return rows[0]

    # ---------- admin case management ----------
    async def admin_list_case_management(self, user: CurrentUser) -> list[dict[str, Any]]:
        await self.authz.require_role(user, UserRole.ADMIN)
        cases = await self.gateway.service_table(
            "GET", "cases", params={"select": "*", "order": "created_at.desc"}
        ) or []
        if not cases:
            return []

        assignments = await self.gateway.service_table(
            "GET", "case_assignments", params={"select": "*", "order": "assigned_at.asc"}
        ) or []
        profiles = await self.gateway.service_table(
            "GET",
            "profiles",
            params={
                "select": "id,username,email,role,clearance_level,is_active",
                "order": "username.asc",
            },
        ) or []
        by_id = {str(row["id"]): row for row in profiles}
        assignments_by_case: dict[str, list[dict[str, Any]]] = {}
        for assignment in assignments:
            assignments_by_case.setdefault(str(assignment["case_id"]), []).append(assignment)

        result: list[dict[str, Any]] = []
        for case in cases:
            case_id = str(case["id"])
            collaborators: list[dict[str, Any]] = []
            for assignment in assignments_by_case.get(case_id, []):
                profile = by_id.get(str(assignment["user_id"]), {})
                collaborators.append(
                    {
                        "user_id": assignment["user_id"],
                        "username": profile.get("username", "unknown"),
                        "email": profile.get("email"),
                        "role": profile.get("role"),
                        "clearance_level": profile.get("clearance_level"),
                        "is_active": profile.get("is_active", False),
                        "assigned_at": assignment.get("assigned_at"),
                        "assigned_by": assignment.get("assigned_by"),
                    }
                )
            primary_id = case.get("primary_investigator_id")
            primary = by_id.get(str(primary_id)) if primary_id else None
            result.append(
                {
                    **case,
                    "primary_investigator": (
                        {
                            "id": primary.get("id"),
                            "username": primary.get("username"),
                            "email": primary.get("email"),
                            "role": primary.get("role"),
                            "clearance_level": primary.get("clearance_level"),
                            "is_active": primary.get("is_active"),
                        }
                        if primary
                        else None
                    ),
                    "collaborators": collaborators,
                }
            )
        return result

    async def admin_create_case_with_assignments(
        self, user: CurrentUser, payload: dict[str, Any]
    ) -> dict[str, Any]:
        await self.authz.require_role(user, UserRole.ADMIN)
        result = await self.gateway.rpc_service(
            "backend_admin_create_case",
            {
                "p_actor_user_id": user.id,
                "p_case_number": payload["case_number"].strip(),
                "p_title": payload["title"].strip(),
                "p_description": (payload.get("description") or "").strip() or None,
                "p_primary_investigator_id": payload.get("primary_investigator_id"),
                "p_collaborator_ids": payload.get("collaborator_ids") or [],
            },
        )
        case_id = str((result or {}).get("case_id") or "")
        if not case_id:
            raise SupabaseError("Admin case creation returned no case id.")
        rows = await self.admin_list_case_management(user)
        for row in rows:
            if str(row["id"]) == case_id:
                return row
        raise NotFoundError("Created case could not be loaded.")

    async def admin_replace_case_assignments(
        self, user: CurrentUser, case_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        await self.authz.require_role(user, UserRole.ADMIN)
        await self.gateway.rpc_service(
            "backend_admin_replace_case_assignments",
            {
                "p_actor_user_id": user.id,
                "p_case_id": case_id,
                "p_primary_investigator_id": payload.get("primary_investigator_id"),
                "p_collaborator_ids": payload.get("collaborator_ids") or [],
            },
        )
        rows = await self.admin_list_case_management(user)
        for row in rows:
            if str(row["id"]) == case_id:
                return row
        raise NotFoundError("Case not found.")

    # ---------- collaborators/users ----------
    async def list_collaborators(self, user: CurrentUser, case_id: str) -> list[dict[str, Any]]:
        await self.authz.require_case_access(user, case_id)
        assignments = await self.gateway.service_table(
            "GET",
            "case_assignments",
            params={"case_id": f"eq.{case_id}", "select": "*", "order": "assigned_at.asc"},
        ) or []
        if not assignments:
            return []
        user_ids = {str(row["user_id"]) for row in assignments}
        assigner_ids = {str(row["assigned_by"]) for row in assignments}
        all_ids = sorted(user_ids | assigner_ids)
        profiles = await self.gateway.service_table(
            "GET",
            "profiles",
            params={"id": f"in.({','.join(all_ids)})", "select": "id,username,role,clearance_level,is_active"},
        ) or []
        by_id = {str(row["id"]): row for row in profiles}
        result: list[dict[str, Any]] = []
        for row in assignments:
            profile = by_id.get(str(row["user_id"]), {})
            assigner = by_id.get(str(row["assigned_by"]), {})
            result.append(
                {
                    "user_id": row["user_id"],
                    "username": profile.get("username", "unknown"),
                    "role": profile.get("role"),
                    "clearance_level": profile.get("clearance_level"),
                    "is_active": profile.get("is_active", False),
                    "assigned_by": row["assigned_by"],
                    "assigned_by_username": assigner.get("username", "unknown"),
                    "assigned_at": row["assigned_at"],
                }
            )
        return result

    async def list_collaborator_candidates(self, user: CurrentUser, case_id: str) -> list[dict[str, Any]]:
        await self.authz.require_manage_collaborators(user, case_id)
        return await self.gateway.service_table(
            "GET",
            "profiles",
            params={
                "is_active": "eq.true",
                "select": "id,username,role,clearance_level,is_active",
                "order": "username.asc",
            },
        ) or []

    async def add_collaborator(self, user: CurrentUser, case_id: str, target_user_id: str) -> dict[str, Any]:
        try:
            await self.authz.require_manage_collaborators(user, case_id)
        except AuthorizationError as exc:
            await self._audit_denied(
                user,
                case_id=case_id,
                document_id=None,
                operation="add_collaborator",
                reason=str(exc),
                metadata={"target_user_id": target_user_id},
            )
            raise
        target = await self.authz.get_profile(target_user_id)
        if not target.get("is_active"):
            raise AuthorizationError("Inactive users cannot be assigned to a case.")
        existing = await self.gateway.service_table(
            "GET",
            "case_assignments",
            params={
                "case_id": f"eq.{case_id}",
                "user_id": f"eq.{target_user_id}",
                "select": "id",
                "limit": "1",
            },
        )
        if existing:
            return {"ok": True, "already_assigned": True}
        await self.gateway.service_table(
            "POST",
            "case_assignments",
            body={"case_id": case_id, "user_id": target_user_id, "assigned_by": user.id},
            prefer="return=minimal",
        )
        await self.gateway.append_audit_service(
            actor_user_id=user.id,
            case_id=case_id,
            document_id=None,
            action="CASE_ASSIGNED",
            metadata={"assigned_user_id": target_user_id},
        )
        return {"ok": True}

    async def remove_collaborator(self, user: CurrentUser, case_id: str, target_user_id: str) -> dict[str, Any]:
        try:
            await self.authz.require_manage_collaborators(user, case_id)
        except AuthorizationError as exc:
            await self._audit_denied(
                user,
                case_id=case_id,
                document_id=None,
                operation="remove_collaborator",
                reason=str(exc),
                metadata={"target_user_id": target_user_id},
            )
            raise
        assignments = await self.gateway.service_table(
            "GET",
            "case_assignments",
            params={"case_id": f"eq.{case_id}", "select": "id,user_id"},
        ) or []
        if not any(str(row["user_id"]) == target_user_id for row in assignments):
            return {"ok": True, "not_assigned": True}
        if len(assignments) <= 1:
            raise ConflictError("The last collaborator cannot be removed from a case.")
        await self.gateway.service_table(
            "DELETE",
            "case_assignments",
            params={"case_id": f"eq.{case_id}", "user_id": f"eq.{target_user_id}"},
            prefer="return=minimal",
        )
        await self.gateway.append_audit_service(
            actor_user_id=user.id,
            case_id=case_id,
            document_id=None,
            action="CASE_UNASSIGNED",
            metadata={"unassigned_user_id": target_user_id},
        )
        return {"ok": True}

    async def list_profiles(self, user: CurrentUser) -> list[dict[str, Any]]:
        await self.authz.require_role(user, UserRole.ADMIN)
        return await self.gateway.service_table(
            "GET",
            "profiles",
            params={"select": "*", "order": "username.asc"},
        ) or []

    async def admin_update_profile(
        self,
        user: CurrentUser,
        target_user_id: str,
        *,
        role: str,
        clearance_level: str,
        is_active: bool,
        department: str | None = None,
    ) -> dict[str, Any]:
        await self.authz.require_role(user, UserRole.ADMIN)
        target = await self.authz.get_profile(target_user_id)
        if target.get("role") == "ADMIN" and target.get("is_active") and (role != "ADMIN" or not is_active):
            active_admins = await self.gateway.service_table(
                "GET",
                "profiles",
                params={"role": "eq.ADMIN", "is_active": "eq.true", "select": "id"},
            ) or []
            if len(active_admins) <= 1:
                raise ConflictError("The last active admin cannot be demoted or disabled.")
        rows = await self.gateway.service_table(
            "PATCH",
            "profiles",
            params={"id": f"eq.{target_user_id}"},
            body={
                "role": role,
                "clearance_level": clearance_level,
                "department": department,
                "is_active": is_active,
            },
            prefer="return=representation",
        )
        if not rows:
            raise NotFoundError("User not found.")
        await self.gateway.append_audit_service(
            actor_user_id=user.id,
            case_id=None,
            document_id=None,
            action="PROFILE_UPDATED",
            metadata={
                "target_user_id": target_user_id,
                "role": role,
                "clearance": clearance_level,
                "department": department,
                "active": is_active,
            },
        )
        return rows[0]

    # ---------- documents ----------
    def validate_file(self, *, content_type: str, data: bytes) -> None:
        size = len(data)
        if content_type not in _ALLOWED_MIME:
            raise SupabaseError(f"Unsupported file type: {content_type or 'unknown'}", status_code=422)
        if size <= 0:
            raise SupabaseError("Empty files cannot be uploaded.", status_code=422)
        if size > self.settings.max_upload_bytes:
            raise SupabaseError("File exceeds the 25 MB limit.", status_code=413)
        signatures = {
            "application/pdf": lambda b: b.startswith(b"%PDF-"),
            "image/png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
            "image/tiff": lambda b: b.startswith(b"II*\x00") or b.startswith(b"MM\x00*"),
            # MP4 and QuickTime (.mov) are both ISO base media containers -
            # the identifying "ftyp" box sits at byte offset 4, not 0.
            "video/mp4": lambda b: b[4:8] == b"ftyp",
            "video/quicktime": lambda b: b[4:8] == b"ftyp",
            "video/webm": lambda b: b.startswith(b"\x1a\x45\xdf\xa3"),
        }
        if not signatures[content_type](data[:16]):
            raise SupabaseError("File contents do not match the declared MIME type.", status_code=422)

    async def list_case_documents(self, user: CurrentUser, case_id: str) -> list[dict[str, Any]]:
        await self.authz.require_case_access(user, case_id)
        rows = await self.gateway.service_table(
            "GET",
            "documents",
            params={"case_id": f"eq.{case_id}", "select": "*", "order": "created_at.desc"},
        ) or []
        return self.authz.visible_documents(user, rows)

    async def get_document(self, user: CurrentUser, document_id: str, *, record_view: bool = True) -> dict[str, Any]:
        access = await self.authz.require_document_access(user, document_id)
        if record_view:
            await self.gateway.append_audit_service(
                actor_user_id=user.id,
                case_id=str(access.document["case_id"]),
                document_id=document_id,
                action="DOCUMENT_VIEWED",
                metadata={},
            )
        return access.document

    async def list_versions(self, user: CurrentUser, document_id: str) -> list[dict[str, Any]]:
        await self.authz.require_document_access(user, document_id)
        return await self.gateway.service_table(
            "GET",
            "document_versions",
            params={"document_id": f"eq.{document_id}", "select": "*", "order": "version_number.desc"},
        ) or []

    async def latest_version(self, user: CurrentUser, document_id: str) -> dict[str, Any]:
        access = await self.authz.require_document_access(user, document_id)
        rows = await self.gateway.service_table(
            "GET",
            "document_versions",
            params={
                "document_id": f"eq.{document_id}",
                "version_number": f"eq.{access.document['current_version_number']}",
                "select": "*",
                "limit": "1",
            },
        )
        if not rows:
            raise NotFoundError("Current document version not found.")
        return rows[0]

    async def upload_new_document(
        self,
        user: CurrentUser,
        *,
        case_id: str,
        title: str,
        document_type: str | None,
        clearance_level: ClearanceLevel,
        filename: str,
        content_type: str,
        data: bytes,
        department: Department = Department.GENERAL,
    ) -> dict[str, Any]:
        await self.authz.require_case_access(user, case_id)
        if CLEARANCE_RANK[user.clearance_level] < CLEARANCE_RANK[clearance_level]:
            raise AuthorizationError("You cannot create evidence above your own clearance level.")
        # Mirrors the clearance check above: an uploader may only tag a
        # document for their own department, or leave it GENERAL (visible to
        # everyone). This stops a CLERK in one department from quietly
        # locking evidence away from the department that actually owns it,
        # or claiming evidence on behalf of a department they are not in.
        # ADMIN is exempt, same as everywhere else department is checked.
        if user.role != UserRole.ADMIN and department != Department.GENERAL:
            if user.department is None or user.department != department:
                raise AuthorizationError(
                    "You can only tag evidence for your own department, or leave it General."
                )
        self.validate_file(content_type=content_type, data=data)

        singleton_key = _singleton_type_key(document_type)
        if singleton_key is not None:
            existing_rows = await self.gateway.service_table(
                "GET", "documents",
                params={"case_id": f"eq.{case_id}", "select": "id,title,document_type"},
            ) or []
            for row in existing_rows:
                if _singleton_type_key(row.get("document_type")) == singleton_key:
                    raise ConflictError(
                        f"This case already has a primary {singleton_key} "
                        f"(\"{row['title']}\"). Add this file as a new version of "
                        f"that document instead of creating a second one.",
                        details={
                            "reason": "SINGLETON_DOCUMENT_TYPE_EXISTS",
                            "singleton_type": singleton_key,
                            "existing_document_id": row["id"],
                            "existing_document_title": row["title"],
                        },
                    )

        document_id = str(uuid.uuid4())
        storage_key = f"{case_id}/{document_id}/uploads/{uuid.uuid4()}-{self._safe_name(filename)}"
        digest = hashlib.sha256(data).hexdigest()
        await self.gateway.upload_service(self.settings.storage_bucket, storage_key, data, content_type)
        try:
            result = await self.gateway.rpc_service(
                "backend_register_document_upload",
                {
                    "p_actor_user_id": user.id,
                    "p_document_id": document_id,
                    "p_case_id": case_id,
                    "p_title": title.strip(),
                    "p_document_type": (document_type or "").strip() or None,
                    "p_clearance": clearance_level.value,
                    "p_storage_key": storage_key,
                    "p_sha256": digest,
                    "p_size_bytes": len(data),
                    "p_mime_type": content_type,
                    "p_department": department.value,
                },
            )
        except Exception:
            await self.gateway.delete_service(self.settings.storage_bucket, storage_key)
            raise
        if not isinstance(result, dict) or result.get("ok") is not True:
            await self.gateway.delete_service(self.settings.storage_bucket, storage_key)
            raise SupabaseError(str((result or {}).get("error") or "Could not register uploaded evidence."), status_code=400)
        return {
            "documentId": document_id,
            "versionId": result["version_id"],
            "versionNumber": result.get("version_number", 1),
            "storageKey": storage_key,
            "sha256": digest,
        }

    async def upload_version(
        self,
        user: CurrentUser,
        *,
        document_id: str,
        filename: str,
        content_type: str,
        data: bytes,
        change_summary: str | None,
    ) -> dict[str, Any]:
        access = await self.authz.require_document_access(user, document_id)
        self.validate_file(content_type=content_type, data=data)
        storage_key = f"{access.document['case_id']}/{document_id}/uploads/{uuid.uuid4()}-{self._safe_name(filename)}"
        digest = hashlib.sha256(data).hexdigest()
        await self.gateway.upload_service(self.settings.storage_bucket, storage_key, data, content_type)
        try:
            result = await self.gateway.rpc_service(
                "backend_register_document_version",
                {
                    "p_actor_user_id": user.id,
                    "p_document_id": document_id,
                    "p_storage_key": storage_key,
                    "p_sha256": digest,
                    "p_size_bytes": len(data),
                    "p_mime_type": content_type,
                    "p_change_summary": (change_summary or "").strip() or None,
                },
            )
        except Exception:
            await self.gateway.delete_service(self.settings.storage_bucket, storage_key)
            raise
        if not isinstance(result, dict) or result.get("ok") is not True:
            await self.gateway.delete_service(self.settings.storage_bucket, storage_key)
            raise SupabaseError(str((result or {}).get("error") or "Could not register evidence version."), status_code=400)
        return {
            "ok": True,
            "versionId": result["version_id"],
            "versionNumber": result["version_number"],
            "storageKey": storage_key,
            "sha256": digest,
        }

    async def download_version(self, user: CurrentUser, document_id: str, version_id: str) -> tuple[bytes, dict[str, Any]]:
        access, version = await self.authz.require_version_access(user, version_id)
        if str(version["document_id"]) != document_id:
            raise NotFoundError("Version does not belong to this document.")
        data = await self.gateway.download_service(self.settings.storage_bucket, str(version["storage_key"]))
        if hashlib.sha256(data).hexdigest() != str(version["sha256"]).lower():
            raise ConflictError("Stored evidence hash does not match immutable version metadata.")
        await self.gateway.append_audit_service(
            actor_user_id=user.id,
            case_id=str(access.document["case_id"]),
            document_id=document_id,
            action="DOCUMENT_DOWNLOADED",
            metadata={"version_id": version_id, "version_number": version["version_number"]},
        )
        return data, version

    # ---------- extraction/review ----------
    async def list_entities(self, user: CurrentUser, version_id: str) -> list[dict[str, Any]]:
        await self.authz.require_version_access(user, version_id)
        return await self.gateway.service_table(
            "GET",
            "document_entities",
            params={"document_version_id": f"eq.{version_id}", "select": "*", "order": "created_at.asc"},
        ) or []

    async def review_entities(
        self,
        user: CurrentUser,
        document_id: str,
        confirmed_ids: list[str],
        rejected_ids: list[str],
    ) -> dict[str, Any]:
        access = await self.authz.require_document_access(user, document_id)
        latest = await self.latest_version(user, document_id)
        rows = await self.gateway.service_table(
            "GET",
            "document_entities",
            params={"document_version_id": f"eq.{latest['id']}", "select": "id"},
        ) or []
        valid = {str(row["id"]) for row in rows}
        unknown = (set(confirmed_ids) | set(rejected_ids)) - valid
        if unknown:
            raise SupabaseError("One or more entity IDs do not belong to the current document version.", status_code=422)
        if confirmed_ids:
            await self.gateway.service_table(
                "PATCH",
                "document_entities",
                params={"id": f"in.({','.join(confirmed_ids)})"},
                body={"confirmed": True},
                prefer="return=minimal",
            )
        if rejected_ids:
            await self.gateway.service_table(
                "PATCH",
                "document_entities",
                params={"id": f"in.({','.join(rejected_ids)})"},
                body={"confirmed": False},
                prefer="return=minimal",
            )
        await self.gateway.append_audit_service(
            actor_user_id=user.id,
            case_id=str(access.document["case_id"]),
            document_id=document_id,
            action="METADATA_CONFIRMED",
            metadata={"confirmed_count": len(confirmed_ids), "rejected_count": len(rejected_ids), "version_id": latest["id"]},
        )
        return {"ok": True, "case_id": str(access.document["case_id"]), "confirmed_count": len(confirmed_ids)}

    async def list_redactions(self, user: CurrentUser, version_id: str) -> list[dict[str, Any]]:
        await self.authz.require_version_access(user, version_id)
        return await self.gateway.service_table(
            "GET",
            "redaction_suggestions",
            params={"document_version_id": f"eq.{version_id}", "select": "*", "order": "created_at.asc"},
        ) or []

    async def review_redactions(
        self,
        user: CurrentUser,
        document_id: str,
        approved_ids: list[str],
        rejected_ids: list[str],
    ) -> dict[str, Any]:
        access = await self.authz.require_document_access(user, document_id)
        latest = await self.latest_version(user, document_id)
        rows = await self.gateway.service_table(
            "GET",
            "redaction_suggestions",
            params={"document_version_id": f"eq.{latest['id']}", "select": "id"},
        ) or []
        valid = {str(row["id"]) for row in rows}
        unknown = (set(approved_ids) | set(rejected_ids)) - valid
        if unknown:
            raise SupabaseError("One or more redaction IDs do not belong to the current document version.", status_code=422)
        if approved_ids:
            await self.gateway.service_table(
                "PATCH",
                "redaction_suggestions",
                params={"id": f"in.({','.join(approved_ids)})"},
                body={"approved": True},
                prefer="return=minimal",
            )
        if rejected_ids:
            await self.gateway.service_table(
                "PATCH",
                "redaction_suggestions",
                params={"id": f"in.({','.join(rejected_ids)})"},
                body={"approved": False},
                prefer="return=minimal",
            )
        await self.gateway.append_audit_service(
            actor_user_id=user.id,
            case_id=str(access.document["case_id"]),
            document_id=document_id,
            action="REDACTION_APPROVED",
            metadata={"approved_count": len(approved_ids), "rejected_count": len(rejected_ids), "version_id": latest["id"]},
        )
        return {"ok": True}

    # ---------- audit/search/integrity ----------
    async def case_audit(self, user: CurrentUser, case_id: str) -> list[dict[str, Any]]:
        await self.authz.require_case_access(user, case_id)
        rows = await self.gateway.service_table(
            "GET",
            "audit_logs",
            params={"case_id": f"eq.{case_id}", "select": "*", "order": "sequence.desc"},
        ) or []
        actor_ids = sorted({str(row["actor_user_id"]) for row in rows if row.get("actor_user_id")})
        profile_map: dict[str, str] = {}
        if actor_ids:
            profiles = await self.gateway.service_table(
                "GET",
                "profiles",
                params={"id": f"in.({','.join(actor_ids)})", "select": "id,username"},
            ) or []
            profile_map = {str(row["id"]): str(row["username"]) for row in profiles}
        return [{**row, "actor_username": profile_map.get(str(row.get("actor_user_id")), "system")} for row in rows]

    async def recent_activity(self, user: CurrentUser, limit: int) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        case_ids = await self.authz.accessible_case_ids(user)
        return await self.gateway.rpc_service(
            "backend_recent_activity",
            {
                "p_actor_user_id": user.id,
                "p_case_ids": case_ids,
                "p_limit": limit,
            },
        ) or []

    async def search(self, user: CurrentUser, query: str, case_id: str | None, limit: int = 50) -> list[dict[str, Any]]:
        q = query.strip()
        if not q:
            return []
        if case_id:
            await self.authz.require_case_access(user, case_id)
            allowed_case_ids: list[str] | None = [case_id]
        else:
            allowed_case_ids = await self.authz.accessible_case_ids(user)
        if allowed_case_ids is not None and not allowed_case_ids:
            return []
        result = await self.gateway.rpc_service(
            "backend_search_casevault",
            {
                "p_query": q,
                "p_case_ids": allowed_case_ids,
                "p_clearance": user.clearance_level.value,
                "p_limit": max(1, min(limit, 100)),
            },
        )
        await self.gateway.append_audit_service(
            actor_user_id=user.id,
            case_id=case_id,
            document_id=None,
            action="SEARCH_PERFORMED",
            metadata={"query_length": len(q), "case_scoped": case_id is not None},
        )
        return result or []

    async def verify_integrity(self, user: CurrentUser) -> dict[str, Any]:
        # No audit row contents are exposed, only verification summary.
        result = await self.gateway.rpc_service("backend_verify_audit_chain", {})
        if isinstance(result, list):
            return result[0] if result else {"valid": True, "total_entries": 0, "first_invalid_sequence": None, "detail": "Audit chain verified."}
        return result

    async def generate_section63_certificate(
        self, user: CurrentUser, document_id: str, version_id: str, expert: dict[str, Any]
    ) -> bytes:
        access, version = await self.authz.require_version_access(user, version_id)
        if str(version["document_id"]) != document_id:
            raise NotFoundError("Version does not belong to this document.")

        case_id = str(access.document["case_id"])
        case_rows = await self.gateway.service_table(
            "GET", "cases", params={"id": f"eq.{case_id}", "select": "case_number,title", "limit": "1"},
        )
        case = case_rows[0] if case_rows else {"case_number": "Unknown", "title": "Unknown"}

        audit_events = await self.case_audit(user, case_id)
        # Only show events for this specific document in the certificate,
        # not the whole case's audit trail.
        doc_events = [e for e in audit_events if str(e.get("document_id")) == document_id]

        pdf_bytes = build_section63_certificate_pdf(
            case_number=case["case_number"],
            case_title=case["title"],
            document_title=access.document["title"],
            document_type=access.document.get("document_type"),
            document_id=document_id,
            version_number=version["version_number"],
            sha256_hash=version["sha256"],
            file_size_bytes=version["size_bytes"],
            mime_type=version["mime_type"],
            created_at=str(version["created_at"]),
            device_operator_name=user.username,
            device_operator_designation=user.role.value if hasattr(user.role, "value") else str(user.role),
            expert_name=expert["expert_name"],
            expert_designation=expert["expert_designation"],
            expert_qualification=expert["expert_qualification"],
            place=expert["place"],
            audit_events=doc_events,
        )

        await self.gateway.append_audit_service(
            actor_user_id=user.id,
            case_id=case_id,
            document_id=document_id,
            action="CERTIFICATE_GENERATED",
            metadata={"version_id": version_id, "expert_name": expert["expert_name"]},
        )
        return pdf_bytes