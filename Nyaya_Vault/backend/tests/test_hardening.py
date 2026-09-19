from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.conftest import auth
from tests.fake_gateway import FakeGateway


def _client(gateway: FakeGateway | None = None, **overrides):
    gateway = gateway or FakeGateway()
    gateway.add_user(email="a@example.com", username="admin", role="ADMIN", clearance="SECRET", token="admin-token")
    base = dict(supabase_url="http://fake.invalid", supabase_anon_key="anon", supabase_service_role_key="service")
    app = create_app(settings=Settings(_env_file=None, **{**base, **overrides}), gateway=gateway)
    return TestClient(app)


def test_security_headers_on_api_and_health():
    with _client() as c:
        for r in (c.get("/health"), c.get("/api/v1/auth/me", headers=auth("admin-token"))):
            assert r.headers["x-content-type-options"] == "nosniff"
            assert r.headers["x-frame-options"] == "DENY"
            assert r.headers["referrer-policy"] == "no-referrer"
            assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
        assert c.get("/api/v1/auth/me", headers=auth("admin-token")).headers["cache-control"] == "no-store"


def test_docs_page_is_not_locked_down_by_the_api_csp():
    with _client() as c:
        r = c.get("/docs")
        assert r.status_code == 200
        assert "content-security-policy" not in r.headers


def test_hsts_only_in_production_over_https():
    with _client(app_env="development") as c:
        assert "strict-transport-security" not in c.get("/health", headers={"x-forwarded-proto": "https"}).headers
    with _client(app_env="production") as c:
        assert "strict-transport-security" not in c.get("/health").headers  # plain http
        hsts = c.get("/health", headers={"x-forwarded-proto": "https"}).headers["strict-transport-security"]
        assert "max-age=31536000" in hsts


def test_docs_are_disabled_in_production_even_if_expose_docs_left_on():
    with _client(app_env="production", expose_docs=True) as c:
        assert c.get("/docs").status_code == 404
        assert c.get("/openapi.json").status_code == 404
    with _client(app_env="development", expose_docs=True) as c:
        assert c.get("/docs").status_code == 200


def test_headers_can_be_disabled():
    with _client(security_headers_enabled=False) as c:
        assert "x-frame-options" not in c.get("/health").headers


def test_general_rate_limit_returns_429_with_retry_after():
    with _client(rate_limit_per_minute=5) as c:
        statuses = [c.get("/api/v1/auth/me", headers=auth("admin-token")).status_code for _ in range(7)]
        assert statuses[:5] == [200] * 5
        assert statuses[5:] == [429, 429]
        blocked = c.get("/api/v1/auth/me", headers=auth("admin-token"))
        assert blocked.json()["code"] == "RATE_LIMITED"
        assert int(blocked.headers["retry-after"]) >= 1
        assert blocked.headers["x-content-type-options"] == "nosniff"  # headers still applied to 429s


def test_health_and_preflight_are_exempt():
    with _client(rate_limit_per_minute=2) as c:
        assert all(c.get("/health").status_code == 200 for _ in range(10))
        for _ in range(10):
            r = c.options(
                "/api/v1/auth/me",
                headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
            )
            assert r.status_code == 200


def test_429_still_carries_cors_headers_so_the_browser_sees_the_real_error():
    with _client(rate_limit_per_minute=1) as c:
        h = {**auth("admin-token"), "Origin": "http://localhost:5173"}
        c.get("/api/v1/auth/me", headers=h)
        r = c.get("/api/v1/auth/me", headers=h)
        assert r.status_code == 429
        assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_strict_bucket_is_separate_and_lower():
    with _client(rate_limit_per_minute=100, rate_limit_strict_per_minute=3) as c:
        h = auth("admin-token")
        codes = [c.post("/api/v1/signatures/verify", headers=h, json={
            "public_key_pem": "x", "canonical_payload": "x", "signature_b64": "x",
        }).status_code for _ in range(5)]
        assert codes == [200, 200, 200, 429, 429]
        assert c.get("/api/v1/auth/me", headers=h).status_code == 200  # general bucket untouched


def test_limits_are_per_client_ip_only_when_proxy_headers_trusted():
    with _client(rate_limit_per_minute=1, trust_proxy_headers=True) as c:
        h = auth("admin-token")
        assert c.get("/api/v1/auth/me", headers={**h, "x-forwarded-for": "9.9.9.9"}).status_code == 200
        assert c.get("/api/v1/auth/me", headers={**h, "x-forwarded-for": "8.8.8.8"}).status_code == 200
        assert c.get("/api/v1/auth/me", headers={**h, "x-forwarded-for": "8.8.8.8"}).status_code == 429

    # Untrusted: a spoofed header must not buy a fresh allowance.
    with _client(rate_limit_per_minute=1, trust_proxy_headers=False) as c:
        h = auth("admin-token")
        assert c.get("/api/v1/auth/me", headers={**h, "x-forwarded-for": "1.1.1.1"}).status_code == 200
        assert c.get("/api/v1/auth/me", headers={**h, "x-forwarded-for": "2.2.2.2"}).status_code == 429


def test_rate_limiting_can_be_disabled():
    with _client(rate_limit_enabled=False, rate_limit_per_minute=1) as c:
        assert all(c.get("/api/v1/auth/me", headers=auth("admin-token")).status_code == 200 for _ in range(5))
