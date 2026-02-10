"""Dependency injection for FastAPI."""

from functools import lru_cache

from app.services.audit_service import AuditService
from app.services.config_service import ConfigService
from app.services.databricks_service import DatabricksService
from app.services.deploy_service import DeployService
from app.services.git_service import GitService


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
