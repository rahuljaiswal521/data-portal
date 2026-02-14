"""Application settings loaded from environment variables."""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Paths
    framework_root: str = str(Path(__file__).resolve().parents[2].parent / "bronze_framework")
    conf_dir: str = ""  # derived from framework_root if empty

    # Databricks
    databricks_host: Optional[str] = None
    databricks_token: Optional[str] = None
    databricks_warehouse_id: Optional[str] = None
    databricks_workspace_path: str = "/Workspace/bronze_framework"
    databricks_cluster_policy_id: Optional[str] = None
    databricks_spark_version: str = "14.3.x-scala2.12"
    databricks_node_type_id: str = "Standard_DS3_v2"

    # Git
    git_enabled: bool = True
    git_auto_push: bool = False

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001", "http://allianzis:3000", "http://allianzis:3001"]

    # Environments
    default_environment: str = "dev"

    # RAG
    anthropic_api_key: Optional[str] = None
    chromadb_persist_dir: str = str(Path(__file__).resolve().parents[1] / "data" / "chromadb")
    rag_model: str = "claude-sonnet-4-5-20250929"
    rag_max_tokens: int = 1024
    rag_temperature: float = 0.3
    rag_require_auth: bool = False

    # Tenant
    tenant_db_path: str = str(Path(__file__).resolve().parents[1] / "data" / "tenants.db")

    model_config = {
        "env_file": str(Path(__file__).resolve().parents[1] / ".env"),
        "env_file_encoding": "utf-8",
    }

    @property
    def sources_dir(self) -> Path:
        base = Path(self.conf_dir) if self.conf_dir else Path(self.framework_root) / "conf"
        return base / "sources"

    @property
    def environments_dir(self) -> Path:
        base = Path(self.conf_dir) if self.conf_dir else Path(self.framework_root) / "conf"
        return base / "environments"

    @property
    def framework_src_path(self) -> Path:
        return Path(self.framework_root) / "src"


settings = Settings()
