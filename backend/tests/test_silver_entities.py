"""Tests for Silver entity CRUD endpoints."""

import pytest

from tests.conftest import make_silver_entity

BASE = "/api/v1/silver"


# ──────────────────────────────────────────────────────────────────────
# List entities
# ──────────────────────────────────────────────────────────────────────

class TestListEntities:
    def test_list_empty(self, client):
        resp = client.get(f"{BASE}/entities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["entities"] == []

    def test_list_after_create(self, client):
        client.post(f"{BASE}/entities", json=make_silver_entity("e1"))
        client.post(f"{BASE}/entities", json=make_silver_entity("e2", domain="policy"))
        resp = client.get(f"{BASE}/entities")
        assert resp.json()["total"] == 2

    def test_list_filter_by_domain(self, client):
        client.post(f"{BASE}/entities", json=make_silver_entity("c1", domain="customer"))
        client.post(f"{BASE}/entities", json=make_silver_entity("p1", domain="policy"))
        resp = client.get(f"{BASE}/entities?domain=customer")
        data = resp.json()
        assert data["total"] == 1
        assert data["entities"][0]["name"] == "c1"

    def test_list_filter_by_enabled(self, client):
        client.post(f"{BASE}/entities", json=make_silver_entity("en1"))
        e2 = make_silver_entity("en2")
        e2["enabled"] = False
        client.post(f"{BASE}/entities", json=e2)
        resp = client.get(f"{BASE}/entities?enabled=true")
        data = resp.json()
        assert all(e["enabled"] for e in data["entities"])

    def test_list_filter_by_scd_type(self, client):
        e_scd2 = make_silver_entity("scd2_e")
        e_scd2["target"]["scd_type"] = "scd2"
        client.post(f"{BASE}/entities", json=e_scd2)

        e_append = make_silver_entity("app_e")
        e_append["target"]["scd_type"] = "append"
        e_append["target"]["business_keys"] = []
        client.post(f"{BASE}/entities", json=e_append)

        resp = client.get(f"{BASE}/entities?scd_type=scd2")
        data = resp.json()
        assert len(data["entities"]) == 1
        assert data["entities"][0]["scd_type"] == "scd2"


# ──────────────────────────────────────────────────────────────────────
# Create entity — happy paths
# ──────────────────────────────────────────────────────────────────────

class TestCreateEntity:
    def test_create_minimal(self, client):
        resp = client.post(f"{BASE}/entities", json=make_silver_entity("min_entity"))
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "min_entity"
        assert "created successfully" in data["message"]

    def test_create_with_description_and_tags(self, client):
        payload = make_silver_entity("tagged_entity")
        payload["description"] = "My silver entity"
        payload["tags"] = {"team": "analytics", "domain": "customer"}
        resp = client.post(f"{BASE}/entities", json=payload)
        assert resp.status_code == 201

    def test_create_with_schedule(self, client):
        payload = make_silver_entity("sched_entity")
        payload["schedule"] = {"cron_expression": "0 6 * * *", "timezone": "UTC"}
        resp = client.post(f"{BASE}/entities", json=payload)
        assert resp.status_code == 201

    def test_create_append_scd_type(self, client):
        payload = make_silver_entity("append_entity")
        payload["target"]["scd_type"] = "append"
        payload["target"]["business_keys"] = []
        resp = client.post(f"{BASE}/entities", json=payload)
        assert resp.status_code == 201

    def test_create_returns_git_commit(self, client, mock_git):
        resp = client.post(f"{BASE}/entities", json=make_silver_entity("git_entity"))
        assert resp.status_code == 201
        assert resp.json()["git_commit"] == "deadbeef"

    def test_create_multi_source(self, client):
        payload = make_silver_entity("multi_src_entity")
        payload["sources"].append({
            "bronze_table": "dev.bronze.orders",
            "priority": 2,
            "columns": [
                {"source": "order_id", "target": "order_id"},
            ],
        })
        resp = client.post(f"{BASE}/entities", json=payload)
        assert resp.status_code == 201


# ──────────────────────────────────────────────────────────────────────
# Create entity — validation errors (422)
# ──────────────────────────────────────────────────────────────────────

class TestCreateEntityValidation:
    def test_missing_name(self, client):
        payload = {
            "domain": "customer",
            "target": {"catalog": "dev", "schema": "slv_customer", "table": "t",
                       "business_keys": ["id"]},
            "sources": [{"bronze_table": "t", "columns": [{"source": "id", "target": "id"}]}],
        }
        resp = client.post(f"{BASE}/entities", json=payload)
        assert resp.status_code == 422

    def test_missing_domain(self, client):
        payload = {
            "name": "no_domain",
            "target": {"catalog": "dev", "schema": "slv_x", "table": "t",
                       "business_keys": ["id"]},
            "sources": [{"bronze_table": "t", "columns": [{"source": "id", "target": "id"}]}],
        }
        resp = client.post(f"{BASE}/entities", json=payload)
        assert resp.status_code == 422

    def test_scd2_without_business_keys(self, client):
        payload = make_silver_entity("scd2_nkeys")
        payload["target"]["scd_type"] = "scd2"
        payload["target"]["business_keys"] = []
        resp = client.post(f"{BASE}/entities", json=payload)
        assert resp.status_code == 422

    def test_no_sources(self, client):
        payload = make_silver_entity("no_sources")
        payload["sources"] = []
        resp = client.post(f"{BASE}/entities", json=payload)
        assert resp.status_code == 422

    def test_source_no_columns(self, client):
        payload = make_silver_entity("no_cols")
        payload["sources"][0]["columns"] = []
        resp = client.post(f"{BASE}/entities", json=payload)
        assert resp.status_code == 422

    def test_missing_target_catalog(self, client):
        payload = make_silver_entity("no_catalog")
        payload["target"]["catalog"] = ""
        resp = client.post(f"{BASE}/entities", json=payload)
        assert resp.status_code == 422

    def test_missing_target_schema(self, client):
        payload = make_silver_entity("no_schema")
        payload["target"]["schema"] = ""
        resp = client.post(f"{BASE}/entities", json=payload)
        assert resp.status_code == 422

    def test_missing_target_table(self, client):
        payload = make_silver_entity("no_table")
        payload["target"]["table"] = ""
        resp = client.post(f"{BASE}/entities", json=payload)
        assert resp.status_code == 422

    def test_empty_body(self, client):
        resp = client.post(f"{BASE}/entities", json={})
        assert resp.status_code == 422


# ──────────────────────────────────────────────────────────────────────
# Create entity — conflict (409)
# ──────────────────────────────────────────────────────────────────────

class TestCreateEntityConflict:
    def test_duplicate_name(self, client):
        payload = make_silver_entity("dup_entity")
        client.post(f"{BASE}/entities", json=payload)
        resp = client.post(f"{BASE}/entities", json=payload)
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]


