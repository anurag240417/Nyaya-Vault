from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_casevault_service
from app.core.models import CurrentUser
from app.schemas.users import AdminProfileUpdate
from app.security.auth import get_current_user
from app.services.casevault import CaseVaultService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
async def list_users(
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> list[dict]:
    return await service.list_profiles(user)


@router.patch("/{user_id}")
async def update_user(
    user_id: str,
    payload: AdminProfileUpdate,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> dict:
    return await service.admin_update_profile(
        user,
        user_id,
        role=payload.role.value,
        clearance_level=payload.clearance_level.value,
        department=payload.department.value if payload.department else None,
        is_active=payload.is_active,
    )