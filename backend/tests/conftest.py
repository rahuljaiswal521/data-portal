"""
Shared pytest fixtures and configuration for the portal backend test suite.

Strategy:
- Mock bronze_framework / silver_framework (not installed as packages)
- Use real ConfigService + SilverConfigService with tmp_path isolation
- Mock GitService and DatabricksService (external I/O)
- Mock RAGService and EmbeddingService (Anthropic + ChromaDB)
- Use real TenantService with a tmp SQLite database
- Inject everything via FastAPI dependency_overrides (bypasses lru_cache)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock


# ── Stub loader classes — must be real classes for __new__() to work ──
class _BronzeConfigLoader:
    """Stub that accepts any data without validation."""
    def _parse_source(self, data):
        return data


class _SilverConfigLoader:
    """Stub that accepts any data without validation."""
    def _parse_entity(self, data):
        return data


# ── Pre-import: mock framework packages before any app code is loaded ──
_bronze_loader_mod = MagicMock()
_bronze_loader_mod.ConfigLoader = _BronzeConfigLoader
_silver_loader_mod = MagicMock()
_silver_loader_mod.ConfigLoader = _SilverConfigLoader

_bronze_mod = MagicMock()
_bronze_mod.config = MagicMock()
_bronze_mod.config.loader = _bronze_loader_mod

_silver_mod = MagicMock()
_silver_mod.config = MagicMock()
_silver_mod.config.loader = _silver_loader_mod

sys.modules.setdefault("bronze_framework", _bronze_mod)
sys.modules.setdefault("bronze_framework.config", _bronze_mod.config)
sys.modules.setdefault("bronze_framework.config.loader", _bronze_loader_mod)
sys.modules.setdefault("silver_framework", _silver_mod)
sys.modules.setdefault("silver_framework.config", _silver_mod.config)
sys.modules.setdefault("silver_framework.config.loader", _silver_loader_mod)

# ── Now safe to import app ─────────────────────────────────────────────
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.dependencies import (
    get_audit_service,
    get_config_service,
    get_databricks_service,
    get_deploy_service,
    get_embedding_service,
    get_git_service,
    get_rag_service,
    get_silver_config_service,
    get_silver_deploy_service,
    get_silver_modeling_service,
    get_tenant_service,
)
from app.main import app
from app.services.audit_service import AuditService
from app.services.config_service import ConfigService
from app.services.databricks_service import DatabricksService
from app.services.deploy_service import DeployService
from app.services.embedding_service import EmbeddingService
from app.services.git_service import GitService
from app.services.rag_service import RAGService
from app.services.silver_config_service import SilverConfigService
from app.services.silver_deploy_service import SilverDeployService
from app.services.silver_modeling_service import SilverModelingService
from app.services.tenant_service import TenantService


# ── Settings isolation ─────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolate_settings(tmp_path, monkeypatch):
    """Redirect all file-system paths to a per-test temp directory."""
    bronze_conf = tmp_path / "bronze_conf"
    silver_conf = tmp_path / "silver_conf"
    (bronze_conf / "sources").mkdir(parents=True)
    (silver_conf / "entities").mkdir(parents=True)

    monkeypatch.setattr(settings, "conf_dir", str(bronze_conf))
    monkeypatch.setattr(settings, "silver_conf_dir", str(silver_conf))
    monkeypatch.setattr(settings, "chromadb_persist_dir", str(tmp_path / "chromadb"))
    monkeypatch.setattr(settings, "tenant_db_path", str(tmp_path / "tenants.db"))
    monkeypatch.setattr(settings, "git_enabled", False)
    monkeypatch.setattr(settings, "rag_require_auth", False)


# ── Mock external services ─────────────────────────────────────────────

@pytest.fixture
def mock_git():
    mock = MagicMock(spec=GitService)
    mock.available = False
    mock.commit_file.return_value = "deadbeef"
    mock.commit_delete.return_value = None
    return mock


@pytest.fixture
def mock_db():
    mock = MagicMock(spec=DatabricksService)
    mock.available = False
    mock.upload_yaml.return_value = None
    mock.create_or_update_job.return_value = None
    mock.trigger_job.return_value = None
    mock.delete_job.return_value = None
    mock.query_sql.return_value = []
    return mock


@pytest.fixture
def mock_audit():
    mock = MagicMock(spec=AuditService)
    mock.get_run_history.return_value = []
    mock.get_dead_letter_count.return_value = 0
    mock.get_dead_letter_records.return_value = []
    mock.get_dashboard_stats.return_value = {"recent_runs": 0, "recent_failures": 0}
    return mock


@pytest.fixture
def mock_rag():
    mock = MagicMock(spec=RAGService)
    mock.answer.return_value = {
        "answer": "The framework uses Delta Lake for storage.",
        "query_type": "GENERAL",
        "sources_used": ["docs/overview.md"],
    }
    mock.build_index.return_value = {"shared_docs": 5, "source_configs": 2}
    return mock


@pytest.fixture
def mock_embedding():
    mock = MagicMock(spec=EmbeddingService)
    mock.get_index_status.return_value = {
        "shared_doc_chunks": 10,
        "tenant_source_chunks": 3,
    }
    return mock


@pytest.fixture
def mock_modeling():
    mock = MagicMock(spec=SilverModelingService)

    from app.models.silver_modeling import (
        EnterpriseModelResponse,
        SuggestModelResponse,
        TableProfileResponse,
    )

    mock.profile_table.return_value = TableProfileResponse(
        table="dev.bronze.orders", row_count=1000
    )
    mock.list_bronze_tables.return_value = [
        {"full_name": "dev.bronze.orders", "columns": []},
    ]
    mock.suggest_enterprise_model.return_value = EnterpriseModelResponse(
        overall_reasoning="Suggested 2 domains"
    )
    mock.suggest_model.return_value = SuggestModelResponse(
        name="orders", domain="finance", description="Order entity"
    )

    def _stream_gen(*args, **kwargs):
        yield "data: chunk1\n\n"
        yield "data: chunk2\n\n"

    mock.suggest_enterprise_model_stream.return_value = _stream_gen()
    return mock


# ── Real services backed by tmp_path ──────────────────────────────────

@pytest.fixture
def mock_tenant(isolate_settings):
    """Real TenantService using the tmp SQLite path."""
    return TenantService()


@pytest.fixture
def config_svc(isolate_settings):
    """Real ConfigService — reads/writes to tmp bronze_conf/sources."""
    return ConfigService()


@pytest.fixture
def silver_config_svc(isolate_settings):
    """Real SilverConfigService — reads/writes to tmp silver_conf/entities."""
    return SilverConfigService()


@pytest.fixture
def deploy_svc(config_svc, mock_git, mock_db):
    return DeployService(config_svc, mock_git, mock_db)


@pytest.fixture
def silver_deploy_svc(silver_config_svc, mock_git, mock_db):
    return SilverDeployService(silver_config_svc, mock_git, mock_db)


# ── Main TestClient fixture ────────────────────────────────────────────

@pytest.fixture
def client(
    config_svc,
    deploy_svc,
    mock_audit,
    mock_db,
    mock_git,
    mock_rag,
    mock_embedding,
    mock_tenant,
    mock_modeling,
    silver_config_svc,
    silver_deploy_svc,
):
    """TestClient with all external dependencies overridden."""
    app.dependency_overrides = {
        get_config_service: lambda: config_svc,
        get_deploy_service: lambda: deploy_svc,
        get_databricks_service: lambda: mock_db,
        get_git_service: lambda: mock_git,
        get_audit_service: lambda: mock_audit,
        get_rag_service: lambda: mock_rag,
        get_embedding_service: lambda: mock_embedding,
        get_tenant_service: lambda: mock_tenant,
        get_silver_config_service: lambda: silver_config_svc,
        get_silver_deploy_service: lambda: silver_deploy_svc,
        get_silver_modeling_service: lambda: mock_modeling,
    }
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Shared helpers ─────────────────────────────────────────────────────

def make_file_source(name="test_source", **overrides):
    """Build a minimal valid FILE source payload."""
    base = {
        "name": name,
        "source_type": "file",
        "target": {"catalog": "dev", "schema": "bronze", "table": name},
        "extract": {"path": "/data/test"},
    }
    base.update(overrides)
    return base


def make_jdbc_source(name="jdbc_source", **overrides):
    """Build a minimal valid JDBC source payload."""
    base = {
        "name": name,
        "source_type": "jdbc",
        "target": {"catalog": "dev", "schema": "bronze", "table": name},
        "extract": {"table": "raw_orders"},
    }
    base.update(overrides)
    return base


def make_silver_entity(name="test_entity", **overrides):
    """Build a minimal valid Silver entity payload."""
    base = {
        "name": name,
        "domain": "customer",
        "target": {
            "catalog": "dev",
            "schema": "slv_customer",
            "table": name,
            "scd_type": "scd2",
            "business_keys": ["customer_id"],
        },
        "sources": [
            {
                "bronze_table": "dev.bronze.customers",
                "columns": [
                    {"source": "customer_id", "target": "customer_id"},
                    {"source": "name", "target": "name"},
                ],
            }
        ],
    }
    base.update(overrides)
    return base
