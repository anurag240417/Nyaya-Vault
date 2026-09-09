from __future__ import annotations

from dataclasses import asdict
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response

from app.api.deps import get_casevault_service, get_processor, get_timeline_service
from app.core.models import ClearanceLevel, CurrentUser
from app.schemas.documents import EntityReview, ProcessRequest, RedactionReview
from app.security.auth import get_current_user
from app.services.casevault import CaseVaultService
from app.services.processor import DocumentProcessor
from app.services.timeline import TimelineService

router = APIRouter(tags=["documents"])


@router.post("/cases/{case_id}/documents")
async def upload_document(
    case_id: str,
    title: str = Form(...),
    document_type: str | None = Form(default=None),
    clearance_level: ClearanceLevel = Form(default=ClearanceLevel.RESTRICTED),
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> dict:
    data = await file.read(service.settings.max_upload_bytes + 1)
    result = await service.upload_new_document(
        user,
        case_id=case_id,
        title=title,
        document_type=document_type,
        clearance_level=clearance_level,
        filename=file.filename or "evidence",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    return result


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> dict:
    return await service.get_document(user, document_id)


@router.get("/documents/{document_id}/versions")
async def list_versions(
    document_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> list[dict]:
    return await service.list_versions(user, document_id)


@router.get("/documents/{document_id}/versions/latest")
async def latest_version(
    document_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> dict:
    return await service.latest_version(user, document_id)


@router.post("/documents/{document_id}/versions")
async def upload_version(
    document_id: str,
    change_summary: str | None = Form(default=None),
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> dict:
    data = await file.read(service.settings.max_upload_bytes + 1)
    return await service.upload_version(
        user,
        document_id=document_id,
        filename=file.filename or "evidence",
        content_type=file.content_type or "application/octet-stream",
        data=data,
        change_summary=change_summary,
    )


@router.get("/documents/{document_id}/versions/{version_id}/download")
async def download_version(
    document_id: str,
    version_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> Response:
    data, version = await service.download_version(user, document_id, version_id)
    filename = str(version.get("storage_key") or "evidence").split("/")[-1]
    return Response(
        content=data,
        media_type=str(version["mime_type"]),
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/document-versions/{version_id}/entities")
async def list_entities(
    version_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> list[dict]:
    return await service.list_entities(user, version_id)


@router.post("/documents/{document_id}/entities/review")
async def review_entities(
    document_id: str,
    payload: EntityReview,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
    timeline_service: TimelineService = Depends(get_timeline_service),
) -> dict:
    result = await service.review_entities(user, document_id, payload.confirmed_ids, payload.rejected_ids)
    if result.get("confirmed_count"):
        # New confirmed facts may complete a PERSON+LOCATION+DATE triple
        # somewhere in the case - re-scan automatically so a candidate
        # timeline statement can appear without anyone having to remember
        # to click "Scan documents for candidates" themselves. This never
        # confirms anything on its own - it only ever produces more
        # SUGGESTED rows for a human to accept or dismiss.
        try:
            await timeline_service.generate_suggestions_from_documents(user, result["case_id"])
        except Exception:
            pass
    return result


@router.get("/document-versions/{version_id}/redactions")
async def list_redactions(
    version_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> list[dict]:
    return await service.list_redactions(user, version_id)


@router.post("/documents/{document_id}/redactions/review")
async def review_redactions(
    document_id: str,
    payload: RedactionReview,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> dict:
    return await service.review_redactions(user, document_id, payload.approved_ids, payload.rejected_ids)


@router.post("/documents/{document_id}/process")
async def process_document(
    document_id: str,
    payload: ProcessRequest,
    user: CurrentUser = Depends(get_current_user),
    processor: DocumentProcessor = Depends(get_processor),
) -> dict:
    summary = await processor.process(user=user, document_id=document_id, version_id=payload.version_id)
    return asdict(summary)


@router.post("/documents/{document_id}/redacted-export")
async def export_redacted(
    document_id: str,
    user: CurrentUser = Depends(get_current_user),
    processor: DocumentProcessor = Depends(get_processor),
) -> Response:
    data, filename = await processor.export_redacted(user=user, document_id=document_id)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )