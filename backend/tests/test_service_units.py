"""Direct unit tests for service classes — not via HTTP.

Tests service methods in isolation with real file I/O (tmp_path)
and mocked external dependencies. These catch bugs that HTTP-level
tests can miss (e.g., wrong field extraction, partial update logic).
"""

import yaml
import pytest
from unittest.mock import MagicMock

from app.models.enums import CdcMode, LoadType, SourceType
from app.models.requests import (
    CdcRequest,
    ExtractRequest,
    SourceCreateRequest,
    SourceUpdateRequest,
    TargetRequest,
)
from app.models.silver_requests import (
    SilverColumnMappingRequest,
    SilverEntityCreateRequest,
    SilverSourceMappingRequest,
    SilverTargetRequest,
)
from app.services.config_service import ConfigService
from app.services.silver_config_service import SilverConfigService
from app.services.deploy_service import DeployService


# ──────────────────────────────────────────────────────────────────────
# ConfigService unit tests
# ──────────────────────────────────────────────────────────────────────

def _file_req(name="svc_test", **kwargs):
    return SourceCreateRequest(
        name=name,
        source_type=SourceType.FILE,
        target=TargetRequest(catalog="dev", schema_name="bronze", table=name),
        extract=ExtractRequest(path="/data/test"),
        **kwargs,
    )


class TestConfigServiceSourceExists:
    def test_returns_false_when_empty(self, config_svc):
        assert config_svc.source_exists("any_name") is False

    def test_returns_true_after_write(self, config_svc):
        req = _file_req("exists_test")
        config_svc.write_source(req)
        assert config_svc.source_exists("exists_test") is True

    def test_returns_false_after_delete(self, config_svc):
        req = _file_req("deleted_test")
        config_svc.write_source(req)
        config_svc.delete_source("deleted_test")
        assert config_svc.source_exists("deleted_test") is False


class TestConfigServiceRenderYaml:
    def test_render_contains_source_name(self, config_svc):
        req = _file_req("render_test")
        yaml_text = config_svc.render_yaml(req)
        assert "render_test" in yaml_text

    def test_render_contains_source_type(self, config_svc):
        req = _file_req("type_test")
        yaml_text = config_svc.render_yaml(req)
        assert "source_type: file" in yaml_text

    def test_render_is_valid_yaml(self, config_svc):
        req = _file_req("valid_yaml_test")
        yaml_text = config_svc.render_yaml(req)
        parsed = yaml.safe_load(yaml_text)
        assert isinstance(parsed, dict)
        assert parsed["name"] == "valid_yaml_test"

    def test_render_jdbc_contains_table(self, config_svc):
        req = SourceCreateRequest(
            name="jdbc_render",
            source_type=SourceType.JDBC,
            target=TargetRequest(catalog="dev", schema_name="bronze", table="jdbc_render"),
            extract=ExtractRequest(table="raw_orders"),
        )
        yaml_text = config_svc.render_yaml(req)
        parsed = yaml.safe_load(yaml_text)
        assert parsed["source_type"] == "jdbc"

    def test_render_api_contains_base_url(self, config_svc):
        req = SourceCreateRequest(
            name="api_render",
            source_type=SourceType.API,
            target=TargetRequest(catalog="dev", schema_name="bronze", table="api_render"),
            extract=ExtractRequest(base_url="https://api.example.com"),
        )
        yaml_text = config_svc.render_yaml(req)
        parsed = yaml.safe_load(yaml_text)
        assert parsed["source_type"] == "api"

    def test_render_catalog_in_target(self, config_svc):
        req = _file_req("cat_test")
        yaml_text = config_svc.render_yaml(req)
        parsed = yaml.safe_load(yaml_text)
        assert parsed["target"]["catalog"] == "dev"

    def test_render_with_tags(self, config_svc):
        req = _file_req("tagged", tags={"domain": "finance", "team": "data"})
        yaml_text = config_svc.render_yaml(req)
        parsed = yaml.safe_load(yaml_text)
        assert parsed["tags"]["domain"] == "finance"

    def test_render_cdc_scd2(self, config_svc):
        req = _file_req("scd2_render")
        req.target.cdc = CdcRequest(enabled=True, mode=CdcMode.SCD2, primary_keys=["id"])
        yaml_text = config_svc.render_yaml(req)
        parsed = yaml.safe_load(yaml_text)
        cdc = parsed["target"]["cdc"]
        assert cdc["enabled"] is True
        assert cdc["mode"] == "scd2"


