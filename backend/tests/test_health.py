"""Tests for GET /health and GET /environments endpoints."""

import yaml


class TestHealth:
    def test_health_returns_200(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_health_response_fields(self, client):
        data = client.get("/api/v1/health").json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "framework_root" in data
        assert "sources_dir_exists" in data
        assert "databricks_configured" in data

    def test_health_sources_dir_exists(self, client):
        # isolate_settings creates the sources dir, so this should be True
        data = client.get("/api/v1/health").json()
        # sources_dir is {bronze_conf}/sources which was created by fixture
        assert isinstance(data["sources_dir_exists"], bool)

    def test_health_databricks_not_configured(self, client, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "databricks_host", None)
        monkeypatch.setattr(settings, "databricks_token", None)
        data = client.get("/api/v1/health").json()
        assert data["databricks_configured"] is False

    def test_health_databricks_configured(self, client, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "databricks_host", "https://adb-123.azuredatabricks.net")
        monkeypatch.setattr(settings, "databricks_token", "dapi-fake-token")
        data = client.get("/api/v1/health").json()
        assert data["databricks_configured"] is True


class TestEnvironments:
    def test_environments_empty(self, client):
        resp = client.get("/api/v1/environments")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_environments_with_files(self, client, tmp_path, monkeypatch):
        from app.config import settings

        # Create a dev.yaml environment file
        env_dir = settings.environments_dir
        env_dir.mkdir(parents=True, exist_ok=True)
        (env_dir / "dev.yaml").write_text("catalog: dev\nenv: development\n")
        (env_dir / "prod.yaml").write_text("catalog: prod\nenv: production\n")

        resp = client.get("/api/v1/environments")
        assert resp.status_code == 200
        envs = resp.json()
        assert len(envs) == 2
        names = [e["name"] for e in envs]
        assert "dev" in names
        assert "prod" in names

    def test_environments_variables_parsed(self, client, monkeypatch):
        from app.config import settings

        env_dir = settings.environments_dir
        env_dir.mkdir(parents=True, exist_ok=True)
        (env_dir / "staging.yaml").write_text("catalog: staging\nregion: us-east-1\n")

        resp = client.get("/api/v1/environments")
        assert resp.status_code == 200
        env = resp.json()[0]
        assert env["name"] == "staging"
        assert env["variables"]["catalog"] == "staging"
        assert env["variables"]["region"] == "us-east-1"
