from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import get_casevault_service
from app.core.models import CurrentUser
from app.schemas.admin import AdminCaseAssignmentsUpdate, AdminCaseCreate
from app.security.auth import get_current_user
from app.services.casevault import CaseVaultService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/cases")
async def list_admin_cases(
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> list[dict]:
    return await service.admin_list_case_management(user)


@router.post("/cases", status_code=status.HTTP_201_CREATED)
async def create_admin_case(
    payload: AdminCaseCreate,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> dict:
    return await service.admin_create_case_with_assignments(user, payload.model_dump())


@router.patch("/cases/{case_id}/assignments")
async def replace_admin_case_assignments(
    case_id: str,
    payload: AdminCaseAssignmentsUpdate,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> dict:
    return await service.admin_replace_case_assignments(user, case_id, payload.model_dump())
