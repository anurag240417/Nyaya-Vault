from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError, AuthorizationError, NotFoundError
from app.core.models import CurrentUser
from app.integrations.supabase import SupabaseGateway

bearer = HTTPBearer(auto_error=False)


def get_gateway(request: Request) -> SupabaseGateway:
    return request.app.state.supabase


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    gateway: SupabaseGateway = Depends(get_gateway),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise AuthenticationError()

    token = credentials.credentials
    try:
        auth_user = await gateway.auth_user(token)
    except Exception as exc:
        raise AuthenticationError("Invalid or expired Supabase access token.") from exc

    user_id = auth_user.get("id")
    if not user_id:
        raise AuthenticationError("Supabase token does not identify a user.")

    rows = await gateway.service_table(
        "GET",
        "profiles",
        params={"id": f"eq.{user_id}", "select": "id,email,username,role,clearance_level,department,is_active,created_at"},
    )
    if not rows:
        raise NotFoundError("User profile is missing. Run the Supabase migrations.")

    profile = rows[0]
    if not profile.get("is_active"):
        raise AuthorizationError("This account is inactive.")
    return CurrentUser(token=token, auth_user=auth_user, **profile)