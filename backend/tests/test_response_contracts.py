"""Response contract tests — verify field names, types, and consistency.

These tests ensure:
1. Every response field has the correct Python type (not just "present")
2. Data written via POST can be read back identically via GET
3. List responses are consistent with individual GET responses
4. Enum values in responses match allowed values
5. No unexpected 'null' leakage where non-optional fields should always be set
"""

import pytest

from tests.conftest import make_file_source, make_jdbc_source, make_silver_entity

BRONZE = "/api/v1/bronze"
SILVER = "/api/v1/silver"


# ──────────────────────────────────────────────────────────────────────
# Bronze: Create/List/Get consistency
# ──────────────────────────────────────────────────────────────────────

class TestBronzeSourceListContract:
    def test_list_total_is_integer(self, client):
        resp = client.get(f"{BRONZE}/sources")
        data = resp.json()
        assert isinstance(data["total"], int)

    def test_list_sources_is_list(self, client):
        resp = client.get(f"{BRONZE}/sources")
        assert isinstance(resp.json()["sources"], list)

    def test_list_source_summary_types(self, client):
        client.post(f"{BRONZE}/sources", json=make_file_source("contract_list"))
        sources = client.get(f"{BRONZE}/sources").json()["sources"]
        assert len(sources) == 1
        s = sources[0]
        assert isinstance(s["name"], str)
        assert isinstance(s["source_type"], str)
        assert isinstance(s["description"], str)
        assert isinstance(s["enabled"], bool)
        assert isinstance(s["tags"], dict)
        assert isinstance(s["target_table"], str)
        assert isinstance(s["cdc_mode"], str)
        assert isinstance(s["load_type"], str)
        # schedule is optional — None or str
        assert s["schedule"] is None or isinstance(s["schedule"], str)

    def test_list_source_type_enum_values(self, client):
        valid_types = {"file", "jdbc", "api", "stream"}
        client.post(f"{BRONZE}/sources", json=make_file_source("enum_test"))
        sources = client.get(f"{BRONZE}/sources").json()["sources"]
        for s in sources:
            assert s["source_type"] in valid_types

    def test_list_cdc_mode_enum_values(self, client):
        valid_modes = {"scd2", "upsert", "append"}
        client.post(f"{BRONZE}/sources", json=make_file_source("cdc_enum"))
        sources = client.get(f"{BRONZE}/sources").json()["sources"]
        for s in sources:
            assert s["cdc_mode"] in valid_modes

    def test_list_load_type_enum_values(self, client):
        valid_loads = {"full", "incremental"}
        client.post(f"{BRONZE}/sources", json=make_file_source("lt_enum"))
        sources = client.get(f"{BRONZE}/sources").json()["sources"]
        for s in sources:
            assert s["load_type"] in valid_loads

    def test_list_total_matches_sources_length(self, client):
        for i in range(3):
            client.post(f"{BRONZE}/sources", json=make_file_source(f"match_src_{i}"))
        resp = client.get(f"{BRONZE}/sources").json()
        assert resp["total"] == len(resp["sources"])


