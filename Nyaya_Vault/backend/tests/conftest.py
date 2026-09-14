from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.fake_gateway import FakeGateway


@pytest.fixture
def gateway() -> FakeGateway:
    g = FakeGateway()
    g.add_user(email="admin@example.com", username="admin", role="ADMIN", clearance="SECRET", token="admin-token")
    g.add_user(email="io@example.com", username="io", role="INVESTIGATING_OFFICER", clearance="SECRET", token="io-token")
    g.add_user(email="otherio@example.com", username="otherio", role="INVESTIGATING_OFFICER", clearance="SECRET", token="otherio-token")
    g.add_user(email="clerk@example.com", username="clerk", role="CLERK", clearance="PUBLIC", token="clerk-token")
    g.add_user(email="lowadmin@example.com", username="lowadmin", role="ADMIN", clearance="PUBLIC", token="lowadmin-token")
    g.add_user(email="inactive@example.com", username="inactive", role="CLERK", clearance="PUBLIC", active=False, token="inactive-token")
    return g


@pytest.fixture
def client(gateway: FakeGateway):
    settings = Settings(
        supabase_url="http://fake.invalid", supabase_anon_key="anon", supabase_service_role_key="service",
        expose_docs=True, enable_semantic_embeddings=False, anthropic_api_key=None, openai_api_key=None,
    )
    app = create_app(settings=settings, gateway=gateway)
    with TestClient(app) as c:
        yield c


def auth(token: str) -> dict[str, str]: return {"Authorization": f"Bearer {token}"}