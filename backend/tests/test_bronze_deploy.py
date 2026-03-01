"""Tests for Bronze deploy and trigger endpoints."""

from tests.conftest import make_file_source

BASE = "/api/v1/bronze"


class TestRedeploy:
    def test_redeploy_existing_source(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("deploy_src"))
        resp = client.post(f"{BASE}/sources/deploy_src/deploy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "deploy_src"
        assert "redeployed" in data["message"].lower()

    def test_redeploy_nonexistent_source(self, client):
        resp = client.post(f"{BASE}/sources/ghost_src/deploy")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_redeploy_returns_job_id_when_db_available(self, client, mock_db):
        mock_db.available = True
        mock_db.create_or_update_job.return_value = "job_99"
        client.post(f"{BASE}/sources", json=make_file_source("db_deploy"))
        resp = client.post(f"{BASE}/sources/db_deploy/deploy")
        assert resp.status_code == 200


class TestTriggerRun:
    def test_trigger_no_databricks(self, client, mock_db):
        """When Databricks is unavailable, trigger still returns 200 with None run_id."""
        mock_db.available = False
        mock_db.trigger_job.return_value = None
        client.post(f"{BASE}/sources", json=make_file_source("trigger_src"))
        resp = client.post(f"{BASE}/sources/trigger_src/trigger")
        assert resp.status_code == 200
        data = resp.json()
        assert "trigger_src" in data["message"]
        assert data["run_id"] is None

    def test_trigger_with_run_id(self, client, mock_db):
        mock_db.trigger_job.return_value = "run_42"
        client.post(f"{BASE}/sources", json=make_file_source("run_src"))
        resp = client.post(f"{BASE}/sources/run_src/trigger")
        assert resp.status_code == 200
        assert resp.json()["run_id"] == "run_42"

    def test_trigger_nonexistent_source(self, client):
        resp = client.post(f"{BASE}/sources/no_such/trigger")
        assert resp.status_code == 404
