from __future__ import annotations

from typing import Any


class AppError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str = "APP_ERROR", details: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details


class SupabaseError(AppError):
    def __init__(self, message: str, *, status_code: int = 502, details: Any = None):
        super().__init__(message, status_code=status_code, code="SUPABASE_ERROR", details=details)


class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication required."):
        super().__init__(message, status_code=401, code="AUTHENTICATION_REQUIRED")


class AuthorizationError(AppError):
    def __init__(self, message: str = "Access denied."):
        super().__init__(message, status_code=403, code="ACCESS_DENIED")


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found."):
        super().__init__(message, status_code=404, code="NOT_FOUND")


class ConflictError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=409, code="CONFLICT")
