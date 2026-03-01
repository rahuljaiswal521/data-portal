"""Tests for Silver monitoring endpoints: stats, run history, diagram."""

from tests.conftest import make_silver_entity

BASE = "/api/v1/silver"


class TestSilverStats:
    def test_stats_empty(self, client):
        resp = client.get(f"{BASE}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_entities"] == 0
        assert data["enabled_entities"] == 0
        assert data["domains"] == []
        assert data["entities_by_domain"] == {}
        assert data["entities_by_scd_type"] == {}

    def test_stats_required_fields(self, client):
        resp = client.get(f"{BASE}/stats")
        data = resp.json()
        for field in ["total_entities", "enabled_entities", "domains",
                      "entities_by_domain", "entities_by_scd_type"]:
            assert field in data

    def test_stats_counts(self, client):
        client.post(f"{BASE}/entities", json=make_silver_entity("e1", domain="customer"))
        e2 = make_silver_entity("e2", domain="policy")
        e2["enabled"] = False
        client.post(f"{BASE}/entities", json=e2)

        resp = client.get(f"{BASE}/stats")
        data = resp.json()
        assert data["total_entities"] == 2
        assert data["enabled_entities"] == 1
        assert "customer" in data["domains"]
        assert "policy" in data["domains"]

    def test_stats_by_domain(self, client):
        client.post(f"{BASE}/entities", json=make_silver_entity("c1", domain="customer"))
        client.post(f"{BASE}/entities", json=make_silver_entity("c2", domain="customer"))
        client.post(f"{BASE}/entities", json=make_silver_entity("p1", domain="policy"))

        resp = client.get(f"{BASE}/stats")
        by_domain = resp.json()["entities_by_domain"]
        assert by_domain.get("customer", 0) == 2
        assert by_domain.get("policy", 0) == 1


def make_silver_entity(name="test_entity", domain="customer", **overrides):
    base = {
        "name": name,
        "domain": domain,
        "target": {
            "catalog": "dev",
            "schema": f"slv_{domain}",
            "table": name,
            "scd_type": "scd2",
            "business_keys": ["id"],
        },
        "sources": [
            {
                "bronze_table": "dev.bronze.raw",
                "columns": [{"source": "id", "target": "id"}],
            }
        ],
    }
    base.update(overrides)
    return base


class TestSilverEntityRuns:
    def test_runs_for_nonexistent_entity_returns_empty(self, client):
        # Silver monitoring: graceful empty list (not 404) for non-existent entity
        resp = client.get(f"{BASE}/entities/nonexistent/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_name"] == "nonexistent"
        assert data["runs"] == []
        assert data["total"] == 0

    def test_runs_for_existing_entity_db_unavailable(self, client):
        client.post(f"{BASE}/entities", json=make_silver_entity("run_entity"))
        resp = client.get(f"{BASE}/entities/run_entity/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_name"] == "run_entity"
        assert data["runs"] == []

    def test_runs_with_limit(self, client):
        client.post(f"{BASE}/entities", json=make_silver_entity("lim_entity"))
        resp = client.get(f"{BASE}/entities/lim_entity/runs?limit=10")
        assert resp.status_code == 200


class TestSilverDiagram:
    def test_diagram_empty(self, client):
        resp = client.get(f"{BASE}/diagram")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mermaid"] == "erDiagram"
        assert data["entity_count"] == 0
        assert data["domains"] == []

    def test_diagram_with_entities(self, client):
        client.post(f"{BASE}/entities", json=make_silver_entity("diag_cust", domain="customer"))
        resp = client.get(f"{BASE}/diagram")
        assert resp.status_code == 200
        data = resp.json()
        assert "erDiagram" in data["mermaid"]
        assert data["entity_count"] >= 1
        assert "customer" in data["domains"]

    def test_diagram_contains_entity_name(self, client):
        client.post(f"{BASE}/entities", json=make_silver_entity("special_entity"))
        resp = client.get(f"{BASE}/diagram")
        assert resp.status_code == 200
        assert "special_entity" in resp.json()["mermaid"]
