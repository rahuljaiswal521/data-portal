"""Dependency injection for FastAPI."""

from functools import lru_cache

from app.services.audit_service import AuditService
from app.services.config_service import ConfigService
from app.services.databricks_service import DatabricksService
from app.services.deploy_service import DeployService
from app.services.embedding_service import EmbeddingService
from app.services.git_service import GitService
from app.services.rag_service import RAGService
from app.services.tenant_service import TenantService


@lru_cache
def get_config_service() -> ConfigService:
    return ConfigService()


@lru_cache
def get_git_service() -> GitService:
    return GitService()


@lru_cache
def get_databricks_service() -> DatabricksService:
    return DatabricksService()


@lru_cache
def get_audit_service() -> AuditService:
    return AuditService(get_databricks_service())


@lru_cache
def get_deploy_service() -> DeployService:
    return DeployService(
        get_config_service(),
        get_git_service(),
        get_databricks_service(),
    )


@lru_cache
def get_tenant_service() -> TenantService:
    return TenantService()


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


@lru_cache
def get_rag_service() -> RAGService:
    return RAGService(
        get_embedding_service(),
        get_config_service(),
        get_audit_service(),
        get_tenant_service(),
    )
