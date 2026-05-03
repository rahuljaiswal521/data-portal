"""Monitoring endpoints for Silver entities."""

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends

from app.dependencies import get_silver_config_service
from app.models.silver_responses import (
    SilverDashboardStats,
    SilverDiagramResponse,
    SilverRunHistoryResponse,
    SilverRunRecord,
)
from app.services.silver_config_service import SilverConfigService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats", response_model=SilverDashboardStats)
def get_silver_stats(
    config_svc: SilverConfigService = Depends(get_silver_config_service),
):
    entities = config_svc.list_entities()

    domains = sorted(set(e.domain for e in entities))
    entities_by_domain: dict[str, int] = {}
    for e in entities:
        entities_by_domain[e.domain] = entities_by_domain.get(e.domain, 0) + 1

    entities_by_scd_type: dict[str, int] = {}
    for e in entities:
        entities_by_scd_type[e.scd_type] = entities_by_scd_type.get(e.scd_type, 0) + 1

    return SilverDashboardStats(
        total_entities=len(entities),
        enabled_entities=sum(1 for e in entities if e.enabled),
        domains=domains,
        entities_by_domain=entities_by_domain,
        entities_by_scd_type=entities_by_scd_type,
    )


@router.get("/entities/{name}/runs", response_model=SilverRunHistoryResponse)
def get_entity_runs(
    name: str,
    limit: int = 50,
    config_svc: SilverConfigService = Depends(get_silver_config_service),
):
    """Get run history for a Silver entity from the audit log.

    Requires Databricks connection — returns empty list if unavailable.
    """
    entity = config_svc.get_entity(name)
    if not entity:
        return SilverRunHistoryResponse(entity_name=name, runs=[], total=0)

    # Query audit log via Databricks SQL
    try:
        from app.dependencies import get_databricks_service
        db = get_databricks_service()
        if not db.available:
            return SilverRunHistoryResponse(entity_name=name, runs=[], total=0)

        catalog = entity.target.get("catalog", "")
        if not catalog:
            return SilverRunHistoryResponse(entity_name=name, runs=[], total=0)

        audit_table = f"{catalog}.slv_meta.transformation_audit_log"
        sql = (
            f"SELECT * FROM {audit_table} "
            f"WHERE entity_name = '{name}' "
            f"ORDER BY start_time DESC LIMIT {limit}"
        )
        rows = db.query_sql(sql)

        runs = []
        for row in (rows or []):
            runs.append(SilverRunRecord(
                entity_name=row.get("entity_name", name),
                domain=row.get("domain", ""),
                target_table=row.get("target_table", ""),
                status=row.get("status", "UNKNOWN"),
                start_time=str(row.get("start_time")) if row.get("start_time") else None,
                end_time=str(row.get("end_time")) if row.get("end_time") else None,
                records_read=int(row.get("records_read", 0)),
                records_written=int(row.get("records_written", 0)),
                records_skipped=int(row.get("records_skipped", 0)),
                error_message=row.get("error_message"),
                scd_type=row.get("scd_type", ""),
                bronze_sources=row.get("bronze_sources", ""),
            ))

        return SilverRunHistoryResponse(entity_name=name, runs=runs, total=len(runs))

    except Exception as e:
        logger.warning("Failed to fetch Silver run history: %s", e)
        return SilverRunHistoryResponse(entity_name=name, runs=[], total=0)


