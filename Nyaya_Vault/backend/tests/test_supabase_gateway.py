from __future__ import annotations

import asyncio
import json

import httpx

from app.core.config import Settings
from app.integrations.supabase import SupabaseGateway


def _run(coro):
    return asyncio.run(coro)


def test_modern_supabase_keys_use_apikey_only_for_trusted_backend_calls() -> None:
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[])

    async def scenario() -> None:
        client = httpx.AsyncClient(
            base_url="https://example.supabase.co",
            transport=httpx.MockTransport(handler),
        )
        gateway = SupabaseGateway(
            Settings(
                supabase_url="https://example.supabase.co",
                supabase_publishable_key="sb_publishable_test",
                supabase_secret_key="sb_secret_test",
            ),
            client=client,
        )
        await gateway.service_table("GET", "profiles")
        await client.aclose()

    _run(scenario())
    request = seen[0]
    assert request.headers["apikey"] == "sb_secret_test"
    assert "authorization" not in request.headers


def test_legacy_service_role_jwt_still_uses_bearer_for_compatibility() -> None:
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[])

    async def scenario() -> None:
        client = httpx.AsyncClient(
            base_url="https://example.supabase.co",
            transport=httpx.MockTransport(handler),
        )
        gateway = SupabaseGateway(
            Settings(
                supabase_url="https://example.supabase.co",
                supabase_anon_key="legacy-anon",
                supabase_secret_key=None,
                supabase_service_role_key="legacy-service-role-jwt",
            ),
            client=client,
        )
        await gateway.service_table("GET", "profiles")
        await client.aclose()

    _run(scenario())
    request = seen[0]
    assert request.headers["apikey"] == "legacy-service-role-jwt"
    assert request.headers["authorization"] == "Bearer legacy-service-role-jwt"


def test_auth_validation_uses_publishable_key_plus_user_jwt() -> None:
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "user-1", "email": "user@example.com"})

    async def scenario() -> None:
        client = httpx.AsyncClient(
            base_url="https://example.supabase.co",
            transport=httpx.MockTransport(handler),
        )
        gateway = SupabaseGateway(
            Settings(
                supabase_url="https://example.supabase.co",
                supabase_publishable_key="sb_publishable_test",
                supabase_secret_key="sb_secret_test",
            ),
            client=client,
        )
        user = await gateway.auth_user("user-access-token")
        assert user["id"] == "user-1"
        await client.aclose()

    _run(scenario())
    request = seen[0]
    assert request.url.path == "/auth/v1/user"
    assert request.headers["apikey"] == "sb_publishable_test"
    assert request.headers["authorization"] == "Bearer user-access-token"


def test_storage_delete_uses_supported_prefixes_endpoint() -> None:
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"message": "Successfully deleted"})

    async def scenario() -> None:
        client = httpx.AsyncClient(
            base_url="https://example.supabase.co",
            transport=httpx.MockTransport(handler),
        )
        gateway = SupabaseGateway(
            Settings(
                supabase_url="https://example.supabase.co",
                supabase_publishable_key="sb_publishable_test",
                supabase_secret_key="sb_secret_test",
            ),
            client=client,
        )
        await gateway.delete_service("case-documents", "cases/c1/document.pdf")
        await client.aclose()

    _run(scenario())
    request = seen[0]
    assert request.method == "DELETE"
    assert request.url.path == "/storage/v1/object/case-documents"
    assert json.loads(request.content) == {"prefixes": ["cases/c1/document.pdf"]}