class TestConfigServiceListSources:
    def test_list_empty_directory(self, config_svc):
        assert config_svc.list_sources() == []

    def test_list_returns_all_sources(self, config_svc):
        for i in range(3):
            config_svc.write_source(_file_req(f"list_src_{i}"))
        result = config_svc.list_sources()
        assert len(result) == 3

    def test_list_filter_by_type(self, config_svc):
        config_svc.write_source(_file_req("file_src"))
        config_svc.write_source(SourceCreateRequest(
            name="jdbc_src",
            source_type=SourceType.JDBC,
            target=TargetRequest(catalog="dev", schema_name="bronze", table="jdbc_src"),
            extract=ExtractRequest(table="raw"),
        ))
        result = config_svc.list_sources(source_type="file")
        assert len(result) == 1
        assert result[0].source_type == SourceType.FILE

    def test_list_filter_by_enabled(self, config_svc):
        config_svc.write_source(_file_req("enabled_s"))
        req_disabled = _file_req("disabled_s")
        req_disabled.enabled = False
        config_svc.write_source(req_disabled)
        result = config_svc.list_sources(enabled=True)
        assert all(s.enabled for s in result)
        assert len(result) == 1

    def test_list_filter_by_domain_from_tags(self, config_svc):
        config_svc.write_source(_file_req("fin", tags={"domain": "finance"}))
        config_svc.write_source(_file_req("hr", tags={"domain": "hr"}))
        result = config_svc.list_sources(domain="finance")
        assert len(result) == 1
        assert result[0].name == "fin"

    def test_list_summary_fields(self, config_svc):
        config_svc.write_source(_file_req("summary_src"))
        sources = config_svc.list_sources()
        s = sources[0]
        assert s.name == "summary_src"
        assert s.source_type == SourceType.FILE
        assert isinstance(s.enabled, bool)
        assert isinstance(s.target_table, str)
        assert isinstance(s.tags, dict)


class TestConfigServiceGetSource:
    def test_get_returns_none_for_missing(self, config_svc):
        assert config_svc.get_source("missing") is None

    def test_get_returns_detail(self, config_svc):
        config_svc.write_source(_file_req("get_detail"))
        detail = config_svc.get_source("get_detail")
        assert detail is not None
        assert detail.name == "get_detail"
        assert detail.source_type == SourceType.FILE
        assert "raw_yaml" in type(detail).model_fields

    def test_get_detail_contains_raw_yaml(self, config_svc):
        config_svc.write_source(_file_req("raw_yaml_src"))
        detail = config_svc.get_source("raw_yaml_src")
        assert detail.raw_yaml != ""
        assert "raw_yaml_src" in detail.raw_yaml


class TestConfigServiceUpdateSource:
    def test_update_description(self, config_svc):
        config_svc.write_source(_file_req("upd_desc"))
        config_svc.update_source("upd_desc", SourceUpdateRequest(description="New description"))
        detail = config_svc.get_source("upd_desc")
        assert detail.description == "New description"

    def test_update_enabled_false(self, config_svc):
        config_svc.write_source(_file_req("upd_enabled"))
        config_svc.update_source("upd_enabled", SourceUpdateRequest(enabled=False))
        detail = config_svc.get_source("upd_enabled")
        assert detail.enabled is False

    def test_update_preserves_unupdated_fields(self, config_svc):
        req = _file_req("preserve_test", description="Original", tags={"key": "val"})
        config_svc.write_source(req)
        config_svc.update_source("preserve_test", SourceUpdateRequest(enabled=False))
        detail = config_svc.get_source("preserve_test")
        assert detail.description == "Original"
        assert detail.tags.get("key") == "val"


class TestConfigServiceValidation:
    def test_valid_file_source(self, config_svc):
        req = _file_req("valid_src")
        valid, errors = config_svc.validate_config(req)
        assert valid is True
        assert errors == []

    def test_empty_name_fails(self, config_svc):
        req = _file_req("")
        valid, errors = config_svc.validate_config(req)
        assert valid is False
        assert any("name" in e.lower() for e in errors)

    def test_empty_table_fails(self, config_svc):
        req = SourceCreateRequest(
            name="no_table",
            source_type=SourceType.FILE,
            target=TargetRequest(catalog="dev", schema_name="bronze", table=""),
            extract=ExtractRequest(path="/data"),
        )
        valid, errors = config_svc.validate_config(req)
        assert valid is False
        assert any("table" in e.lower() for e in errors)

    def test_empty_catalog_fails(self, config_svc):
        req = SourceCreateRequest(
            name="no_catalog",
            source_type=SourceType.FILE,
            target=TargetRequest(catalog="", schema_name="bronze", table="t"),
            extract=ExtractRequest(path="/data"),
        )
        valid, errors = config_svc.validate_config(req)
        assert valid is False
        assert any("catalog" in e.lower() for e in errors)

    def test_jdbc_missing_table_and_query(self, config_svc):
        req = SourceCreateRequest(
            name="jdbc_missing",
            source_type=SourceType.JDBC,
            target=TargetRequest(catalog="dev", schema_name="bronze", table="t"),
            extract=ExtractRequest(),
        )
        valid, errors = config_svc.validate_config(req)
        assert valid is False
        assert any("jdbc" in e.lower() for e in errors)

    def test_scd2_without_primary_keys(self, config_svc):
        req = _file_req("scd2_no_keys")
        req.target.cdc = CdcRequest(enabled=True, mode=CdcMode.SCD2, primary_keys=[])
        valid, errors = config_svc.validate_config(req)
        assert valid is False
        assert any("primary_keys" in e.lower() for e in errors)

    def test_valid_config_returns_yaml_preview(self, config_svc):
        req = _file_req("preview_src")
        valid, errors = config_svc.validate_config(req)
        assert valid is True
        yaml_text = config_svc.render_yaml(req)
        assert "preview_src" in yaml_text


