from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_casevault_service
from app.core.models import CurrentUser
from app.security.auth import get_current_user
from app.services.casevault import CaseVaultService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def me(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "role": user.role.value,
        "clearance_level": user.clearance_level.value,
        "is_active": user.is_active,
        **({"created_at": user.model_extra.get("created_at")} if user.model_extra and user.model_extra.get("created_at") else {}),
    }


@router.post("/login-event")
async def record_login(
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> dict:
    return await service.record_login(user)
