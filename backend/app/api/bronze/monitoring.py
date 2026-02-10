"""Monitoring endpoints: run history, dead letters, dashboard stats."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_audit_service, get_config_service
from app.models.responses import (
    DashboardStats,
    DeadLetterResponse,
    RunHistoryResponse,
    RunRecord,
)
from app.services.audit_service import AuditService
from app.services.config_service import ConfigService

router = APIRouter()


@router.get("/sources/{name}/runs", response_model=RunHistoryResponse)
def get_run_history(
    name: str,
    limit: int = Query(default=50, le=200),
    config_svc: ConfigService = Depends(get_config_service),
    audit_svc: AuditService = Depends(get_audit_service),
):
    source = config_svc.get_source(name)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")

    catalog = source.target.get("catalog", "")
    if not catalog:
        return RunHistoryResponse(source_name=name, runs=[], total=0)

    rows = audit_svc.get_run_history(name, catalog, limit)
    runs = [
        RunRecord(
            source_name=row.get("source_name", name),
            environment=row.get("environment", ""),
            start_time=row.get("start_time"),
            end_time=row.get("end_time"),
            status=row.get("status", "UNKNOWN"),
            records_read=int(row.get("records_read", 0)),
            records_written=int(row.get("records_written", 0)),
            records_quarantined=int(row.get("records_quarantined", 0)),
            error=row.get("error"),
        )
        for row in rows
    ]
    return RunHistoryResponse(source_name=name, runs=runs, total=len(runs))


@router.get("/sources/{name}/dead-letters", response_model=DeadLetterResponse)
def get_dead_letters(
    name: str,
    limit: int = Query(default=20, le=100),
    config_svc: ConfigService = Depends(get_config_service),
    audit_svc: AuditService = Depends(get_audit_service),
):
    source = config_svc.get_source(name)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")

    catalog = source.target.get("catalog", "")
    table = source.target.get("table", "")
    if not catalog or not table:
        return DeadLetterResponse(source_name=name, total_count=0, recent_records=[])

    count = audit_svc.get_dead_letter_count(name, catalog, table)
    records = audit_svc.get_dead_letter_records(name, catalog, table, limit)
    return DeadLetterResponse(source_name=name, total_count=count, recent_records=records)


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    config_svc: ConfigService = Depends(get_config_service),
    audit_svc: AuditService = Depends(get_audit_service),
):
    sources = config_svc.list_sources()
    enabled = sum(1 for s in sources if s.enabled)
    by_type: dict[str, int] = {}
    for s in sources:
        by_type[s.source_type.value] = by_type.get(s.source_type.value, 0) + 1

    # Try to get run stats from Databricks
    run_stats = {"recent_runs": 0, "recent_failures": 0}
    if sources:
        # Use first source's catalog for audit query
        first_source = config_svc.get_source(sources[0].name)
        if first_source:
            catalog = first_source.target.get("catalog", "")
            if catalog:
                run_stats = audit_svc.get_dashboard_stats(catalog)

    return DashboardStats(
        total_sources=len(sources),
        enabled_sources=enabled,
        disabled_sources=len(sources) - enabled,
        sources_by_type=by_type,
        **run_stats,
    )
