"""Tests for Bronze source CRUD endpoints."""

import pytest

from tests.conftest import make_file_source, make_jdbc_source


BASE = "/api/v1/bronze"


# ──────────────────────────────────────────────────────────────────────
# List sources
# ──────────────────────────────────────────────────────────────────────

class TestListSources:
    def test_list_empty(self, client):
        resp = client.get(f"{BASE}/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["sources"] == []

    def test_list_after_create(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("src1"))
        client.post(f"{BASE}/sources", json=make_jdbc_source("src2"))
        resp = client.get(f"{BASE}/sources")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_list_filter_by_type(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("fsrc"))
        client.post(f"{BASE}/sources", json=make_jdbc_source("jsrc"))
        resp = client.get(f"{BASE}/sources?source_type=file")
        assert resp.status_code == 200
        sources = resp.json()["sources"]
        assert all(s["source_type"] == "file" for s in sources)
        assert len(sources) == 1

    def test_list_filter_by_enabled(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("enabled_src"))
        client.post(f"{BASE}/sources", json=make_file_source("disabled_src", enabled=False))
        resp = client.get(f"{BASE}/sources?enabled=true")
        assert resp.status_code == 200
        sources = resp.json()["sources"]
        assert all(s["enabled"] for s in sources)

    def test_list_filter_by_domain(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("d1", tags={"domain": "finance"}))
        client.post(f"{BASE}/sources", json=make_file_source("d2", tags={"domain": "hr"}))
        resp = client.get(f"{BASE}/sources?domain=finance")
        assert resp.status_code == 200
        sources = resp.json()["sources"]
        assert len(sources) == 1
        assert sources[0]["name"] == "d1"


# ──────────────────────────────────────────────────────────────────────
# Create source — happy paths
# ──────────────────────────────────────────────────────────────────────

class TestCreateSource:
    def test_create_file_source(self, client):
        payload = make_file_source("my_file_src")
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "my_file_src"
        assert "yaml_path" in data
        assert "created successfully" in data["message"]

    def test_create_jdbc_source(self, client):
        payload = make_jdbc_source("my_jdbc_src")
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 201
        assert resp.json()["name"] == "my_jdbc_src"

    def test_create_jdbc_with_query(self, client):
        payload = {
            "name": "jdbc_query",
            "source_type": "jdbc",
            "target": {"catalog": "dev", "schema": "bronze", "table": "jdbc_query"},
            "extract": {"query": "SELECT * FROM raw WHERE id > 0"},
        }
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 201

    def test_create_api_source(self, client):
        payload = {
            "name": "api_src",
            "source_type": "api",
            "target": {"catalog": "dev", "schema": "bronze", "table": "api_src"},
            "extract": {
                "base_url": "https://api.example.com",
                "endpoint": "/data",
                "method": "GET",
            },
        }
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 201

    def test_create_api_source_with_auth(self, client):
        payload = {
            "name": "api_auth",
            "source_type": "api",
            "target": {"catalog": "dev", "schema": "bronze", "table": "api_auth"},
            "extract": {
                "base_url": "https://api.example.com",
                "auth": {"type": "bearer", "secret_scope": "scope1", "secret_key_token": "key1"},
                "pagination": {"type": "offset", "page_size": 50},
            },
        }
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 201

    def test_create_stream_kafka(self, client):
        payload = {
            "name": "kafka_src",
            "source_type": "stream",
            "target": {"catalog": "dev", "schema": "bronze", "table": "kafka_src"},
            "extract": {
                "kafka_bootstrap_servers": "broker1:9092",
                "kafka_topic": "events",
                "kafka_consumer_group": "portal-cg",
            },
        }
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 201

    def test_create_stream_eventhub(self, client):
        payload = {
            "name": "eh_src",
            "source_type": "stream",
            "target": {"catalog": "dev", "schema": "bronze", "table": "eh_src"},
            "extract": {"event_hub_connection_string_key": "my-eh-key"},
        }
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 201

    def test_create_returns_git_commit(self, client, mock_git):
        resp = client.post(f"{BASE}/sources", json=make_file_source("git_test"))
        assert resp.status_code == 201
        assert resp.json()["git_commit"] == "deadbeef"

    def test_create_with_description_and_tags(self, client):
        payload = make_file_source(
            "tagged_src",
            description="My tagged source",
            tags={"domain": "finance", "team": "data"},
        )
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 201

    def test_create_with_schedule(self, client):
        payload = make_file_source("scheduled_src")
        payload["schedule"] = {"cron_expression": "0 8 * * *", "timezone": "Australia/Sydney"}
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 201

    def test_create_with_scd2_cdc(self, client):
        payload = make_file_source("scd2_src")
        payload["target"]["cdc"] = {
            "enabled": True,
            "mode": "scd2",
            "primary_keys": ["id"],
        }
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 201


# ──────────────────────────────────────────────────────────────────────
# Create source — validation errors (422)
# ──────────────────────────────────────────────────────────────────────

class TestCreateSourceValidation:
    def test_missing_name_pydantic(self, client):
        payload = {
            "source_type": "file",
            "target": {"catalog": "dev", "schema": "bronze", "table": "t"},
            "extract": {"path": "/data"},
        }
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 422

    def test_missing_source_type_pydantic(self, client):
        payload = {
            "name": "no_type",
            "target": {"catalog": "dev", "schema": "bronze", "table": "t"},
        }
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 422

    def test_invalid_source_type_pydantic(self, client):
        payload = {
            "name": "bad_type",
            "source_type": "database",
            "target": {"catalog": "dev", "schema": "bronze", "table": "t"},
        }
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 422

    def test_invalid_cdc_mode_pydantic(self, client):
        payload = make_file_source("cdc_bad")
        payload["target"]["cdc"] = {"enabled": True, "mode": "invalid_mode"}
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 422

    def test_invalid_load_type_pydantic(self, client):
        payload = make_file_source("lt_bad")
        payload["extract"]["load_type"] = "streaming"
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 422

    def test_file_source_missing_path(self, client):
        payload = {
            "name": "file_no_path",
            "source_type": "file",
            "target": {"catalog": "dev", "schema": "bronze", "table": "t"},
            "extract": {},
        }
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 422

    def test_jdbc_source_missing_table_and_query(self, client):
        payload = {
            "name": "jdbc_empty",
            "source_type": "jdbc",
            "target": {"catalog": "dev", "schema": "bronze", "table": "t"},
            "extract": {},
        }
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 422

    def test_api_source_missing_base_url(self, client):
        payload = {
            "name": "api_no_url",
            "source_type": "api",
            "target": {"catalog": "dev", "schema": "bronze", "table": "t"},
            "extract": {},
        }
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 422

    def test_stream_source_missing_both_brokers(self, client):
        payload = {
            "name": "stream_empty",
            "source_type": "stream",
            "target": {"catalog": "dev", "schema": "bronze", "table": "t"},
            "extract": {},
        }
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 422

    def test_scd2_cdc_without_primary_keys(self, client):
        payload = make_file_source("scd2_no_keys")
        payload["target"]["cdc"] = {
            "enabled": True,
            "mode": "scd2",
            "primary_keys": [],
        }
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 422

    def test_upsert_cdc_without_primary_keys(self, client):
        payload = make_file_source("upsert_no_keys")
        payload["target"]["cdc"] = {
            "enabled": True,
            "mode": "upsert",
            "primary_keys": [],
        }
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 422

    def test_empty_body(self, client):
        resp = client.post(f"{BASE}/sources", json={})
        assert resp.status_code == 422

    def test_empty_name_string(self, client):
        payload = make_file_source("")
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 422


# ──────────────────────────────────────────────────────────────────────
# Create source — conflict (409)
# ──────────────────────────────────────────────────────────────────────

class TestCreateSourceConflict:
    def test_duplicate_name(self, client):
        payload = make_file_source("dup_src")
        client.post(f"{BASE}/sources", json=payload)
        resp = client.post(f"{BASE}/sources", json=payload)
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]


