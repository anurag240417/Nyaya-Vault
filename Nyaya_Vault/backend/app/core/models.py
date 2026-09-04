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


class CurrentUser(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    email: str
    username: str
    role: UserRole
    clearance_level: ClearanceLevel
    is_active: bool
    token: str
    auth_user: dict[str, Any]
