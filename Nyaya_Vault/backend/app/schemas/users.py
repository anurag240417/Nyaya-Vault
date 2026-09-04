from __future__ import annotations

from pydantic import BaseModel

from app.core.models import ClearanceLevel, UserRole


class AdminProfileUpdate(BaseModel):
    role: UserRole
    clearance_level: ClearanceLevel
    is_active: bool
