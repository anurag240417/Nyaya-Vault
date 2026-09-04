from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.core.exceptions import SupabaseError


class SupabaseGateway:
    """Async Supabase REST/Auth/Storage gateway.

    Browser JWTs are used only to validate identity with Supabase Auth.
    Business table/storage access uses the service-role key *after* FastAPI
    authorization succeeds. The service-role key must never be exposed to React.
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            base_url=settings.normalized_supabase_url,
            timeout=httpx.Timeout(settings.request_timeout_seconds),
        )

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    def _headers(self, *, token: str | None = None, service: bool = False, extra: dict[str, str] | None = None) -> dict[str, str]:
        if service:
            key = self.settings.backend_api_key
            headers = {"apikey": key}
            # Modern sb_secret_* keys are API keys, not JWTs. Legacy
            # service_role JWTs still require the Bearer header.
            if not key.startswith("sb_secret_"):
                headers["Authorization"] = f"Bearer {key}"
        else:
            key = self.settings.browser_api_key
            headers = {"apikey": key}
            if token:
                headers["Authorization"] = f"Bearer {token}"
        if extra:
            headers.update(extra)
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        service: bool = False,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        expected: set[int] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        response = await self.client.request(
            method,
            path,
            params=params,
            json=json_body,
            content=content,
            headers=self._headers(token=token, service=service, extra=headers),
            timeout=timeout or self.settings.request_timeout_seconds,
        )
        accepted = expected or set(range(200, 300))
        if response.status_code not in accepted:
            try:
                details: Any = response.json()
            except Exception:
                details = response.text[:2000]
            message = "Supabase request failed."
            if isinstance(details, dict):
                message = str(details.get("msg") or details.get("message") or details.get("error_description") or details.get("error") or message)
            elif details:
                message = str(details)
            status = response.status_code if response.status_code in {400, 401, 403, 404, 409, 422, 429} else 502
            raise SupabaseError(message, status_code=status, details=details)
        return response

    @staticmethod
    def _json(response: httpx.Response) -> Any:
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    # Supabase Auth
    async def auth_user(self, token: str) -> dict[str, Any]:
        return self._json(await self._request("GET", "/auth/v1/user", token=token))

    # PostgREST - trusted backend only
    async def service_table(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, Any] | None = None,
        body: Any = None,
        prefer: str | None = None,
    ) -> Any:
        headers = {"Prefer": prefer} if prefer else None
        response = await self._request(
            method,
            f"/rest/v1/{table}",
            service=True,
            params=params,
            json_body=body,
            headers=headers,
        )
        return self._json(response)

    async def rpc_service(self, function: str, payload: dict[str, Any] | None = None) -> Any:
        response = await self._request("POST", f"/rest/v1/rpc/{function}", service=True, json_body=payload or {})
        return self._json(response)

    # Storage - trusted backend only
    @staticmethod
    def _storage_object_path(bucket: str, storage_key: str) -> str:
        return f"/storage/v1/object/{quote(bucket, safe='')}/{quote(storage_key, safe='/')}"

    async def upload_service(self, bucket: str, storage_key: str, data: bytes, mime_type: str, *, upsert: bool = False) -> None:
        await self._request(
            "POST",
            self._storage_object_path(bucket, storage_key),
            service=True,
            content=data,
            headers={"Content-Type": mime_type, "x-upsert": "true" if upsert else "false"},
            timeout=self.settings.processing_timeout_seconds,
        )

    async def download_service(self, bucket: str, storage_key: str) -> bytes:
        response = await self._request(
            "GET",
            self._storage_object_path(bucket, storage_key),
            service=True,
            timeout=self.settings.processing_timeout_seconds,
        )
        return response.content

    async def delete_service(self, bucket: str, storage_key: str) -> None:
        # Supabase Storage bulk-delete endpoint accepts object prefixes in JSON.
        # Use it even for one object so deletion works with both hosted and
        # self-hosted Storage API implementations.
        await self._request(
            "DELETE",
            f"/storage/v1/object/{quote(bucket, safe='')}",
            service=True,
            json_body={"prefixes": [storage_key]},
            expected={200, 204, 404},
        )

    async def append_audit_service(
        self,
        *,
        actor_user_id: str | None,
        case_id: str | None,
        document_id: str | None,
        action: str,
        result: str = "SUCCESS",
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        return await self.rpc_service(
            "append_audit_entry",
            {
                "p_actor_user_id": actor_user_id,
                "p_case_id": case_id,
                "p_document_id": document_id,
                "p_action": action,
                "p_result": result,
                "p_reason": reason,
                "p_metadata": metadata or {},
            },
        )
