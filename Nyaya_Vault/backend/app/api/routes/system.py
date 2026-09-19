from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_blockchain_anchor_service, get_casevault_service
from app.core.models import CurrentUser
from app.schemas.signing import SignatureVerifyRequest
from app.security.auth import get_current_user
from app.services.blockchain_anchor import BlockchainAnchorService
from app.services.casevault import CaseVaultService
from app.services.signing import verify_signature

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


@router.post("/signatures/verify")
async def verify_document_signature(
    body: SignatureVerifyRequest, user: CurrentUser = Depends(get_current_user),
) -> dict:
    # Pure cryptographic check - no database involved, and anyone can run
    # the same check offline from what's printed on the PDF itself.
    return {"valid": verify_signature(
        public_key_pem=body.public_key_pem, canonical_payload=body.canonical_payload,
        signature_b64=body.signature_b64,
    )}


@router.get("/integrity/anchors")
async def list_integrity_anchors(
    limit: int = Query(default=25, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    anchors: BlockchainAnchorService = Depends(get_blockchain_anchor_service),
) -> dict:
    return {
        "enabled": anchors.enabled,
        "schedule": anchors.schedule_info(),
        "anchors": await anchors.list_anchors(user, limit),
    }


@router.post("/integrity/anchors")
async def create_integrity_anchor(
    user: CurrentUser = Depends(get_current_user),
    anchors: BlockchainAnchorService = Depends(get_blockchain_anchor_service),
) -> dict:
    return await anchors.create_anchor(user)


@router.get("/integrity/anchors/{anchor_id}/verify")
async def verify_integrity_anchor(
    anchor_id: str,
    user: CurrentUser = Depends(get_current_user),
    anchors: BlockchainAnchorService = Depends(get_blockchain_anchor_service),
) -> dict:
    return await anchors.verify_anchor(user, anchor_id)
