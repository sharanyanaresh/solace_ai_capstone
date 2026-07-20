"""Tests for authentication endpoints."""
from __future__ import annotations


def test_register_success(client):
    res = client.post("/api/v1/auth/register", json={
        "email": "new@example.com",
        "password": "strongpass1",
    })
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "new@example.com"


def test_register_duplicate_email(registered_user):
    client, _ = registered_user
    res = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "anotherpass1",
    })
    assert res.status_code == 400
    assert "already registered" in res.json()["detail"].lower()


def test_register_short_password(client):
    res = client.post("/api/v1/auth/register", json={
        "email": "short@example.com",
        "password": "abc",
    })
    assert res.status_code == 422


def test_login_success(registered_user):
    client, _ = registered_user
    res = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "securepass123",
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "test@example.com"


def test_login_wrong_password(registered_user):
    client, _ = registered_user
    res = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "wrongpassword",
    })
    assert res.status_code == 401


def test_login_nonexistent_user(client):
    res = client.post("/api/v1/auth/login", json={
        "email": "ghost@example.com",
        "password": "anything123",
    })
    assert res.status_code == 401


def test_me_authenticated(auth_header):
    client, headers = auth_header
    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["email"] == "test@example.com"


def test_me_unauthenticated(client):
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


def test_refresh_rotates_token(registered_user):
    client, data = registered_user
    old_refresh = data["refresh_token"]
    res = client.post("/api/v1/auth/refresh", json={
        "refresh_token": old_refresh,
    })
    assert res.status_code == 200
    new_data = res.json()
    assert "access_token" in new_data
    assert "refresh_token" in new_data
    assert new_data["refresh_token"] != old_refresh

    # old refresh token should now be revoked
    res2 = client.post("/api/v1/auth/refresh", json={
        "refresh_token": old_refresh,
    })
    assert res2.status_code == 401


def test_logout(registered_user):
    client, data = registered_user
    res = client.post("/api/v1/auth/logout", json={
        "refresh_token": data["refresh_token"],
    })
    assert res.status_code == 204

    # refresh with revoked token should fail
    res2 = client.post("/api/v1/auth/refresh", json={
        "refresh_token": data["refresh_token"],
    })
    assert res2.status_code == 401