def _sanitize_mermaid_name(name: str) -> str:
    """Make a name safe for Mermaid identifiers (alphanumeric + underscore only)."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    # Remove leading digits (invalid identifier start)
    cleaned = re.sub(r"^[0-9]+", "", cleaned)
    return cleaned or "unnamed"


def _build_mermaid_diagram(entities_detail: list) -> str:
    """Generate Mermaid ER diagram syntax from Silver entity details."""
    lines = ["erDiagram"]

    # Group entities by domain
    entities_by_domain: dict[str, list] = {}
    for entity in entities_detail:
        entities_by_domain.setdefault(entity.domain, []).append(entity)

    # Build business key ownership: bk_name -> entity_name (first entity that owns it)
    bk_to_entity: dict[str, str] = {}
    for entity in entities_detail:
        target = entity.target
        for bk in target.get("business_keys", []):
            if bk not in bk_to_entity:
                bk_to_entity[bk] = entity.name

    # Collect unique target columns per entity
    entity_columns: dict[str, list[dict]] = {}
    for entity in entities_detail:
        target = entity.target
        bkeys = set(target.get("business_keys", []))
        columns_seen: dict[str, dict] = {}
        for source in entity.sources:
            for col in source.get("columns", []):
                tgt = col.get("target", col.get("source", ""))
                if not tgt or tgt in columns_seen:
                    continue
                marker = ""
                if tgt in bkeys:
                    marker = "PK"
                elif tgt in bk_to_entity and bk_to_entity[tgt] != entity.name:
                    marker = "FK"
                columns_seen[tgt] = {"name": tgt, "marker": marker}
        entity_columns[entity.name] = list(columns_seen.values())

    # Collect all bronze source names for rendering as minimal blocks
    bronze_sources_seen: set[str] = set()
    relationships: list[str] = []

    # Generate entity blocks grouped by domain
    for domain in sorted(entities_by_domain.keys()):
        lines.append(f"    %% Domain: {domain}")
        for entity in entities_by_domain[domain]:
            safe_name = _sanitize_mermaid_name(entity.name)
            lines.append(f"    {safe_name} {{")
            for col in entity_columns.get(entity.name, []):
                marker_str = f" {col['marker']}" if col["marker"] else ""
                lines.append(f"        string {col['name']}{marker_str}")
            lines.append("    }")

            # Source -> entity relationships
            for source in entity.sources:
                bronze_table = source.get("bronze_table", "")
                if not bronze_table:
                    continue
                # Strip variable prefix like ${catalog}.
                display_name = re.sub(r"\$\{[^}]+\}\.", "", bronze_table)
                safe_bronze = _sanitize_mermaid_name(display_name)
                bronze_sources_seen.add(safe_bronze)
                priority = source.get("priority", "")
                label = f"source (pri {priority})" if priority else "source"
                relationships.append(
                    f'    {safe_bronze} ||--o{{ {safe_name} : "{label}"'
                )

    # Cross-entity FK relationships
    for entity in entities_detail:
        safe_name = _sanitize_mermaid_name(entity.name)
        for col in entity_columns.get(entity.name, []):
            if col["marker"] == "FK":
                owner = bk_to_entity.get(col["name"])
                if owner:
                    safe_owner = _sanitize_mermaid_name(owner)
                    relationships.append(
                        f'    {safe_owner} ||--o{{ {safe_name} : "{col["name"]}"'
                    )

    # Add bronze source blocks (minimal — no columns)
    if bronze_sources_seen:
        lines.append("    %% Bronze Sources")
        for src in sorted(bronze_sources_seen):
            lines.append(f"    {src} {{")
            lines.append("        string _bronze_source")
            lines.append("    }")

    # Add relationships
    if relationships:
        lines.append("")
        lines.extend(relationships)

    return "\n".join(lines)


@router.get("/diagram", response_model=SilverDiagramResponse)
def get_silver_diagram(
    config_svc: SilverConfigService = Depends(get_silver_config_service),
):
    """Generate a Mermaid ER diagram from all Silver entity configurations."""
    summaries = config_svc.list_entities()
    if not summaries:
        return SilverDiagramResponse(mermaid="erDiagram", entity_count=0, domains=[])

    # Fetch full detail for each entity to get column mappings
    entities_detail = []
    for summary in summaries:
        detail = config_svc.get_entity(summary.name)
        if detail:
            entities_detail.append(detail)

    domains = sorted(set(e.domain for e in entities_detail))
    mermaid_text = _build_mermaid_diagram(entities_detail)

    return SilverDiagramResponse(
        mermaid=mermaid_text,
        entity_count=len(entities_detail),
        domains=domains,
    )
