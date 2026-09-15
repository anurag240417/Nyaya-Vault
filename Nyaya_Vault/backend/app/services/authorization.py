from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.models import CLEARANCE_RANK, ClearanceLevel, CurrentUser, Department, UserRole
from app.integrations.supabase import SupabaseGateway


@dataclass(frozen=True)
class DocumentAccess:
    document: dict[str, Any]
    case: dict[str, Any]


class AuthorizationService:
    """Single source of CaseVault business authorization.

    Supabase RLS is intentionally not trusted for browser-facing business
    operations. The backend loads the authenticated profile, case assignments,
    and document clearance and decides access here before using service_role.
    """

    def __init__(self, gateway: SupabaseGateway) -> None:
        self.gateway = gateway

    async def _one(self, table: str, *, params: dict[str, Any], message: str) -> dict[str, Any]:
        rows = await self.gateway.service_table("GET", table, params=params)
        if not rows:
            raise NotFoundError(message)
        return rows[0]

    async def get_profile(self, user_id: str) -> dict[str, Any]:
        return await self._one(
            "profiles",
            params={"id": f"eq.{user_id}", "select": "*"},
            message="User not found.",
        )

    async def is_case_member(self, user_id: str, case_id: str) -> bool:
        rows = await self.gateway.service_table(
            "GET",
            "case_assignments",
            params={
                "case_id": f"eq.{case_id}",
                "user_id": f"eq.{user_id}",
                "select": "id",
                "limit": "1",
            },
        )
        return bool(rows)

    async def require_role(self, user: CurrentUser, *roles: UserRole) -> None:
        if user.role not in roles:
            raise AuthorizationError(f"Requires one of: {', '.join(role.value for role in roles)}.")

    async def require_case_access(self, user: CurrentUser, case_id: str) -> dict[str, Any]:
        case = await self._one(
            "cases",
            params={"id": f"eq.{case_id}", "select": "*"},
            message="Case not found.",
        )
        if user.role == UserRole.ADMIN:
            return case
        if str(case.get("primary_investigator_id") or "") == user.id:
            # cases.primary_investigator_id is the authoritative assignment
            # record; case_assignments is a derived join table populated by
            # the same RPCs. If they ever drift (partial migration run,
            # a hand-edited row, a failed mid-transaction insert), the
            # person on record as primary investigator must not be locked
            # out of their own case.
            return case
        if not await self.is_case_member(user.id, case_id):
            raise AuthorizationError("You are not assigned to this case.")
        return case

    async def require_case_editor(self, user: CurrentUser, case_id: str) -> dict[str, Any]:
        case = await self.require_case_access(user, case_id)
        if user.role == UserRole.ADMIN:
            return case
        if user.role == UserRole.INVESTIGATING_OFFICER and await self.is_case_member(user.id, case_id):
            return case
        raise AuthorizationError("Only an admin or assigned investigating officer may modify this case.")

    async def require_manage_collaborators(self, user: CurrentUser, case_id: str) -> dict[str, Any]:
        case = await self.require_case_access(user, case_id)
        if user.role == UserRole.ADMIN:
            return case
        if user.role == UserRole.INVESTIGATING_OFFICER and await self.is_case_member(user.id, case_id):
            return case
        raise AuthorizationError("Only an admin or assigned investigating officer may manage collaborators.")

    async def require_document_access(self, user: CurrentUser, document_id: str) -> DocumentAccess:
        document = await self._one(
            "documents",
            params={"id": f"eq.{document_id}", "select": "*"},
            message="Document not found.",
        )
        case = await self.require_case_access(user, str(document["case_id"]))
        required = ClearanceLevel(str(document["clearance_level"]))
        if CLEARANCE_RANK[user.clearance_level] < CLEARANCE_RANK[required]:
            raise AuthorizationError("Your evidence clearance is insufficient for this document.")
        self.check_department_access(user, document)
        return DocumentAccess(document=document, case=case)

    def check_department_access(self, user: CurrentUser, document: dict[str, Any]) -> None:
        """Department is a third, independent access axis on top of case
        membership and clearance level: a document tagged for a specific
        department is invisible to everyone outside that department, even an
        assigned collaborator with sufficient clearance. GENERAL-tagged
        documents (the default) are exempt, as is ADMIN - mirroring how ADMIN
        already bypasses case membership in require_case_access.
        """
        if user.role == UserRole.ADMIN:
            return
        doc_department = document.get("department")
        if not doc_department or doc_department == Department.GENERAL.value:
            return
        if user.department is None or user.department.value != doc_department:
            raise AuthorizationError(
                "This document belongs to another department. Ask an admin to grant you access."
            )

    def visible_documents(self, user: CurrentUser, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Clearance + department filter for list endpoints, where raising on
        the first denial would be wrong - a list should just omit what the
        caller cannot open, the same way clearance filtering already works.
        """
        user_rank = CLEARANCE_RANK[user.clearance_level]
        visible = []
        for row in documents:
            if user_rank < CLEARANCE_RANK[ClearanceLevel(str(row["clearance_level"]))]:
                continue
            try:
                self.check_department_access(user, row)
            except AuthorizationError:
                continue
            visible.append(row)
        return visible

    async def require_version_access(self, user: CurrentUser, version_id: str) -> tuple[DocumentAccess, dict[str, Any]]:
        version = await self._one(
            "document_versions",
            params={"id": f"eq.{version_id}", "select": "*"},
            message="Document version not found.",
        )
        access = await self.require_document_access(user, str(version["document_id"]))
        return access, version

    async def accessible_case_ids(self, user: CurrentUser) -> list[str] | None:
        """None means all cases (admin); otherwise concrete assigned IDs."""
        if user.role == UserRole.ADMIN:
            return None
        assignment_rows = await self.gateway.service_table(
            "GET",
            "case_assignments",
            params={"user_id": f"eq.{user.id}", "select": "case_id"},
        ) or []
        case_ids = {str(row["case_id"]) for row in assignment_rows}
        # Union in cases.primary_investigator_id so a drifted record (see
        # require_case_access) still shows up in list views, not just when
        # the case is opened by direct link.
        primary_rows = await self.gateway.service_table(
            "GET",
            "cases",
            params={"primary_investigator_id": f"eq.{user.id}", "select": "id"},
        ) or []
        case_ids.update(str(row["id"]) for row in primary_rows)
        return list(case_ids)