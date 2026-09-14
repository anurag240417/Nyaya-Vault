from __future__ import annotations

from fastapi import Request

from app.services.assistant import AssistantService
from app.services.casevault import CaseVaultService
from app.services.processor import DocumentProcessor
from app.services.timeline import TimelineService


def get_casevault_service(request: Request) -> CaseVaultService:
    return request.app.state.casevault


def get_processor(request: Request) -> DocumentProcessor:
    return request.app.state.processor


def get_timeline_service(request: Request) -> TimelineService:
    return request.app.state.timeline


def get_assistant_service(request: Request) -> AssistantService:
    return request.app.state.assistant