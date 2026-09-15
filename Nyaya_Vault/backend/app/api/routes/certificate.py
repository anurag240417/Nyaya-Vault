"""
Section 63 certificate route.

Drop this file at: backend/app/api/routes/certificate.py

Then, same registration steps as the assistant feature:
  1. app/api/routes/__init__.py -> add `certificate` to the import and __all__
  2. app/main.py -> `from app.api.routes import certificate` and
     `app.include_router(certificate.router, prefix=prefix)`
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.api.deps import get_casevault_service
from app.core.models import CurrentUser
from app.schemas.certificate import CertificateRequest
from app.security.auth import get_current_user
from app.services.casevault import CaseVaultService

router = APIRouter(prefix="/documents", tags=["certificate"])


@router.post("/{document_id}/versions/{version_id}/certificate")
async def generate_certificate(
    document_id: str,
    version_id: str,
    body: CertificateRequest,
    user: CurrentUser = Depends(get_current_user),
    service: CaseVaultService = Depends(get_casevault_service),
) -> Response:
    pdf_bytes = await service.generate_section63_certificate(
        user, document_id, version_id, body.model_dump()
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="section63-certificate-{document_id[:8]}.pdf"'
        },
    )