class TestBronzeSourceDetailContract:
    def test_get_detail_field_types(self, client):
        client.post(f"{BRONZE}/sources", json=make_file_source("detail_contract"))
        data = client.get(f"{BRONZE}/sources/detail_contract").json()
        assert isinstance(data["name"], str)
        assert isinstance(data["source_type"], str)
        assert isinstance(data["description"], str)
        assert isinstance(data["enabled"], bool)
        assert isinstance(data["tags"], dict)
        assert isinstance(data["connection"], dict)
        assert isinstance(data["extract"], dict)
        assert isinstance(data["target"], dict)
        assert isinstance(data["raw_yaml"], str)
        assert len(data["raw_yaml"]) > 0

    def test_create_then_get_name_matches(self, client):
        payload = make_file_source("name_consistency")
        client.post(f"{BRONZE}/sources", json=payload)
        detail = client.get(f"{BRONZE}/sources/name_consistency").json()
        assert detail["name"] == "name_consistency"

    def test_create_then_get_description_matches(self, client):
        payload = make_file_source("desc_consistency", description="My test description")
        client.post(f"{BRONZE}/sources", json=payload)
        detail = client.get(f"{BRONZE}/sources/desc_consistency").json()
        assert detail["description"] == "My test description"

    def test_create_then_get_enabled_matches(self, client):
        payload = make_file_source("en_consistency", enabled=False)
        client.post(f"{BRONZE}/sources", json=payload)
        detail = client.get(f"{BRONZE}/sources/en_consistency").json()
        assert detail["enabled"] is False

    def test_create_then_get_tags_match(self, client):
        tags = {"env": "dev", "team": "data-eng"}
        payload = make_file_source("tags_consistency", tags=tags)
        client.post(f"{BRONZE}/sources", json=payload)
        detail = client.get(f"{BRONZE}/sources/tags_consistency").json()
        assert detail["tags"]["env"] == "dev"
        assert detail["tags"]["team"] == "data-eng"

    def test_detail_target_has_catalog(self, client):
        client.post(f"{BRONZE}/sources", json=make_file_source("cat_detail"))
        data = client.get(f"{BRONZE}/sources/cat_detail").json()
        assert data["target"].get("catalog") == "dev"

    def test_list_and_get_name_consistent(self, client):
        """Name in list summary == name in detail."""
        client.post(f"{BRONZE}/sources", json=make_file_source("list_get_consistent"))
        list_names = [s["name"] for s in client.get(f"{BRONZE}/sources").json()["sources"]]
        detail = client.get(f"{BRONZE}/sources/list_get_consistent").json()
        assert detail["name"] in list_names


class TestBronzeCreateResponseContract:
    def test_create_response_fields(self, client):
        resp = client.post(f"{BRONZE}/sources", json=make_file_source("create_resp"))
        assert resp.status_code == 201
        data = resp.json()
        assert isinstance(data["name"], str)
        assert isinstance(data["yaml_path"], str)
        assert isinstance(data["message"], str)
        # git_commit and job_id are Optional
        assert "git_commit" in data
        assert "job_id" in data

    def test_create_response_name_matches_request(self, client):
        resp = client.post(f"{BRONZE}/sources", json=make_file_source("create_match"))
        assert resp.json()["name"] == "create_match"

    def test_create_response_yaml_path_is_nonempty_string(self, client):
        resp = client.post(f"{BRONZE}/sources", json=make_file_source("path_test"))
        yaml_path = resp.json()["yaml_path"]
        assert isinstance(yaml_path, str)
        assert len(yaml_path) > 0
        assert yaml_path.endswith(".yaml")

    def test_create_response_message_contains_created(self, client):
        resp = client.post(f"{BRONZE}/sources", json=make_file_source("msg_test"))
        assert "created" in resp.json()["message"].lower()

    def test_delete_response_contract(self, client):
        client.post(f"{BRONZE}/sources", json=make_file_source("del_contract"))
        resp = client.delete(f"{BRONZE}/sources/del_contract")
        data = resp.json()
        assert isinstance(data["name"], str)
        assert isinstance(data["message"], str)
        assert data["name"] == "del_contract"


class TestBronzeMonitoringContracts:
    def test_run_history_response_types(self, client, mock_audit):
        mock_audit.get_run_history.return_value = [
            {
                "source_name": "rh_src",
                "environment": "dev",
                "status": "SUCCEEDED",
                "records_read": 100,
                "records_written": 98,
                "records_quarantined": 2,
                "error": None,
            }
        ]
        client.post(f"{BRONZE}/sources", json=make_file_source("rh_src"))
        data = client.get(f"{BRONZE}/sources/rh_src/runs").json()
        assert isinstance(data["source_name"], str)
        assert isinstance(data["runs"], list)
        assert isinstance(data["total"], int)
        run = data["runs"][0]
        assert isinstance(run["source_name"], str)
        assert isinstance(run["status"], str)
        assert isinstance(run["records_read"], int)
        assert isinstance(run["records_written"], int)
        assert isinstance(run["records_quarantined"], int)

    def test_dead_letter_response_types(self, client, mock_audit):
        mock_audit.get_dead_letter_count.return_value = 5
        mock_audit.get_dead_letter_records.return_value = [{"id": 1, "error": "test"}]
        client.post(f"{BRONZE}/sources", json=make_file_source("dl_src"))
        data = client.get(f"{BRONZE}/sources/dl_src/dead-letters").json()
        assert isinstance(data["source_name"], str)
        assert isinstance(data["total_count"], int)
        assert isinstance(data["recent_records"], list)

    def test_stats_response_types(self, client):
        client.post(f"{BRONZE}/sources", json=make_file_source("stats_c"))
        data = client.get(f"{BRONZE}/stats").json()
        assert isinstance(data["total_sources"], int)
        assert isinstance(data["enabled_sources"], int)
        assert isinstance(data["disabled_sources"], int)
        assert isinstance(data["sources_by_type"], dict)
        assert isinstance(data["recent_runs"], int)
        assert isinstance(data["recent_failures"], int)
        # enabled + disabled = total
        assert data["enabled_sources"] + data["disabled_sources"] == data["total_sources"]

    def test_stats_by_type_values_are_integers(self, client):
        client.post(f"{BRONZE}/sources", json=make_file_source("type_int_1"))
        client.post(f"{BRONZE}/sources", json=make_file_source("type_int_2"))
        by_type = client.get(f"{BRONZE}/stats").json()["sources_by_type"]
        for v in by_type.values():
            assert isinstance(v, int)


