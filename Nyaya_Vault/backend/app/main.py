from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import admin, assistant, auth, cases, certificate, documents, system, timeline, users
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.integrations.supabase import SupabaseGateway
from app.services.assistant import AssistantService
from app.services.casevault import CaseVaultService
from app.services.processor import DocumentProcessor
from app.services.timeline import TimelineService


def create_app(*, settings: Settings | None = None, gateway: SupabaseGateway | None = None) -> FastAPI:
    settings = settings or get_settings()
    supplied_gateway = gateway

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.supabase = supplied_gateway or SupabaseGateway(settings)
        app.state.casevault = CaseVaultService(app.state.supabase, settings)
        app.state.processor = DocumentProcessor(app.state.supabase, settings)
        app.state.timeline = TimelineService(app.state.supabase, settings)
        app.state.assistant = AssistantService(app.state.supabase, settings, app.state.casevault, app.state.timeline)
        yield
        if supplied_gateway is None:
            await app.state.supabase.close()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        docs_url="/docs" if settings.expose_docs else None,
        redoc_url="/redoc" if settings.expose_docs else None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code, **({"details": exc.details} if exc.details is not None else {})},
        )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    prefix = settings.api_prefix
    app.include_router(auth.router, prefix=prefix)
    app.include_router(admin.router, prefix=prefix)
    app.include_router(users.router, prefix=prefix)
    app.include_router(cases.router, prefix=prefix)
    app.include_router(documents.router, prefix=prefix)
    app.include_router(system.router, prefix=prefix)
    app.include_router(timeline.router, prefix=prefix)
    app.include_router(assistant.router, prefix=prefix)
    app.include_router(certificate.router, prefix=prefix)
    return app


app = create_app()