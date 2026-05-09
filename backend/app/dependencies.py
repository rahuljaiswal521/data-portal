"""Dependency injection for FastAPI.

The Databricks-touching services (DatabricksService and everything that
depends on it) are scoped per-tenant: each request looks up the tenant's
own host/token/warehouse_id from the tenants table. If a tenant has not
configured credentials, ``get_databricks_service`` returns an *unavailable*
instance — routes that genuinely need Databricks should call
``require_databricks_service`` instead, which raises HTTP 412.

A small in-process cache reuses ``DatabricksService`` instances per tenant
to avoid rebuilding the SDK ``WorkspaceClient`` on every request.
"""

import time
from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException

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
def get_tenant_service() -> TenantService:
    return TenantService()


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


# ── Auth dependency import ────────────────────────────────────────────────────
# Imported AFTER ``get_tenant_service`` is defined so that
# ``app.api.common.auth`` (which imports ``get_tenant_service`` from us) does
# not hit a partially-initialised symbol during its own import.

from app.api.common.auth import get_current_tenant  # noqa: E402


# ── Per-tenant Databricks cache ──────────────────────────────────────────────

# Cache key: (tenant_id, host, token_hash, warehouse_id) — token_hash so we
# rebuild the WorkspaceClient when credentials are rotated.
# Value: (DatabricksService, created_at_unix)
_DATABRICKS_CACHE: dict[tuple, tuple[DatabricksService, float]] = {}
_DATABRICKS_CACHE_TTL_SECONDS = 300  # 5 minutes


def _get_or_build_databricks_service(
    tenant_id: str,
    creds: Optional[dict],
) -> DatabricksService:
    """Return a cached DatabricksService for the tenant, or build a new one."""
    if creds is None:
        # Unavailable instance — pass None for everything so available == False.
        return DatabricksService(host=None, token=None, warehouse_id=None)

    key = (
        tenant_id,
        creds["host"],
        # Hash the token rather than caching the literal in the dict key to
        # reduce the risk of accidentally surfacing it via ``repr``.
        hash(creds["token"]),
        creds["warehouse_id"],
    )
    now = time.time()
    cached = _DATABRICKS_CACHE.get(key)
    if cached and now - cached[1] < _DATABRICKS_CACHE_TTL_SECONDS:
        return cached[0]

    svc = DatabricksService(
        host=creds["host"],
        token=creds["token"],
        warehouse_id=creds["warehouse_id"],
    )
    _DATABRICKS_CACHE[key] = (svc, now)
    # Best-effort eviction: drop oldest entries when the cache grows large.
    if len(_DATABRICKS_CACHE) > 50:
        oldest = min(_DATABRICKS_CACHE.items(), key=lambda kv: kv[1][1])
        _DATABRICKS_CACHE.pop(oldest[0], None)
    return svc


def get_databricks_service(
    tenant_id: str = Depends(get_current_tenant),
    tenant_svc: TenantService = Depends(get_tenant_service),
) -> DatabricksService:
    """Return a Databricks service bound to the current tenant's credentials.

    Returns an *unavailable* instance (``available == False``) when the tenant
    has not configured credentials. Use ``require_databricks_service`` to
    enforce a 412 Precondition Failed instead.
    """
    creds = tenant_svc.get_databricks_credentials(tenant_id)
    return _get_or_build_databricks_service(tenant_id, creds)


def require_databricks_service(
    db: DatabricksService = Depends(get_databricks_service),
) -> DatabricksService:
    """Like ``get_databricks_service``, but raises HTTP 412 when not configured.

    Use this for endpoints that genuinely need Databricks (deploy, trigger,
    run history, etc.) so the frontend can intercept and redirect to Settings.
    """
    if not db.available:
        raise HTTPException(
            status_code=412,
            detail="Databricks credentials not configured. Visit Settings to add them.",
        )
    return db


# ── Per-tenant downstream services ───────────────────────────────────────────
# These were previously @lru_cache singletons. They now build per-request so
# they pick up the right tenant's DatabricksService.


def get_audit_service(
    db: DatabricksService = Depends(get_databricks_service),
) -> AuditService:
    return AuditService(db)


def get_deploy_service(
    cfg: ConfigService = Depends(get_config_service),
    git: GitService = Depends(get_git_service),
    db: DatabricksService = Depends(get_databricks_service),
) -> DeployService:
    return DeployService(cfg, git, db)


# Silver services
@lru_cache
def get_silver_config_service() -> SilverConfigService:
    return SilverConfigService()


def get_silver_deploy_service(
    cfg: SilverConfigService = Depends(get_silver_config_service),
    git: GitService = Depends(get_git_service),
    db: DatabricksService = Depends(get_databricks_service),
) -> SilverDeployService:
    return SilverDeployService(cfg, git, db)


def get_silver_modeling_service(
    db: DatabricksService = Depends(get_databricks_service),
    tenant_svc: TenantService = Depends(get_tenant_service),
) -> SilverModelingService:
    return SilverModelingService(db, tenant_svc)


def get_testing_service(
    cfg: ConfigService = Depends(get_config_service),
    db: DatabricksService = Depends(get_databricks_service),
) -> TestingService:
    return TestingService(cfg, db)


def get_tc_generator_service(
    cfg: ConfigService = Depends(get_config_service),
    testing: TestingService = Depends(get_testing_service),
    tenant_svc: TenantService = Depends(get_tenant_service),
) -> TcGeneratorService:
    return TcGeneratorService(cfg, testing, tenant_svc)


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


def get_gold_readiness_service(
    bronze_cfg: ConfigService = Depends(get_config_service),
    silver_cfg: SilverConfigService = Depends(get_silver_config_service),
    db: DatabricksService = Depends(get_databricks_service),
) -> GoldReadinessService:
    return GoldReadinessService(
        bronze_config_service=bronze_cfg,
        silver_config_service=silver_cfg,
        databricks_service=db,
    )


def get_rag_service(
    embedding: EmbeddingService = Depends(get_embedding_service),
    cfg: ConfigService = Depends(get_config_service),
    audit: AuditService = Depends(get_audit_service),
    tenant_svc: TenantService = Depends(get_tenant_service),
    deploy: DeployService = Depends(get_deploy_service),
    silver_cfg: SilverConfigService = Depends(get_silver_config_service),
    silver_deploy: SilverDeployService = Depends(get_silver_deploy_service),
) -> RAGService:
    return RAGService(
        embedding,
        cfg,
        audit,
        tenant_svc,
        deploy,
        silver_cfg,
        silver_deploy,
    )
