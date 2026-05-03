"""API routes for AI-assisted Silver entity modeling."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.common.auth import get_current_tenant
from app.dependencies import get_silver_modeling_service
from app.models.silver_modeling import (
    EnterpriseModelRequest,
    EnterpriseModelResponse,
    ProfileTableRequest,
    SuggestModelRequest,
    SuggestModelResponse,
    TableProfileResponse,
)
from app.services.silver_modeling_service import SilverModelingService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/modeling/profile-table", response_model=TableProfileResponse)
def profile_table(
    req: ProfileTableRequest,
    service: SilverModelingService = Depends(get_silver_modeling_service),
) -> TableProfileResponse:
    """Profile a single Bronze table — returns columns, stats, sample data."""
    return service.profile_table(req.catalog, req.schema_name, req.table)


@router.get("/modeling/bronze-tables")
def list_bronze_tables(
    catalog: str = "dev",
    schema: str = "bronze",
    service: SilverModelingService = Depends(get_silver_modeling_service),
) -> list:
    """Discover available bronze tables from Databricks."""
    return service.list_bronze_tables(catalog, schema)


@router.post("/modeling/suggest-enterprise-model", response_model=EnterpriseModelResponse)
def suggest_enterprise_model(
    req: EnterpriseModelRequest,
    tenant_id: str = Depends(get_current_tenant),
    service: SilverModelingService = Depends(get_silver_modeling_service),
) -> EnterpriseModelResponse:
    """Analyze multiple bronze tables -> suggest full domain + entity structure.

    Uses the tenant's currently-selected model (Anthropic / OpenAI / Gemini).
    """
    return service.suggest_enterprise_model(req.tables, req.catalog, tenant_id=tenant_id)


@router.post("/modeling/suggest-enterprise-model/stream")
def suggest_enterprise_model_stream(
    req: EnterpriseModelRequest,
    tenant_id: str = Depends(get_current_tenant),
    service: SilverModelingService = Depends(get_silver_modeling_service),
) -> StreamingResponse:
    """Stream the enterprise model analysis as SSE chunks."""
    return StreamingResponse(
        service.suggest_enterprise_model_stream(req.tables, req.catalog, tenant_id=tenant_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/modeling/suggest-model", response_model=SuggestModelResponse)
def suggest_model(
    req: SuggestModelRequest,
    tenant_id: str = Depends(get_current_tenant),
    service: SilverModelingService = Depends(get_silver_modeling_service),
) -> SuggestModelResponse:
    """Profile all tables, then call the selected AI model to suggest a Silver entity model."""
    # Profile each table
    profiles = {}
    for tbl in req.tables:
        parts = tbl.full_table_name.split(".")
        if len(parts) != 3:
            return SuggestModelResponse(
                error=f"Invalid table name '{tbl.full_table_name}'. Expected format: catalog.schema.table",
            )
        catalog, schema, table = parts
        profiles[tbl.full_table_name] = service.profile_table(catalog, schema, table)

    # Build table dicts for the service
    tables = [
        {
            "full_table_name": tbl.full_table_name,
            "column_definitions": tbl.column_definitions,
        }
        for tbl in req.tables
    ]

    return service.suggest_model(
        tables=tables,
        profiles=profiles,
        domain_hint=req.domain_hint,
        entity_name_hint=req.entity_name_hint,
        tenant_id=tenant_id,
    )