class TestBronzeValidationContract:
    def test_validation_response_fields(self, client):
        resp = client.post(f"{BRONZE}/sources/x/validate", json=make_file_source("val_c"))
        data = resp.json()
        assert isinstance(data["valid"], bool)
        assert isinstance(data["errors"], list)
        # yaml_preview is Optional[str]
        assert "yaml_preview" in data

    def test_validation_valid_has_nonempty_preview(self, client):
        resp = client.post(f"{BRONZE}/sources/x/validate", json=make_file_source("preview_c"))
        data = resp.json()
        assert data["valid"] is True
        assert isinstance(data["yaml_preview"], str)
        assert len(data["yaml_preview"]) > 10

    def test_validation_invalid_has_null_preview(self, client):
        payload = {
            "name": "bad_c",
            "source_type": "file",
            "target": {"catalog": "dev", "schema": "bronze", "table": "t"},
            "extract": {},  # missing path
        }
        resp = client.post(f"{BRONZE}/sources/x/validate", json=payload)
        data = resp.json()
        assert data["valid"] is False
        assert data["yaml_preview"] is None

    def test_validation_errors_are_strings(self, client):
        payload = {
            "name": "",
            "source_type": "file",
            "target": {"catalog": "", "schema": "bronze", "table": ""},
            "extract": {},
        }
        resp = client.post(f"{BRONZE}/sources/x/validate", json=payload)
        errors = resp.json()["errors"]
        assert len(errors) > 0
        for e in errors:
            assert isinstance(e, str)


# ──────────────────────────────────────────────────────────────────────
# Silver: response contracts
# ──────────────────────────────────────────────────────────────────────

