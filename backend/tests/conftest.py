from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_ROOT = Path("/tmp/socialmediapost-tests")
TEST_ROOT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_ROOT / 'test.db'}")
os.environ.setdefault("STORAGE_ROOT", str(TEST_ROOT / "storage"))
os.environ.setdefault("SESSION_SECRET", "12345678901234567890123456789012")
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("AUTH_REQUIRED", "true")

from app.main import app  # noqa: E402
from app.core.db import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        response = test_client.post("/api/auth/bootstrap")
        assert response.status_code == 200
        yield test_client


@pytest.fixture
def csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("smp_csrf") or ""}
