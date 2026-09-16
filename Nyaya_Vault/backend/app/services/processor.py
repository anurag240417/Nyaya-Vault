from __future__ import annotations

import hashlib
import io
import os
import socket
import uuid
from dataclasses import dataclass
from typing import Any

import anyio
from PIL import Image

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, SupabaseError
from app.integrations.supabase import SupabaseGateway
from app.core.models import CurrentUser
from app.services.authorization import AuthorizationService
from app.services.chunking import chunk_text
from app.services.embeddings import EmbeddingUnavailable, embed_texts
from app.services.ner import extract_entities
from app.services.ocr import extract_text
from app.services.redaction import RedactionRegion, apply_redactions, suggest_redactions
from app.services.vision import VisionService


@dataclass(frozen=True)
class ProcessingSummary:
    document_id: str
    version_id: str
    status: str
    ocr_used: bool
    extracted_characters: int
    entities_created: int
    chunks_created: int
    embeddings_created: int
    redaction_suggestions_created: int


class DocumentProcessor:
    def __init__(self, gateway: SupabaseGateway, settings: Settings) -> None:
        self.gateway = gateway
        self.settings = settings
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:12]}"
        self.authz = AuthorizationService(gateway)
        self.vision = VisionService(settings)

    async def _one_service_row(self, table: str, *, params: dict[str, Any], not_found: str) -> dict[str, Any]:
        rows = await self.gateway.service_table("GET", table, params=params)
        if not rows:
            raise NotFoundError(not_found)
        return rows[0]

    async def _set_version_status(self, version_id: str, status: str, *, error: str | None = None, extra: dict[str, Any] | None = None) -> None:
        body: dict[str, Any] = {"processing_status": status, "processing_error": error}
        if extra:
            body.update(extra)
        await self.gateway.service_table(
            "PATCH",
            "document_versions",
            params={"id": f"eq.{version_id}"},
            body=body,
            prefer="return=minimal",
        )

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        message = str(exc).replace("\n", " ").strip()
        if not message:
            message = exc.__class__.__name__
        # Keep secrets/URLs out of browser-visible processing_error as much as possible.
        for marker in ("service_role", "apikey", "Authorization:", "Bearer "):
            if marker.lower() in message.lower():
                return "Document processing failed inside the trusted processor. Check server logs."
        return message[:500]

    async def process(self, *, user: CurrentUser, document_id: str, version_id: str) -> ProcessingSummary:
        await self.authz.require_document_access(user, document_id)
        actor_user_id = user.id

        document = await self._one_service_row(
            "documents",
            params={"id": f"eq.{document_id}", "select": "id,case_id,current_version_number,title"},
            not_found="Document not found.",
        )
        version = await self._one_service_row(
            "document_versions",
            params={"id": f"eq.{version_id}", "select": "*"},
            not_found="Document version not found.",
        )
        if str(version.get("document_id")) != document_id:
            raise NotFoundError("The requested version does not belong to this document.")

        claimed = await self.gateway.rpc_service(
            "claim_document_processing",
            {
                "p_version_id": version_id,
                "p_worker_id": self.worker_id,
                "p_lease_seconds": self.settings.processing_lease_seconds,
            },
        )
        if claimed is not True:
            raise ConflictError("This immutable version is already being processed by another worker.")

        try:
            await self._set_version_status(version_id, "EXTRACTING_TEXT", error=None)
            file_bytes = await self.gateway.download_service(self.settings.storage_bucket, version["storage_key"])
            actual_hash = hashlib.sha256(file_bytes).hexdigest()
            if actual_hash != str(version["sha256"]).lower():
                raise ValueError("Stored evidence hash does not match the immutable version record.")

            extraction = await anyio.to_thread.run_sync(extract_text, file_bytes, version["mime_type"])
            extracted_text = extraction.text or ""
            await self._set_version_status(
                version_id,
                "ANALYZING_ENTITIES",
                error=None,
                extra={"extracted_text": extracted_text, "ocr_used": bool(extraction.ocr_used)},
            )

            entities = await anyio.to_thread.run_sync(extract_entities, extracted_text)
            vision_entities: list[dict[str, Any]] = []
            if version["mime_type"].startswith("image/"):
                vision_entities = await anyio.to_thread.run_sync(self.vision.analyze_image, file_bytes)
            elif version["mime_type"].startswith("video/"):
                vision_entities = await anyio.to_thread.run_sync(self.vision.analyze_video, file_bytes)

            confirmed_rows = await self.gateway.service_table(
                "GET",
                "document_entities",
                params={"document_version_id": f"eq.{version_id}", "confirmed": "eq.true", "select": "id,entity_type,value,confidence"},
            ) or []
            confirmed_keys = {(str(row["entity_type"]), str(row["value"]).casefold()) for row in confirmed_rows}

            await self.gateway.service_table(
                "DELETE",
                "document_entities",
                params={"document_version_id": f"eq.{version_id}", "confirmed": "eq.false"},
                prefer="return=minimal",
            )
            entity_payload: list[dict[str, Any]] = []
            seen = set(confirmed_keys)
            for entity in entities:
                key = (entity.entity_type, entity.value.casefold())
                if key in seen:
                    continue
                seen.add(key)
                entity_payload.append(
                    {
                        "document_version_id": version_id,
                        "entity_type": entity.entity_type,
                        "value": entity.value[:2000],
                        "confidence": entity.confidence,
                        "confirmed": False,
                    }
                )
            # Vision detections don't dedupe against the same (type, value)
            # key as NER text entities - the same object detected in
            # multiple sampled frames is intentionally kept as separate
            # rows (each with its own frame_timestamp_seconds), since each
            # is a distinct sighting an investigator may want to review
            # independently, not a duplicate of the same extracted fact.
            for payload in vision_entities:
                entity_payload.append({**payload, "document_version_id": version_id})
            if entity_payload:
                await self.gateway.service_table("POST", "document_entities", body=entity_payload, prefer="return=minimal")

            await self._set_version_status(version_id, "GENERATING_SEARCH_INDEX", error=None)
            await self.gateway.service_table(
                "DELETE",
                "document_chunks",
                params={"document_version_id": f"eq.{version_id}"},
                prefer="return=minimal",
            )
            chunks = chunk_text(
                extracted_text,
                max_chars=self.settings.embedding_chunk_chars,
                overlap=self.settings.embedding_chunk_overlap,
            )
            chunk_rows: list[dict[str, Any]] = []
            if chunks:
                chunk_rows = await self.gateway.service_table(
                    "POST",
                    "document_chunks",
                    body=[
                        {
                            "document_version_id": version_id,
                            "chunk_index": chunk.index,
                            "page_number": chunk.page_number,
                            "chunk_text": chunk.text,
                        }
                        for chunk in chunks
                    ],
                    prefer="return=representation",
                ) or []

            embeddings_created = 0
            if self.settings.enable_semantic_embeddings and chunk_rows:
                try:
                    vectors = await anyio.to_thread.run_sync(
                        embed_texts,
                        [str(row["chunk_text"]) for row in chunk_rows],
                        self.settings.embedding_model,
                    )
                    embedding_rows = [
                        {
                            "document_chunk_id": row["id"],
                            "model_name": self.settings.embedding_model,
                            "embedding_json": vector,
                        }
                        for row, vector in zip(chunk_rows, vectors)
                    ]
                    if embedding_rows:
                        await self.gateway.service_table("POST", "document_embeddings", body=embedding_rows, prefer="return=minimal")
                        embeddings_created = len(embedding_rows)
                except EmbeddingUnavailable:
                    # Core processing must stay functional when optional ML packages are omitted.
                    embeddings_created = 0

            # Human-confirmed entities are the only source for redaction suggestions.
            await self.gateway.service_table(
                "DELETE",
                "redaction_suggestions",
                params={"document_version_id": f"eq.{version_id}", "approved": "eq.false"},
                prefer="return=minimal",
            )
            approved_rows = await self.gateway.service_table(
                "GET",
                "redaction_suggestions",
                params={"document_version_id": f"eq.{version_id}", "approved": "eq.true", "select": "entity_type,entity_value,region_json"},
            ) or []
            approved_keys = {
                (str(row.get("entity_type")), str(row.get("entity_value") or "").casefold(), str(row.get("region_json")))
                for row in approved_rows
            }

            redaction_payload: list[dict[str, Any]] = []
            if confirmed_rows:
                confirmed = [(str(row["entity_type"]), str(row["value"])) for row in confirmed_rows]
                regions = await anyio.to_thread.run_sync(suggest_redactions, file_bytes, version["mime_type"], confirmed)
                seen_regions: set[tuple[Any, ...]] = set()
                for region in regions:
                    region_json = {
                        "page_number": region.page_number,
                        "x0": region.x0,
                        "y0": region.y0,
                        "x1": region.x1,
                        "y1": region.y1,
                        "location_method": region.location_method,
                        "value": region.value,
                    }
                    region_key = (
                        region.entity_type,
                        region.value.casefold(),
                        region.page_number,
                        round(region.x0, 2), round(region.y0, 2), round(region.x1, 2), round(region.y1, 2),
                    )
                    if region_key in seen_regions:
                        continue
                    seen_regions.add(region_key)
                    if any(key[0] == region.entity_type and key[1] == region.value.casefold() for key in approved_keys):
                        continue
                    redaction_payload.append(
                        {
                            "document_version_id": version_id,
                            "entity_type": region.entity_type,
                            "entity_value": region.value,
                            "page_number": region.page_number + 1,
                            "region_json": region_json,
                            "confidence": 0.98 if region.location_method == "native" else 0.75,
                            "approved": False,
                        }
                    )
            if redaction_payload:
                await self.gateway.service_table("POST", "redaction_suggestions", body=redaction_payload, prefer="return=minimal")
                await self.gateway.append_audit_service(
                    actor_user_id=actor_user_id,
                    case_id=str(document["case_id"]),
                    document_id=document_id,
                    action="REDACTION_CREATED",
                    metadata={"version_id": version_id, "suggestion_count": len(redaction_payload)},
                )

            await self._set_version_status(version_id, "READY", error=None)
            await self.gateway.rpc_service(
                "finish_document_processing",
                {
                    "p_version_id": version_id,
                    "p_worker_id": self.worker_id,
                    "p_succeeded": True,
                    "p_error": None,
                },
            )
            return ProcessingSummary(
                document_id=document_id,
                version_id=version_id,
                status="READY",
                ocr_used=bool(extraction.ocr_used),
                extracted_characters=len(extracted_text),
                entities_created=len(entity_payload),
                chunks_created=len(chunk_rows),
                embeddings_created=embeddings_created,
                redaction_suggestions_created=len(redaction_payload),
            )
        except Exception as exc:
            safe_error = self._safe_error(exc)
            try:
                await self._set_version_status(version_id, "FAILED", error=safe_error)
                await self.gateway.rpc_service(
                    "finish_document_processing",
                    {
                        "p_version_id": version_id,
                        "p_worker_id": self.worker_id,
                        "p_succeeded": False,
                        "p_error": safe_error,
                    },
                )
            except Exception:
                pass
            raise

    async def export_redacted(self, *, user: CurrentUser, document_id: str) -> tuple[bytes, str]:
        await self.authz.require_document_access(user, document_id)
        actor_user_id = user.id
        document = await self._one_service_row(
            "documents",
            params={"id": f"eq.{document_id}", "select": "id,case_id,title,current_version_number"},
            not_found="Document not found.",
        )
        versions = await self.gateway.service_table(
            "GET",
            "document_versions",
            params={
                "document_id": f"eq.{document_id}",
                "version_number": f"eq.{document['current_version_number']}",
                "select": "*",
            },
        )
        if not versions:
            raise NotFoundError("Current document version not found.")
        version = versions[0]
        approved = await self.gateway.service_table(
            "GET",
            "redaction_suggestions",
            params={"document_version_id": f"eq.{version['id']}", "approved": "eq.true", "select": "*"},
        ) or []
        if not approved:
            raise SupabaseError("No human-approved redactions exist for the current version.", status_code=400)

        file_bytes = await self.gateway.download_service(self.settings.storage_bucket, version["storage_key"])
        if hashlib.sha256(file_bytes).hexdigest() != str(version["sha256"]).lower():
            raise ValueError("Stored evidence hash does not match the immutable version record.")

        regions: list[RedactionRegion] = []
        for row in approved:
            data = row.get("region_json") or {}
            if isinstance(data, str):
                import json
                data = json.loads(data)
            regions.append(
                RedactionRegion(
                    page_number=int(data.get("page_number", max(int(row.get("page_number") or 1) - 1, 0))),
                    x0=float(data["x0"]), y0=float(data["y0"]),
                    x1=float(data["x1"]), y1=float(data["y1"]),
                    entity_type=str(row["entity_type"]),
                    value=str(row.get("entity_value") or data.get("value") or ""),
                    location_method=str(data.get("location_method") or "stored"),
                )
            )

        redacted = await anyio.to_thread.run_sync(apply_redactions, file_bytes, version["mime_type"], regions)
        if version["mime_type"] != "application/pdf":
            image = Image.open(io.BytesIO(redacted)).convert("RGB")
            out = io.BytesIO()
            image.save(out, format="PDF")
            redacted = out.getvalue()

        await self.gateway.append_audit_service(
            actor_user_id=actor_user_id,
            case_id=str(document["case_id"]),
            document_id=document_id,
            action="REPORT_EXPORTED",
            metadata={
                "version_id": str(version["id"]),
                "approved_redaction_count": len(approved),
                "derivative_sha256": hashlib.sha256(redacted).hexdigest(),
            },
        )
        safe_title = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(document["title"]))[:120] or "document"
        return redacted, f"{safe_title}-redacted.pdf"