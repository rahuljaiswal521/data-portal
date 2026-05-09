"""Tests for per-tenant Databricks credentials.

Covers:
- GET  /api/v1/account/settings — `databricks` field shape
- PUT  /api/v1/account/settings/databricks
- DELETE /api/v1/account/settings/databricks
- POST /api/v1/account/settings/databricks/test
- HTTP 412 gate on deploy/trigger endpoints when credentials missing
- TenantService get/set/clear_databricks_credentials
"""

from unittest.mock import MagicMock, patch

from app.dependencies import require_databricks_service
from app.main import app
from app.services.databricks_service import DatabricksService

BASE = "/api/v1/account"


class TestDatabricksFieldInAccountSettings:
    def test_databricks_field_present(self, client):
        resp = client.get(f"{BASE}/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "databricks" in data
        assert "configured" in data["databricks"]
        assert "host_preview" in data["databricks"]
        assert "warehouse_id" in data["databricks"]

    def test_databricks_unconfigured_by_default(self, client):
        resp = client.get(f"{BASE}/settings")
        data = resp.json()
        assert data["databricks"]["configured"] is False
        assert data["databricks"]["host_preview"] is None
        assert data["databricks"]["warehouse_id"] is None

    def test_databricks_field_after_set(self, client, mock_tenant):
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_databricks_credentials(
            "default",
            host="https://adb-1234567890123456.7.azuredatabricks.net",
            token="dapi-secret-token-value",
            warehouse_id="abcd1234efgh5678",
        )
        resp = client.get(f"{BASE}/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["databricks"]["configured"] is True
        # Host preview should mask the workspace id
        assert "adb-***" in data["databricks"]["host_preview"]
        assert data["databricks"]["warehouse_id"] == "abcd1234efgh5678"


class TestSetDatabricksCredentials:
    def test_put_credentials_persists(self, client, mock_tenant):
        mock_tenant.ensure_default_tenant()
        body = {
            "host": "https://adb-1234567890123456.7.azuredatabricks.net",
            "token": "dapi-secret-token-value",
            "warehouse_id": "abcd1234efgh5678",
        }
        resp = client.put(f"{BASE}/settings/databricks", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["databricks"]["configured"] is True

        # Verify persistence in tenant service
        creds = mock_tenant.get_databricks_credentials("default")
        assert creds is not None
        assert creds["host"] == body["host"]
        assert creds["token"] == body["token"]
        assert creds["warehouse_id"] == body["warehouse_id"]

    def test_put_token_not_returned_in_response(self, client, mock_tenant):
        mock_tenant.ensure_default_tenant()
        body = {
            "host": "https://adb-1234567890123456.7.azuredatabricks.net",
            "token": "dapi-secret-token-value",
            "warehouse_id": "abcd1234efgh5678",
        }
        resp = client.put(f"{BASE}/settings/databricks", json=body)
        assert resp.status_code == 200
        # Token must never be echoed back
        assert "token" not in resp.json()["databricks"]
        assert body["token"] not in resp.text

    def test_put_validation_min_lengths(self, client):
        # token too short
        resp = client.put(
            f"{BASE}/settings/databricks",
            json={
                "host": "https://adb-1234567890123456.7.azuredatabricks.net",
                "token": "short",
                "warehouse_id": "abcd1234",
            },
        )
        assert resp.status_code == 422


class TestDeleteDatabricksCredentials:
    def test_delete_clears_credentials(self, client, mock_tenant):
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_databricks_credentials(
            "default",
            host="https://adb-1234567890123456.7.azuredatabricks.net",
            token="dapi-secret",
            warehouse_id="abcd1234efgh5678",
        )

        resp = client.delete(f"{BASE}/settings/databricks")
        assert resp.status_code == 200
        assert resp.json()["databricks"]["configured"] is False

        assert mock_tenant.get_databricks_credentials("default") is None

    def test_delete_when_not_configured_is_noop(self, client):
        resp = client.delete(f"{BASE}/settings/databricks")
        assert resp.status_code == 200
        assert resp.json()["databricks"]["configured"] is False


class TestTestDatabricksConnection:
    def test_connection_success(self, client):
        body = {
            "host": "https://adb-1234567890123456.7.azuredatabricks.net",
            "token": "dapi-secret-token",
            "warehouse_id": "abcd1234efgh5678",
        }
        # Patch DatabricksService to simulate a working client
        with patch.object(DatabricksService, "available", new=True), \
             patch.object(DatabricksService, "current_user_email", return_value="alice@example.com"):
            resp = client.post(f"{BASE}/settings/databricks/test", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["user"] == "alice@example.com"

    def test_connection_failure_auth(self, client):
        body = {
            "host": "https://adb-1234567890123456.7.azuredatabricks.net",
            "token": "dapi-bad-token",
            "warehouse_id": "abcd1234efgh5678",
        }
        with patch.object(DatabricksService, "available", new=True), \
             patch.object(DatabricksService, "current_user_email", return_value=None):
            resp = client.post(f"{BASE}/settings/databricks/test", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["user"] is None
        assert "auth" in data["message"].lower() or "fail" in data["message"].lower()

    def test_connection_unavailable_client(self, client):
        body = {
            "host": "https://adb-1234567890123456.7.azuredatabricks.net",
            "token": "dapi-token",
            "warehouse_id": "abcd1234efgh5678",
        }
        with patch.object(DatabricksService, "available", new=False):
            resp = client.post(f"{BASE}/settings/databricks/test", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False

    def test_connection_does_not_persist(self, client, mock_tenant):
        body = {
            "host": "https://adb-1234567890123456.7.azuredatabricks.net",
            "token": "dapi-token",
            "warehouse_id": "abcd1234efgh5678",
        }
        with patch.object(DatabricksService, "available", new=True), \
             patch.object(DatabricksService, "current_user_email", return_value="user@x.com"):
            client.post(f"{BASE}/settings/databricks/test", json=body)
        # Test endpoint must NOT save credentials
        assert mock_tenant.get_databricks_credentials("default") is None


class TestRequireDatabricksGate:
    """The 412 gate on deploy/trigger endpoints when credentials missing.

    Conftest normally bypasses this gate (overrides require_databricks_service),
    so we remove the override here to exercise the real one with mock_db.
    """

    def test_bronze_deploy_returns_412_when_unavailable(self, client, mock_db):
        # Remove the bypass override added in conftest
        app.dependency_overrides.pop(require_databricks_service, None)
        mock_db.available = False
        resp = client.post("/api/v1/bronze/sources/anything/deploy")
        assert resp.status_code == 412
        assert "databricks" in resp.json()["detail"].lower()

    def test_silver_trigger_returns_412_when_unavailable(self, client, mock_db):
        app.dependency_overrides.pop(require_databricks_service, None)
        mock_db.available = False
        resp = client.post("/api/v1/silver/entities/anything/trigger")
        assert resp.status_code == 412


class TestTenantServiceDatabricksMethods:
    def test_set_get_round_trip(self, mock_tenant):
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_databricks_credentials(
            "default", host="https://h", token="tttttttt", warehouse_id="wwww"
        )
        creds = mock_tenant.get_databricks_credentials("default")
        assert creds == {"host": "https://h", "token": "tttttttt", "warehouse_id": "wwww"}

    def test_get_returns_none_when_unset(self, mock_tenant):
        mock_tenant.ensure_default_tenant()
        assert mock_tenant.get_databricks_credentials("default") is None

    def test_get_returns_none_when_partial(self, mock_tenant):
        """All three fields are required — partial returns None."""
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_databricks_credentials(
            "default", host="https://h", token="tttttttt", warehouse_id="wwww"
        )
        # Manually wipe one field to simulate corruption
        import sqlite3
        from app.config import settings
        with sqlite3.connect(settings.tenant_db_path) as conn:
            conn.execute(
                "UPDATE tenants SET databricks_warehouse_id = NULL WHERE id = 'default'"
            )
        assert mock_tenant.get_databricks_credentials("default") is None

    def test_clear_credentials(self, mock_tenant):
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_databricks_credentials(
            "default", host="https://h", token="tttttttt", warehouse_id="wwww"
        )
        mock_tenant.clear_databricks_credentials("default")
        assert mock_tenant.get_databricks_credentials("default") is None