class TestSilverEntityListContract:
    def test_list_response_types(self, client):
        resp = client.get(f"{SILVER}/entities")
        data = resp.json()
        assert isinstance(data["entities"], list)
        assert isinstance(data["total"], int)

    def test_list_entity_summary_types(self, client):
        client.post(f"{SILVER}/entities", json=make_silver_entity("slv_contract"))
        entities = client.get(f"{SILVER}/entities").json()["entities"]
        e = entities[0]
        assert isinstance(e["name"], str)
        assert isinstance(e["domain"], str)
        assert isinstance(e["description"], str)
        assert isinstance(e["enabled"], bool)
        assert isinstance(e["tags"], dict)
        assert isinstance(e["target_table"], str)
        assert isinstance(e["scd_type"], str)
        assert isinstance(e["business_keys"], list)
        assert isinstance(e["source_count"], int)
        assert isinstance(e["bronze_tables"], list)

    def test_silver_create_response_fields(self, client):
        resp = client.post(f"{SILVER}/entities", json=make_silver_entity("slv_resp"))
        assert resp.status_code == 201
        data = resp.json()
        assert isinstance(data["name"], str)
        assert isinstance(data["yaml_path"], str)
        assert isinstance(data["message"], str)
        assert data["name"] == "slv_resp"

    def test_silver_detail_fields(self, client):
        client.post(f"{SILVER}/entities", json=make_silver_entity("slv_detail"))
        data = client.get(f"{SILVER}/entities/slv_detail").json()
        assert isinstance(data["name"], str)
        assert isinstance(data["domain"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["target"], dict)
        assert isinstance(data["raw_yaml"], str)
        assert len(data["raw_yaml"]) > 0


class TestSilverStatsContract:
    def test_stats_types(self, client):
        data = client.get(f"{SILVER}/stats").json()
        assert isinstance(data["total_entities"], int)
        assert isinstance(data["enabled_entities"], int)
        assert isinstance(data["domains"], list)
        assert isinstance(data["entities_by_domain"], dict)
        assert isinstance(data["entities_by_scd_type"], dict)

    def test_stats_enabled_lte_total(self, client):
        client.post(f"{SILVER}/entities", json=make_silver_entity("s1"))
        e2 = make_silver_entity("s2")
        e2["enabled"] = False
        client.post(f"{SILVER}/entities", json=e2)
        data = client.get(f"{SILVER}/stats").json()
        assert data["enabled_entities"] <= data["total_entities"]


class TestSilverDiagramContract:
    def test_diagram_response_types(self, client):
        data = client.get(f"{SILVER}/diagram").json()
        assert isinstance(data["mermaid"], str)
        assert isinstance(data["entity_count"], int)
        assert isinstance(data["domains"], list)

    def test_diagram_starts_with_er_diagram(self, client):
        data = client.get(f"{SILVER}/diagram").json()
        assert data["mermaid"].startswith("erDiagram")

    def test_diagram_entity_count_matches_entities(self, client):
        client.post(f"{SILVER}/entities", json=make_silver_entity("diag_c1"))
        client.post(f"{SILVER}/entities", json=make_silver_entity("diag_c2"))
        data = client.get(f"{SILVER}/diagram").json()
        assert data["entity_count"] == 2


# ──────────────────────────────────────────────────────────────────────
# RAG: response contracts
# ──────────────────────────────────────────────────────────────────────

class TestRagResponseContracts:
    def test_chat_response_types(self, client):
        resp = client.post("/api/v1/rag/chat", json={"question": "Hello"})
        data = resp.json()
        assert isinstance(data["answer"], str)
        assert isinstance(data["query_type"], str)
        assert isinstance(data["sources_used"], list)
        assert isinstance(data["session_id"], str)
        assert len(data["session_id"]) > 0

    def test_chat_sources_used_contains_strings(self, client, mock_rag):
        mock_rag.answer.return_value = {
            "answer": "Test",
            "query_type": "DOCS",
            "sources_used": ["doc1.md", "doc2.md"],
        }
        resp = client.post("/api/v1/rag/chat", json={"question": "How?"})
        for src in resp.json()["sources_used"]:
            assert isinstance(src, str)

    def test_history_response_types(self, client):
        resp = client.get("/api/v1/rag/chat/history?session_id=test_session")
        data = resp.json()
        assert isinstance(data["session_id"], str)
        assert isinstance(data["messages"], list)

    def test_index_status_types(self, client):
        data = client.get("/api/v1/rag/index/status").json()
        assert isinstance(data["shared_doc_chunks"], int)
        assert isinstance(data["tenant_source_chunks"], int)
        assert data["shared_doc_chunks"] >= 0
        assert data["tenant_source_chunks"] >= 0

    def test_index_rebuild_types(self, client):
        data = client.post("/api/v1/rag/index/rebuild").json()
        assert isinstance(data["shared_docs_indexed"], int)
        assert isinstance(data["source_configs_indexed"], int)
        assert isinstance(data["message"], str)


# ──────────────────────────────────────────────────────────────────────
# Error response contracts
# ──────────────────────────────────────────────────────────────────────

class TestErrorResponseContracts:
    def test_404_has_detail_field(self, client):
        resp = client.get(f"{BRONZE}/sources/nonexistent")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)

    def test_409_has_detail_field(self, client):
        client.post(f"{BRONZE}/sources", json=make_file_source("conflict_src"))
        resp = client.post(f"{BRONZE}/sources", json=make_file_source("conflict_src"))
        assert resp.status_code == 409
        assert "detail" in resp.json()

    def test_422_has_detail_field(self, client):
        resp = client.post(f"{BRONZE}/sources", json={})
        assert resp.status_code == 422
        data = resp.json()
        assert "detail" in data

    def test_422_pydantic_has_structured_errors(self, client):
        resp = client.post(f"{BRONZE}/sources", json={})
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        # Pydantic 422 returns a list of error objects
        assert isinstance(detail, list)
        for err in detail:
            assert "msg" in err
            assert "type" in err

    def test_health_never_returns_404(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code != 404
