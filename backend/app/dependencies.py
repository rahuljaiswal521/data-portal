"""Dependency injection for FastAPI."""

from functools import lru_cache

from app.services.audit_service import AuditService
from app.services.config_service import ConfigService
from app.services.databricks_service import DatabricksService
from app.services.deploy_service import DeployService
from app.services.embedding_service import EmbeddingService
from app.services.git_service import GitService
from app.services.rag_service import RAGService
from app.services.gold_config_service import GoldConfigService
from app.services.gold_ingest_service import GoldIngestService
from app.services.gold_readiness_service import GoldReadinessService
from app.services.silver_config_service import SilverConfigService
from app.services.silver_deploy_service import SilverDeployService
from app.services.silver_modeling_service import SilverModelingService
from app.services.tenant_service import TenantService
from app.services.tc_generator_service import TcGeneratorService
from app.services.testing_service import TestingService


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


# Silver services
@lru_cache
def get_silver_config_service() -> SilverConfigService:
    return SilverConfigService()


@lru_cache
def get_silver_deploy_service() -> SilverDeployService:
    return SilverDeployService(
        get_silver_config_service(),
        get_git_service(),
        get_databricks_service(),
    )


@lru_cache
def get_silver_modeling_service() -> SilverModelingService:
    return SilverModelingService(get_databricks_service(), get_tenant_service())


@lru_cache
def get_testing_service() -> TestingService:
    return TestingService(get_config_service(), get_databricks_service())


@lru_cache
def get_tc_generator_service() -> TcGeneratorService:
    return TcGeneratorService(
        get_config_service(), get_testing_service(), get_tenant_service()
    )


# Gold services
@lru_cache
def get_gold_config_service() -> GoldConfigService:
    from app.config import settings
    return GoldConfigService(settings.gold_marts_dir)


@lru_cache
def get_gold_ingest_service() -> GoldIngestService:
    from app.config import settings
    return GoldIngestService(
        gold_framework_src=settings.gold_framework_src_path,
        gold_config_service=get_gold_config_service(),
    )


@lru_cache
def get_gold_readiness_service() -> GoldReadinessService:
    return GoldReadinessService(
        bronze_config_service=get_config_service(),
        silver_config_service=get_silver_config_service(),
        databricks_service=get_databricks_service(),
    )


@lru_cache
def get_rag_service() -> RAGService:
    return RAGService(
        get_embedding_service(),
        get_config_service(),
        get_audit_service(),
        get_tenant_service(),
        get_deploy_service(),
        get_silver_config_service(),
        get_silver_deploy_service(),
    )
