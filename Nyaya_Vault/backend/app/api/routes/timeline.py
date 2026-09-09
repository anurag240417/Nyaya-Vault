from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import get_timeline_service
from app.core.models import CurrentUser
from app.schemas.timeline import TimelineStatementCreate, TravelTimeSet
from app.security.auth import get_current_user
from app.services.timeline import TimelineService

router = APIRouter(prefix="/cases/{case_id}/timeline", tags=["timeline"])


@router.get("/statements")
async def list_statements(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: TimelineService = Depends(get_timeline_service),
) -> list[dict]:
    return await service.list_statements(user, case_id)


@router.post("/statements", status_code=status.HTTP_201_CREATED)
async def add_statement(
    case_id: str,
    payload: TimelineStatementCreate,
    user: CurrentUser = Depends(get_current_user),
    service: TimelineService = Depends(get_timeline_service),
) -> dict:
    return await service.add_statement(user, case_id, payload.model_dump())


@router.get("/conflicts")
async def list_conflicts(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: TimelineService = Depends(get_timeline_service),
) -> list[dict]:
    return await service.list_conflicts(user, case_id)


@router.post("/travel-times", status_code=status.HTTP_201_CREATED)
async def set_travel_minutes(
    case_id: str,
    payload: TravelTimeSet,
    user: CurrentUser = Depends(get_current_user),
    service: TimelineService = Depends(get_timeline_service),
) -> dict:
    return await service.set_travel_minutes(user, case_id, payload.model_dump())


@router.post("/suggestions/generate", status_code=status.HTTP_201_CREATED)
async def generate_suggestions(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: TimelineService = Depends(get_timeline_service),
) -> list[dict]:
    return await service.generate_suggestions_from_documents(user, case_id)


@router.post("/statements/{statement_id}/confirm")
async def confirm_suggestion(
    case_id: str,
    statement_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: TimelineService = Depends(get_timeline_service),
) -> dict:
    return await service.confirm_suggestion(user, case_id, statement_id)


@router.delete("/statements/{statement_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def reject_suggestion(
    case_id: str,
    statement_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: TimelineService = Depends(get_timeline_service),
) -> None:
    await service.reject_suggestion(user, case_id, statement_id)