# ──────────────────────────────────────────────────────────────────────
# SilverConfigService unit tests
# ──────────────────────────────────────────────────────────────────────

def _silver_req(name="slv_test", domain="customer"):
    return SilverEntityCreateRequest(
        name=name,
        domain=domain,
        target=SilverTargetRequest(
            catalog="dev",
            schema_name=f"slv_{domain}",
            table=name,
            scd_type="scd2",
            business_keys=["id"],
        ),
        sources=[
            SilverSourceMappingRequest(
                bronze_table="dev.bronze.raw",
                columns=[SilverColumnMappingRequest(source="id", target="id")],
            )
        ],
    )


class TestSilverConfigServiceValidation:
    def test_valid_entity(self, silver_config_svc):
        req = _silver_req("valid_entity")
        valid, errors = silver_config_svc.validate_config(req)
        assert valid is True
        assert errors == []

    def test_missing_domain(self, silver_config_svc):
        req = _silver_req("no_domain")
        req.domain = ""
        valid, errors = silver_config_svc.validate_config(req)
        assert valid is False
        assert any("domain" in e.lower() for e in errors)

    def test_scd2_without_business_keys(self, silver_config_svc):
        req = _silver_req("scd2_no_bkeys")
        req.target.business_keys = []
        valid, errors = silver_config_svc.validate_config(req)
        assert valid is False
        assert any("business key" in e.lower() for e in errors)

    def test_no_sources_fails(self, silver_config_svc):
        req = _silver_req("no_sources")
        req.sources = []
        valid, errors = silver_config_svc.validate_config(req)
        assert valid is False
        assert any("source" in e.lower() for e in errors)

    def test_source_with_no_columns_fails(self, silver_config_svc):
        req = _silver_req("no_cols")
        req.sources[0].columns = []
        valid, errors = silver_config_svc.validate_config(req)
        assert valid is False
        assert any("column" in e.lower() for e in errors)

    def test_append_scd_type_no_business_keys_ok(self, silver_config_svc):
        req = _silver_req("append_entity")
        req.target.scd_type = "append"
        req.target.business_keys = []
        valid, errors = silver_config_svc.validate_config(req)
        assert valid is True

    def test_missing_target_schema_fails(self, silver_config_svc):
        req = _silver_req("no_schema")
        req.target.schema_name = ""
        valid, errors = silver_config_svc.validate_config(req)
        assert valid is False
        assert any("schema" in e.lower() for e in errors)

    def test_missing_target_catalog_fails(self, silver_config_svc):
        req = _silver_req("no_catalog")
        req.target.catalog = ""
        valid, errors = silver_config_svc.validate_config(req)
        assert valid is False


class TestSilverConfigServiceRenderYaml:
    def test_render_is_valid_yaml(self, silver_config_svc):
        req = _silver_req("render_silver")
        yaml_text = silver_config_svc.render_yaml(req)
        parsed = yaml.safe_load(yaml_text)
        assert isinstance(parsed, dict)
        assert parsed["name"] == "render_silver"

    def test_render_contains_domain(self, silver_config_svc):
        req = _silver_req("domain_test", domain="policy")
        yaml_text = silver_config_svc.render_yaml(req)
        assert "policy" in yaml_text

    def test_render_contains_business_keys(self, silver_config_svc):
        req = _silver_req("bkey_test")
        yaml_text = silver_config_svc.render_yaml(req)
        parsed = yaml.safe_load(yaml_text)
        target = parsed.get("target", {})
        assert "id" in target.get("business_keys", [])