# ──────────────────────────────────────────────────────────────────────
# Get source
# ──────────────────────────────────────────────────────────────────────

class TestGetSource:
    def test_get_existing(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("get_me"))
        resp = client.get(f"{BASE}/sources/get_me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "get_me"
        assert data["source_type"] == "file"
        assert "raw_yaml" in data
        assert "target" in data

    def test_get_nonexistent(self, client):
        resp = client.get(f"{BASE}/sources/does_not_exist")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ──────────────────────────────────────────────────────────────────────
# Update source
# ──────────────────────────────────────────────────────────────────────

class TestUpdateSource:
    def test_update_description(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("upd_src"))
        resp = client.put(f"{BASE}/sources/upd_src", json={"description": "New desc"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "upd_src"

    def test_update_enabled_toggle(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("toggle_src"))
        resp = client.put(f"{BASE}/sources/toggle_src", json={"enabled": False})
        assert resp.status_code == 200

    def test_update_tags(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("tags_src"))
        resp = client.put(f"{BASE}/sources/tags_src", json={"tags": {"env": "prod"}})
        assert resp.status_code == 200

    def test_update_nonexistent(self, client):
        resp = client.put(f"{BASE}/sources/ghost", json={"description": "x"})
        assert resp.status_code == 404

    def test_update_empty_body_is_ok(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("noop_src"))
        resp = client.put(f"{BASE}/sources/noop_src", json={})
        assert resp.status_code == 200


# ──────────────────────────────────────────────────────────────────────
# Delete source
# ──────────────────────────────────────────────────────────────────────

class TestDeleteSource:
    def test_delete_existing(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("del_src"))
        resp = client.delete(f"{BASE}/sources/del_src")
        assert resp.status_code == 200
        assert resp.json()["name"] == "del_src"
        assert "deleted" in resp.json()["message"].lower()

    def test_delete_nonexistent(self, client):
        resp = client.delete(f"{BASE}/sources/no_such_source")
        assert resp.status_code == 404

    def test_delete_removes_from_list(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("gone_src"))
        client.delete(f"{BASE}/sources/gone_src")
        resp = client.get(f"{BASE}/sources")
        names = [s["name"] for s in resp.json()["sources"]]
        assert "gone_src" not in names


# ──────────────────────────────────────────────────────────────────────
# Validate source
# ──────────────────────────────────────────────────────────────────────

class TestValidateSource:
    def test_validate_valid_config(self, client):
        payload = make_file_source("v_src")
        resp = client.post(f"{BASE}/sources/v_src/validate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["errors"] == []
        assert data["yaml_preview"] is not None

    def test_validate_invalid_config(self, client):
        payload = {
            "name": "bad_file",
            "source_type": "file",
            "target": {"catalog": "dev", "schema": "bronze", "table": "t"},
            "extract": {},  # missing path
        }
        resp = client.post(f"{BASE}/sources/any_name/validate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0
        assert data["yaml_preview"] is None

    def test_validate_nonexistent_source_name_path(self, client):
        # The name in the path is NOT used for validation — no 404
        payload = make_file_source("v_src_body")
        resp = client.post(f"{BASE}/sources/nonexistent_name/validate", json=payload)
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_validate_returns_yaml_preview(self, client):
        payload = make_file_source("yaml_preview_test")
        resp = client.post(f"{BASE}/sources/x/validate", json=payload)
        assert resp.status_code == 200
        preview = resp.json()["yaml_preview"]
        assert "yaml_preview_test" in preview
        assert "source_type: file" in preview
