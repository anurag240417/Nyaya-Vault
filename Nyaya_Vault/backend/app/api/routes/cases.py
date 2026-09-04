from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_casevault_service
from app.core.models import CurrentUser
from app.schemas.cases import CaseCreate, CaseUpdate, CollaboratorChange
from app.security.auth import get_current_user
from app.services.casevault import CaseVaultService

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("")
async def list_cases(
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> list[dict]:
    return await service.list_cases(user)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CaseCreate,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> dict:
    return await service.create_case(user, payload.model_dump())


@router.get("/{case_id}")
async def get_case(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> dict:
    return await service.get_case(user, case_id)


@router.patch("/{case_id}")
async def update_case(
    case_id: str,
    payload: CaseUpdate,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> dict:
    return await service.update_case(user, case_id, payload.model_dump(exclude_unset=True))


@router.get("/{case_id}/collaborator-candidates")
async def collaborator_candidates(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> list[dict]:
    return await service.list_collaborator_candidates(user, case_id)


@router.get("/{case_id}/collaborators")
async def collaborators(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> list[dict]:
    return await service.list_collaborators(user, case_id)


@router.post("/{case_id}/collaborators")
async def add_collaborator(
    case_id: str,
    payload: CollaboratorChange,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> dict:
    return await service.add_collaborator(user, case_id, payload.user_id)


@router.delete("/{case_id}/collaborators/{user_id}", status_code=status.HTTP_200_OK)
async def remove_collaborator(
    case_id: str,
    user_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> dict:
    return await service.remove_collaborator(user, case_id, user_id)


@router.get("/{case_id}/documents")
async def documents(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> list[dict]:
    return await service.list_case_documents(user, case_id)


@router.get("/{case_id}/audit")
async def case_audit(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> list[dict]:
    return await service.case_audit(user, case_id)