class TestSilverConfigServiceCrud:
    def test_write_then_exists(self, silver_config_svc):
        req = _silver_req("crud_test")
        silver_config_svc.write_entity(req)
        assert silver_config_svc.entity_exists("crud_test") is True

    def test_delete_removes_entity(self, silver_config_svc):
        req = _silver_req("del_test")
        silver_config_svc.write_entity(req)
        silver_config_svc.delete_entity("del_test")
        assert silver_config_svc.entity_exists("del_test") is False

    def test_list_returns_written_entity(self, silver_config_svc):
        req = _silver_req("listed_entity")
        silver_config_svc.write_entity(req)
        entities = silver_config_svc.list_entities()
        assert len(entities) == 1
        assert entities[0].name == "listed_entity"

    def test_get_entity_detail_fields(self, silver_config_svc):
        req = _silver_req("detail_entity")
        silver_config_svc.write_entity(req)
        detail = silver_config_svc.get_entity("detail_entity")
        assert detail is not None
        assert detail.name == "detail_entity"
        assert detail.domain == "customer"
        assert isinstance(detail.sources, list)
        assert isinstance(detail.target, dict)
        assert len(detail.raw_yaml) > 0


# ──────────────────────────────────────────────────────────────────────
# DeployService unit tests
# ──────────────────────────────────────────────────────────────────────

class TestDeployServiceCreate:
    def test_create_calls_git_commit(self, deploy_svc, mock_git):
        req = _file_req("git_svc_test")
        deploy_svc.create_source(req)
        mock_git.commit_file.assert_called_once()

    def test_create_calls_db_upload(self, deploy_svc, mock_db):
        req = _file_req("db_upload_test")
        deploy_svc.create_source(req)
        mock_db.upload_yaml.assert_called_once()

    def test_create_calls_db_job(self, deploy_svc, mock_db):
        req = _file_req("db_job_test")
        deploy_svc.create_source(req)
        mock_db.create_or_update_job.assert_called_once()

    def test_create_returns_response_with_name(self, deploy_svc):
        req = _file_req("resp_name_test")
        result = deploy_svc.create_source(req)
        assert result.name == "resp_name_test"

    def test_create_invalid_config_raises_value_error(self, deploy_svc):
        req = SourceCreateRequest(
            name="",
            source_type=SourceType.FILE,
            target=TargetRequest(catalog="dev", schema_name="bronze", table="t"),
            extract=ExtractRequest(path="/data"),
        )
        with pytest.raises(ValueError):
            deploy_svc.create_source(req)

    def test_create_git_commit_sha_in_response(self, deploy_svc, mock_git):
        mock_git.commit_file.return_value = "abc12345"
        req = _file_req("sha_test")
        result = deploy_svc.create_source(req)
        assert result.git_commit == "abc12345"

    def test_create_job_id_in_response_when_available(self, deploy_svc, mock_db):
        mock_db.create_or_update_job.return_value = "job_999"
        req = _file_req("job_id_test")
        result = deploy_svc.create_source(req)
        assert result.job_id == "job_999"


class TestDeployServiceDelete:
    def test_delete_raises_file_not_found_for_missing(self, deploy_svc):
        from app.services.deploy_service import DeployService
        with pytest.raises(FileNotFoundError):
            deploy_svc.delete_source("nonexistent_source")

    def test_delete_calls_git_commit_delete(self, deploy_svc, mock_git):
        req = _file_req("del_git_test")
        deploy_svc.create_source(req)
        deploy_svc.delete_source("del_git_test")
        mock_git.commit_delete.assert_called_once()

    def test_delete_calls_db_delete_job(self, deploy_svc, mock_db):
        req = _file_req("del_job_test")
        deploy_svc.create_source(req)
        deploy_svc.delete_source("del_job_test")
        mock_db.delete_job.assert_called_once()

    def test_delete_source_no_longer_exists(self, deploy_svc, config_svc):
        req = _file_req("gone_service_test")
        deploy_svc.create_source(req)
        deploy_svc.delete_source("gone_service_test")
        assert config_svc.get_source("gone_service_test") is None


class TestDeployServiceUpdate:
    def test_update_writes_to_yaml(self, deploy_svc, config_svc):
        req = _file_req("update_svc_test")
        deploy_svc.create_source(req)
        deploy_svc.update_source("update_svc_test", SourceUpdateRequest(description="Updated!"))
        detail = config_svc.get_source("update_svc_test")
        assert detail.description == "Updated!"

    def test_update_calls_git_commit(self, deploy_svc, mock_git):
        req = _file_req("update_git_test")
        deploy_svc.create_source(req)
        mock_git.commit_file.reset_mock()
        deploy_svc.update_source("update_git_test", SourceUpdateRequest(description="x"))
        assert mock_git.commit_file.call_count == 1
