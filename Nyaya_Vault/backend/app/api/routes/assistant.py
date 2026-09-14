from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_assistant_service
from app.core.models import CurrentUser
from app.schemas.assistant import AskQuestion
from app.security.auth import get_current_user
from app.services.assistant import AssistantService

router = APIRouter(prefix="/cases/{case_id}/assistant", tags=["assistant"])


@router.post("/ask")
async def ask(
    case_id: str,
    payload: AskQuestion,
    user: CurrentUser = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> dict:
    return await service.ask(user, case_id, payload.question)


@router.post("/summary")
async def summary(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> dict:
    return await service.summarize(user, case_id)


@router.post("/legal-sections")
async def legal_sections(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> dict:
    return await service.suggest_legal_sections(user, case_id)


@router.get("/gaps")
async def gaps(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> list[dict]:
    return await service.check_gaps(user, case_id)