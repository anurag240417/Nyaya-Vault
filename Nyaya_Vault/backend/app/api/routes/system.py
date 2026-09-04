from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_casevault_service
from app.core.models import CurrentUser
from app.security.auth import get_current_user
from app.services.casevault import CaseVaultService

router = APIRouter(tags=["search", "audit", "integrity"])


@router.get("/activity")
async def recent_activity(
    limit: int = Query(default=12, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> list[dict]:
    return await service.recent_activity(user, limit)


@router.get("/search")
async def search(
    q: str = Query(min_length=1, max_length=500),
    case_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> list[dict]:
    return await service.search(user, q, case_id, limit)


@router.get("/integrity/verify")
async def verify_integrity(
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> dict:
    return await service.verify_integrity(user)
