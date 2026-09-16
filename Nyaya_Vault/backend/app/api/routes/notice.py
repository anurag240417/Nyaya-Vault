from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.api.deps import get_casevault_service
from app.core.models import CurrentUser
from app.schemas.notice import LegalNoticeRequest
from app.security.auth import get_current_user
from app.services.casevault import CaseVaultService
from app.services.notice_types import NOTICE_TYPES

router = APIRouter(prefix="/cases/{case_id}/notices", tags=["notices"])


@router.get("/types")
async def list_notice_types(case_id: str, user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    # No case-specific data here, but still requires auth like every other
    # endpoint - this just isn't itself a case-access check, the actual
    # generation call below is.
    return [
        {
            "key": spec.key,
            "title": spec.title,
            "statute_reference": spec.statute_reference,
            "fields": [
                {"key": f.key, "label": f.label, "required": f.required, "placeholder": f.placeholder}
                for f in spec.fields
            ],
        }
        for spec in NOTICE_TYPES.values()
    ]


@router.post("")
async def generate_notice(
    case_id: str,
    payload: LegalNoticeRequest,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> Response:
    pdf_bytes = await service.generate_legal_notice(user, case_id, payload.model_dump())
    filename = f"{payload.notice_type.lower()}-{case_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )