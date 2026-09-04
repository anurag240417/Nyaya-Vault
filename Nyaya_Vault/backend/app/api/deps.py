from __future__ import annotations

from fastapi import Request

from app.services.casevault import CaseVaultService
from app.services.processor import DocumentProcessor


def get_casevault_service(request: Request) -> CaseVaultService:
    return request.app.state.casevault


def get_processor(request: Request) -> DocumentProcessor:
    return request.app.state.processor
