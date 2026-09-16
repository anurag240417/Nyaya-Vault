from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    INVESTIGATING_OFFICER = "INVESTIGATING_OFFICER"
    PROSECUTOR = "PROSECUTOR"
    JUDGE = "JUDGE"
    CLERK = "CLERK"


class ClearanceLevel(StrEnum):
    PUBLIC = "PUBLIC"
    RESTRICTED = "RESTRICTED"
    CONFIDENTIAL = "CONFIDENTIAL"
    SECRET = "SECRET"


CLEARANCE_RANK: dict[ClearanceLevel, int] = {
    ClearanceLevel.PUBLIC: 1,
    ClearanceLevel.RESTRICTED: 2,
    ClearanceLevel.CONFIDENTIAL: 3,
    ClearanceLevel.SECRET: 4,
}


class CaseStatus(StrEnum):
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    SOLVED = "SOLVED"
    UNSOLVED = "UNSOLVED"
    CLOSED = "CLOSED"


class Department(StrEnum):
    """Which real-world department a user belongs to, or a document
    originates from. This is a separate axis from ClearanceLevel (need-to-know
    depth) and from case_assignments (case membership) - a user can be
    assigned to a case and hold sufficient clearance, yet still be unable to
    open a document tagged for a department they are not part of.

    GENERAL is the deliberate "visible to every department" tag - case-wide
    notes, admin-created records, and anything pre-dating this feature all
    default here so nothing existing silently becomes invisible.
    """

    POLICE = "POLICE"
    FORENSICS = "FORENSICS"
    PROSECUTION = "PROSECUTION"
    JUDICIARY = "JUDICIARY"
    GENERAL = "GENERAL"


class CurrentUser(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    email: str
    username: str
    role: UserRole
    clearance_level: ClearanceLevel
    # None means "unassigned" - deliberately not defaulted to GENERAL, so a
    # freshly signed-up user sees no department-restricted documents until an
    # admin explicitly assigns them one (mirrors role/clearance defaults).
    department: Department | None = None
    is_active: bool
    token: str
    auth_user: dict[str, Any]