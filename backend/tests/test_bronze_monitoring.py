"""Tests for Bronze monitoring endpoints: run history, dead letters, stats."""

from tests.conftest import make_file_source

BASE = "/api/v1/bronze"


class TestRunHistory:
    def test_run_history_404_for_nonexistent(self, client):
        resp = client.get(f"{BASE}/sources/no_such/runs")
        assert resp.status_code == 404

    def test_run_history_empty_when_audit_returns_nothing(self, client, mock_audit):
        # Source exists and has a catalog, but audit returns no rows → empty runs
        mock_audit.get_run_history.return_value = []
        client.post(f"{BASE}/sources", json=make_file_source("no_runs_src"))
        resp = client.get(f"{BASE}/sources/no_runs_src/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_name"] == "no_runs_src"
        assert data["runs"] == []
        assert data["total"] == 0

    def test_run_history_with_mock_data(self, client, mock_audit):
        mock_audit.get_run_history.return_value = [
            {
                "source_name": "mock_src",
                "environment": "dev",
                "status": "SUCCEEDED",
                "records_read": 100,
                "records_written": 98,
                "records_quarantined": 2,
            }
        ]
        client.post(f"{BASE}/sources", json=make_file_source("mock_src"))
        resp = client.get(f"{BASE}/sources/mock_src/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["runs"][0]["status"] == "SUCCEEDED"

    def test_run_history_default_limit(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("limit_src"))
        resp = client.get(f"{BASE}/sources/limit_src/runs")
        assert resp.status_code == 200

    def test_run_history_limit_1(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("lim1_src"))
        resp = client.get(f"{BASE}/sources/lim1_src/runs?limit=1")
        assert resp.status_code == 200

    def test_run_history_limit_200(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("lim200_src"))
        resp = client.get(f"{BASE}/sources/lim200_src/runs?limit=200")
        assert resp.status_code == 200

    def test_run_history_limit_201_rejected(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("lim_bad"))
        resp = client.get(f"{BASE}/sources/lim_bad/runs?limit=201")
        assert resp.status_code == 422

    def test_run_history_limit_overflow_rejected(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("overflow_src"))
        resp = client.get(f"{BASE}/sources/overflow_src/runs?limit=99999")
        assert resp.status_code == 422


class TestDeadLetters:
    def test_dead_letters_404_for_nonexistent(self, client):
        resp = client.get(f"{BASE}/sources/no_src/dead-letters")
        assert resp.status_code == 404

    def test_dead_letters_empty_when_audit_returns_nothing(self, client, mock_audit):
        mock_audit.get_dead_letter_count.return_value = 0
        mock_audit.get_dead_letter_records.return_value = []
        client.post(f"{BASE}/sources", json=make_file_source("dl_empty"))
        resp = client.get(f"{BASE}/sources/dl_empty/dead-letters")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 0
        assert data["recent_records"] == []

    def test_dead_letters_with_data(self, client, mock_audit):
        mock_audit.get_dead_letter_count.return_value = 3
        mock_audit.get_dead_letter_records.return_value = [
            {"id": 1, "error": "null constraint"},
            {"id": 2, "error": "type mismatch"},
            {"id": 3, "error": "schema drift"},
        ]
        client.post(f"{BASE}/sources", json=make_file_source("dl_data"))
        resp = client.get(f"{BASE}/sources/dl_data/dead-letters")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 3
        assert len(data["recent_records"]) == 3

    def test_dead_letters_limit_100(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("dl_lim"))
        resp = client.get(f"{BASE}/sources/dl_lim/dead-letters?limit=100")
        assert resp.status_code == 200

    def test_dead_letters_limit_101_rejected(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("dl_bad"))
        resp = client.get(f"{BASE}/sources/dl_bad/dead-letters?limit=101")
        assert resp.status_code == 422


class TestDashboardStats:
    def test_stats_no_sources(self, client):
        resp = client.get(f"{BASE}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sources"] == 0
        assert data["enabled_sources"] == 0
        assert data["disabled_sources"] == 0
        assert data["sources_by_type"] == {}
        assert data["recent_runs"] == 0

    def test_stats_counts(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("s1"))
        client.post(f"{BASE}/sources", json=make_file_source("s2", enabled=False))
        client.post(f"{BASE}/sources", json=make_jdbc_source("s3"))

        resp = client.get(f"{BASE}/stats")
        data = resp.json()
        assert data["total_sources"] == 3
        assert data["enabled_sources"] == 2
        assert data["disabled_sources"] == 1

    def test_stats_by_type(self, client):
        client.post(f"{BASE}/sources", json=make_file_source("f1"))
        client.post(f"{BASE}/sources", json=make_file_source("f2"))
        client.post(f"{BASE}/sources", json=make_jdbc_source("j1"))

        resp = client.get(f"{BASE}/stats")
        by_type = resp.json()["sources_by_type"]
        assert by_type.get("file", 0) == 2
        assert by_type.get("jdbc", 0) == 1

    def test_stats_required_fields(self, client):
        resp = client.get(f"{BASE}/stats")
        data = resp.json()
        for field in ["total_sources", "enabled_sources", "disabled_sources",
                      "sources_by_type", "recent_runs", "recent_failures"]:
            assert field in data, f"Missing field: {field}"


def make_jdbc_source(name="jdbc_source", **overrides):
    base = {
        "name": name,
        "source_type": "jdbc",
        "target": {"catalog": "dev", "schema": "bronze", "table": name},
        "extract": {"table": "raw_orders"},
    }
    base.update(overrides)
    return base
