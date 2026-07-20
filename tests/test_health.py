"""Tests for health and config endpoints."""
from __future__ import annotations


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "solace"


def test_public_config(client):
    res = client.get("/api/v1/config")
    assert res.status_code == 200
    assert "allow_open_registration" in res.json()
