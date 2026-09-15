from __future__ import annotations

from pydantic import BaseModel

from app.core.models import ClearanceLevel, Department, UserRole


class AdminProfileUpdate(BaseModel):
    role: UserRole
    clearance_level: ClearanceLevel
    # None = unassigned. Only an admin can change this (see routes/users.py) -
    # there is deliberately no self-service department picker, for the same
    # reason there is no self-service role/clearance picker.
    department: Department | None = None
    is_active: bool