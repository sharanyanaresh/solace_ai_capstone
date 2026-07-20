"""Shared test fixtures — in-memory SQLite DB, FastAPI TestClient, helpers."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from backend.app.db import Base, get_db
from backend.app.main import app
from backend.app.rate_limit import limiter


@pytest.fixture(autouse=True)
def _disable_rate_limit():
    """Tests share one client IP; the 5/min limiter would 429 across tests. Disable it."""
    prev = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = prev


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def registered_user(client):
    """Register a test user and return (client, tokens_dict)."""
    res = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "securepass123",
        "display_name": "Tester",
    })
    assert res.status_code == 201
    return client, res.json()


@pytest.fixture()
def auth_header(registered_user):
    """Return (client, auth_headers) for an authenticated user."""
    client, data = registered_user
    return client, {"Authorization": f"Bearer {data['access_token']}"}
