from __future__ import annotations

import math
import re
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings

_WINDOW_SECONDS = 60.0
_EXEMPT_PATHS = {"/health"}
_DOC_PATHS = {"/docs", "/redoc", "/openapi.json"}

# Method + path patterns that are expensive (OCR/embeddings/LLM/PDF/chain
# transactions) or write-heavy enough to deserve a much lower ceiling than
# ordinary reads.
_STRICT = [
    ("POST", re.compile(r"^/api/v1/documents/[^/]+/process$")),
    ("POST", re.compile(r"^/api/v1/documents/[^/]+/versions/[^/]+/certificate$")),
    ("POST", re.compile(r"^/api/v1/cases/[^/]+/notices$")),
    ("POST", re.compile(r"^/api/v1/cases/[^/]+/assistant/.*$")),
    ("POST", re.compile(r"^/api/v1/cases/[^/]+/timeline/suggestions/generate$")),
    ("POST", re.compile(r"^/api/v1/integrity/anchors$")),
    ("POST", re.compile(r"^/api/v1/signatures/verify$")),
    ("GET", re.compile(r"^/api/v1/integrity/verify$")),
    ("GET", re.compile(r"^/api/v1/integrity/anchors/[^/]+/verify$")),
]


def _is_strict(method: str, path: str) -> bool:
    return any(method == m and pattern.match(path) for m, pattern in _STRICT)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._last_sweep = time.monotonic()

    def _client_ip(self, request: Request) -> str:
        if self.settings.trust_proxy_headers:
            forwarded = request.headers.get("x-forwarded-for", "")
            if forwarded:
                # The last hop is the one our own proxy appended; earlier
                # entries are whatever the client claimed.
                return forwarded.split(",")[-1].strip() or "unknown"
        return request.client.host if request.client else "unknown"

    def _sweep(self, now: float) -> None:
        if now - self._last_sweep < _WINDOW_SECONDS:
            return
        self._last_sweep = now
        for key in [k for k, q in self._hits.items() if not q or now - q[-1] > _WINDOW_SECONDS]:
            del self._hits[key]

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if not self.settings.rate_limit_enabled or path in _EXEMPT_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        strict = _is_strict(request.method, path)
        bucket = "strict" if strict else "general"
        limit = self.settings.rate_limit_strict_per_minute if strict else self.settings.rate_limit_per_minute

        now = time.monotonic()
        self._sweep(now)
        hits = self._hits[(self._client_ip(request), bucket)]
        while hits and now - hits[0] > _WINDOW_SECONDS:
            hits.popleft()

        if len(hits) >= limit:
            retry_after = max(1, math.ceil(_WINDOW_SECONDS - (now - hits[0])))
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Slow down and retry shortly.", "code": "RATE_LIMITED"},
                headers={"Retry-After": str(retry_after), "X-RateLimit-Limit": str(limit), "X-RateLimit-Remaining": "0"},
            )

        hits.append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - len(hits)))
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if not self.settings.security_headers_enabled:
            return response

        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        h.setdefault("Cross-Origin-Resource-Policy", "same-site")

        path = request.url.path
        if path not in _DOC_PATHS:
            # A JSON/PDF API has no reason to load or embed anything; the
            # Swagger/ReDoc pages do (CDN scripts), so they're exempt.
            h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        if path.startswith("/api/"):
            # Case data and evidence must not sit in shared/browser caches.
            h.setdefault("Cache-Control", "no-store")

        forwarded_https = request.headers.get("x-forwarded-proto", "").lower() == "https"
        if self.settings.is_production and (request.url.scheme == "https" or forwarded_https):
            h.setdefault("Strict-Transport-Security", f"max-age={self.settings.hsts_max_age_seconds}; includeSubDomains")
        return response
