"""Tests for the api_key_auth HTTP middleware in app/main.py.

The middleware behaviour:
- If settings.portal_api_key is None/empty → all requests pass through (auth disabled)
- If key is set and path starts with /api/v1/health → pass through unconditionally
- If key is set and X-API-Key header is missing or wrong → 401
- If key is set and X-API-Key header matches → pass through
"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


# ── Helpers ────────────────────────────────────────────────────────────

HEALTH = "/api/v1/health"
SOURCES = "/api/v1/bronze/sources"


# ── Tests ──────────────────────────────────────────────────────────────


class TestAuthDisabled:
    """When portal_api_key is not configured, all requests pass through."""

    def test_auth_disabled_sources_open(self, client, monkeypatch):
        """With no key set, GET /bronze/sources returns 200 without any header."""
        monkeypatch.setattr(settings, "portal_api_key", None)
        resp = client.get(SOURCES)
        assert resp.status_code == 200

    def test_auth_disabled_health_open(self, client, monkeypatch):
        """With no key set, health endpoint is open."""
        monkeypatch.setattr(settings, "portal_api_key", None)
        resp = client.get(HEALTH)
        assert resp.status_code == 200

    def test_auth_disabled_empty_string(self, client, monkeypatch):
        """Empty string key also disables auth (falsy check)."""
        monkeypatch.setattr(settings, "portal_api_key", "")
        resp = client.get(SOURCES)
        assert resp.status_code == 200


class TestAuthHealthAlwaysOpen:
    """Health endpoint bypasses auth even when a key is configured."""

    def test_health_open_without_header(self, client, monkeypatch):
        """Health endpoint returns 200 when key is set and no header provided."""
        monkeypatch.setattr(settings, "portal_api_key", "secret123")
        resp = client.get(HEALTH)
        assert resp.status_code == 200

    def test_health_open_with_wrong_header(self, client, monkeypatch):
        """Health endpoint returns 200 even when wrong key is supplied."""
        monkeypatch.setattr(settings, "portal_api_key", "secret123")
        resp = client.get(HEALTH, headers={"X-API-Key": "wrong"})
        assert resp.status_code == 200

    def test_health_open_with_correct_header(self, client, monkeypatch):
        """Health endpoint returns 200 with correct key (sanity check)."""
        monkeypatch.setattr(settings, "portal_api_key", "secret123")
        resp = client.get(HEALTH, headers={"X-API-Key": "secret123"})
        assert resp.status_code == 200


class TestAuthProtectedEndpoints:
    """Protected endpoints reject requests without a valid API key."""

    def test_missing_key_returns_401(self, client, monkeypatch):
        """When key configured, request without X-API-Key header → 401."""
        monkeypatch.setattr(settings, "portal_api_key", "secret123")
        resp = client.get(SOURCES)
        assert resp.status_code == 401

    def test_wrong_key_returns_401(self, client, monkeypatch):
        """Wrong key → 401."""
        monkeypatch.setattr(settings, "portal_api_key", "secret123")
        resp = client.get(SOURCES, headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_401_response_body(self, client, monkeypatch):
        """401 response includes a detail message."""
        monkeypatch.setattr(settings, "portal_api_key", "secret123")
        resp = client.get(SOURCES)
        body = resp.json()
        assert "detail" in body

    def test_correct_key_passes(self, client, monkeypatch):
        """Correct X-API-Key header → 200 (request reaches the handler)."""
        monkeypatch.setattr(settings, "portal_api_key", "secret123")
        resp = client.get(SOURCES, headers={"X-API-Key": "secret123"})
        assert resp.status_code == 200

    def test_correct_key_on_post(self, client, monkeypatch):
        """Correct key works on POST endpoints too."""
        monkeypatch.setattr(settings, "portal_api_key", "my-key")
        payload = {
            "name": "auth_test_src",
            "source_type": "file",
            "target": {"catalog": "dev", "schema": "bronze", "table": "auth_test_src"},
            "extract": {"path": "/data/auth"},
        }
        resp = client.post(SOURCES, json=payload, headers={"X-API-Key": "my-key"})
        assert resp.status_code == 201

    def test_missing_key_on_post_returns_401(self, client, monkeypatch):
        """Missing key on POST → 401 (not 422)."""
        monkeypatch.setattr(settings, "portal_api_key", "my-key")
        payload = {
            "name": "auth_test_src",
            "source_type": "file",
            "target": {"catalog": "dev", "schema": "bronze", "table": "auth_test_src"},
            "extract": {"path": "/data/auth"},
        }
        resp = client.post(SOURCES, json=payload)
        assert resp.status_code == 401