# ──────────────────────────────────────────────────────────────────────
# Get entity
# ──────────────────────────────────────────────────────────────────────

class TestGetEntity:
    def test_get_existing(self, client):
        client.post(f"{BASE}/entities", json=make_silver_entity("get_entity"))
        resp = client.get(f"{BASE}/entities/get_entity")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "get_entity"
        assert "raw_yaml" in data
        assert "target" in data
        assert "sources" in data

    def test_get_nonexistent(self, client):
        resp = client.get(f"{BASE}/entities/ghost_entity")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ──────────────────────────────────────────────────────────────────────
# Update entity
# ──────────────────────────────────────────────────────────────────────

class TestUpdateEntity:
    def test_update_description(self, client):
        client.post(f"{BASE}/entities", json=make_silver_entity("upd_entity"))
        resp = client.put(f"{BASE}/entities/upd_entity", json={"description": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "upd_entity"

    def test_update_enabled(self, client):
        client.post(f"{BASE}/entities", json=make_silver_entity("en_entity"))
        resp = client.put(f"{BASE}/entities/en_entity", json={"enabled": False})
        assert resp.status_code == 200

    def test_update_nonexistent(self, client):
        resp = client.put(f"{BASE}/entities/ghost", json={"description": "x"})
        assert resp.status_code == 404

    def test_update_empty_body(self, client):
        client.post(f"{BASE}/entities", json=make_silver_entity("noop_entity"))
        resp = client.put(f"{BASE}/entities/noop_entity", json={})
        assert resp.status_code == 200


# ──────────────────────────────────────────────────────────────────────
# Delete entity
# ──────────────────────────────────────────────────────────────────────

class TestDeleteEntity:
    def test_delete_existing(self, client):
        client.post(f"{BASE}/entities", json=make_silver_entity("del_entity"))
        resp = client.delete(f"{BASE}/entities/del_entity")
        assert resp.status_code == 200
        assert resp.json()["name"] == "del_entity"
        assert "deleted" in resp.json()["message"].lower()

    def test_delete_nonexistent(self, client):
        resp = client.delete(f"{BASE}/entities/no_entity")
        assert resp.status_code == 404

    def test_delete_removes_from_list(self, client):
        client.post(f"{BASE}/entities", json=make_silver_entity("gone_entity"))
        client.delete(f"{BASE}/entities/gone_entity")
        resp = client.get(f"{BASE}/entities")
        names = [e["name"] for e in resp.json()["entities"]]
        assert "gone_entity" not in names


# ──────────────────────────────────────────────────────────────────────
# Validate entity
# ──────────────────────────────────────────────────────────────────────

class TestValidateEntity:
    def test_validate_valid(self, client):
        payload = make_silver_entity("v_entity")
        resp = client.post(f"{BASE}/entities/v_entity/validate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["errors"] == []
        assert data["yaml_preview"] is not None

    def test_validate_invalid_scd2_no_bkeys(self, client):
        payload = make_silver_entity("inv_entity")
        payload["target"]["business_keys"] = []
        resp = client.post(f"{BASE}/entities/inv_entity/validate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0
        assert data["yaml_preview"] is None

    def test_validate_path_name_not_checked(self, client):
        # The {name} in path is not validated against existing entities
        payload = make_silver_entity("body_entity")
        resp = client.post(f"{BASE}/entities/nonexistent/validate", json=payload)
        assert resp.status_code == 200
        assert resp.json()["valid"] is True
