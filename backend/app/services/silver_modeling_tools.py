"""AI tool definitions and execution for Silver data modeling."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.models.silver_requests import (
    SilverColumnMappingRequest,
    SilverEntityCreateRequest,
    SilverScheduleRequest,
    SilverSourceMappingRequest,
    SilverTargetRequest,
    SilverTemporalConfigRequest,
    SilverWatermarkRequest,
)
from app.services.databricks_service import DatabricksService
from app.services.silver_config_service import SilverConfigService
from app.services.silver_deploy_service import SilverDeployService

logger = logging.getLogger(__name__)

# ── Tool Definitions (Claude API format) ──

SILVER_TOOLS = [
    {
        "name": "profile_bronze_table",
        "description": (
            "Analyze a Bronze table's schema, column statistics, and sample data "
            "to help design a Silver entity model. This is read-only and safe to call. "
            "Use this when the user wants to model a Bronze table for Silver and doesn't "
            "have data definitions."
        ),
        "input_schema": {
            "type": "object",
            "required": ["catalog", "schema", "table"],
            "properties": {
                "catalog": {
                    "type": "string",
                    "description": "Unity Catalog name (e.g. dev)",
                },
                "schema": {
                    "type": "string",
                    "description": "Schema name (e.g. bronze)",
                },
                "table": {
                    "type": "string",
                    "description": "Table name (e.g. crm_customers)",
                },
            },
        },
    },
    {
        "name": "preview_silver_model",
        "description": (
            "Generate a YAML preview of a Silver entity configuration and validate it. "
            "Use this BEFORE create_silver_entity so the user can review the config. "
            "This is safe and read-only."
        ),
        "input_schema": {
            "type": "object",
            "required": ["name", "domain", "target"],
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Entity name in snake_case (e.g. customer)",
                },
                "domain": {
                    "type": "string",
                    "description": "Business domain (e.g. customer, policy, payment)",
                },
                "description": {
                    "type": "string",
                    "description": "Human-readable description",
                },
                "entity_type": {
                    "type": "string",
                    "enum": ["standard", "temporal_join"],
                    "description": "Entity type: standard (default) or temporal_join for non-aligned SCD2 sources",
                },
                "tags": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
                "sources": {
                    "type": "array",
                    "description": "Bronze source mappings",
                    "items": {
                        "type": "object",
                        "required": ["bronze_table", "columns"],
                        "properties": {
                            "bronze_table": {"type": "string"},
                            "priority": {"type": "integer", "description": "1=highest priority"},
                            "filter_condition": {"type": "string"},
                            "watermark": {
                                "type": "object",
                                "properties": {
                                    "column": {"type": "string"},
                                    "type": {"type": "string"},
                                    "default_value": {"type": "string"},
                                },
                            },
                            "temporal": {
                                "type": "object",
                                "description": "Temporal boundary config (required for temporal_join entities)",
                                "required": ["start_column", "end_column"],
                                "properties": {
                                    "start_column": {"type": "string", "description": "Target column name for interval start"},
                                    "end_column": {"type": "string", "description": "Target column name for interval end"},
                                    "end_inclusive": {"type": "boolean", "description": "True=[start,end], False=[start,end)"},
                                },
                            },
                            "columns": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["source", "target"],
                                    "properties": {
                                        "source": {"type": "string"},
                                        "target": {"type": "string"},
                                        "transform": {"type": "string"},
                                        "default_value": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                },
                "target": {
                    "type": "object",
                    "required": ["catalog", "table"],
                    "properties": {
                        "catalog": {"type": "string"},
                        "schema": {"type": "string", "description": "Silver schema (e.g. slv_customer)"},
                        "table": {"type": "string"},
                        "scd_type": {"type": "string", "enum": ["scd2", "append"]},
                        "business_keys": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "partition_by": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "schedule": {
                    "type": "object",
                    "properties": {
                        "cron_expression": {"type": "string"},
                        "timezone": {"type": "string"},
                    },
                },
            },
        },
    },
    {
        "name": "create_silver_entity",
        "description": (
            "Deploy a Silver entity: write YAML config, git commit, upload to Databricks, "
            "and create a job. Only call this AFTER the user has reviewed the preview and "
            "explicitly confirmed they want to proceed."
        ),
        "input_schema": {
            "type": "object",
            "required": ["name", "domain", "target"],
            "properties": {
                "name": {"type": "string"},
                "domain": {"type": "string"},
                "description": {"type": "string"},
                "entity_type": {"type": "string", "enum": ["standard", "temporal_join"]},
                "tags": {"type": "object", "additionalProperties": {"type": "string"}},
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["bronze_table", "columns"],
                        "properties": {
                            "bronze_table": {"type": "string"},
                            "priority": {"type": "integer"},
                            "filter_condition": {"type": "string"},
                            "watermark": {
                                "type": "object",
                                "properties": {
                                    "column": {"type": "string"},
                                    "type": {"type": "string"},
                                    "default_value": {"type": "string"},
                                },
                            },
                            "temporal": {
                                "type": "object",
                                "required": ["start_column", "end_column"],
                                "properties": {
                                    "start_column": {"type": "string"},
                                    "end_column": {"type": "string"},
                                    "end_inclusive": {"type": "boolean"},
                                },
                            },
                            "columns": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["source", "target"],
                                    "properties": {
                                        "source": {"type": "string"},
                                        "target": {"type": "string"},
                                        "transform": {"type": "string"},
                                        "default_value": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                },
                "target": {
                    "type": "object",
                    "required": ["catalog", "table"],
                    "properties": {
                        "catalog": {"type": "string"},
                        "schema": {"type": "string"},
                        "table": {"type": "string"},
                        "scd_type": {"type": "string", "enum": ["scd2", "append"]},
                        "business_keys": {"type": "array", "items": {"type": "string"}},
                        "partition_by": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "schedule": {
                    "type": "object",
                    "properties": {
                        "cron_expression": {"type": "string"},
                        "timezone": {"type": "string"},
                    },
                },
            },
        },
    },
]


# ── Build SilverEntityCreateRequest from tool params ──

def _build_entity_request(params: Dict[str, Any]) -> SilverEntityCreateRequest:
    """Convert tool parameters into a SilverEntityCreateRequest."""
    # Sources
    sources = []
    for s in params.get("sources", []):
        watermark_data = s.get("watermark", {})
        watermark = SilverWatermarkRequest(
            column=watermark_data.get("column", "_effective_from"),
            type=watermark_data.get("type", "timestamp"),
            default_value=watermark_data.get("default_value"),
        )
        columns = [
            SilverColumnMappingRequest(
                source=c["source"],
                target=c["target"],
                transform=c.get("transform"),
                default_value=c.get("default_value"),
            )
            for c in s.get("columns", [])
        ]
        temporal = None
        if s.get("temporal"):
            t = s["temporal"]
            temporal = SilverTemporalConfigRequest(
                start_column=t["start_column"],
                end_column=t["end_column"],
                end_inclusive=t.get("end_inclusive", False),
            )
        sources.append(SilverSourceMappingRequest(
            bronze_table=s["bronze_table"],
            priority=s.get("priority", 1),
            filter_condition=s.get("filter_condition"),
            watermark=watermark,
            columns=columns,
            temporal=temporal,
        ))

    # Target
    target_raw = params.get("target", {})
    domain = params.get("domain", "")
    target = SilverTargetRequest(
        catalog=target_raw.get("catalog", ""),
        schema_name=target_raw.get("schema", f"slv_{domain}" if domain else ""),
        table=target_raw.get("table", ""),
        scd_type=target_raw.get("scd_type", "scd2"),
        business_keys=target_raw.get("business_keys", []),
        partition_by=target_raw.get("partition_by", []),
    )

    # Schedule
    schedule = None
    if params.get("schedule"):
        s = params["schedule"]
        schedule = SilverScheduleRequest(
            cron_expression=s.get("cron_expression"),
            timezone=s.get("timezone", "UTC"),
        )

    return SilverEntityCreateRequest(
        name=params["name"],
        domain=domain,
        description=params.get("description", ""),
        entity_type=params.get("entity_type", "standard"),
        tags=params.get("tags", {}),
        sources=sources,
        target=target,
        schedule=schedule,
    )


# ── Tool Execution ──

def execute_silver_tool(
    tool_name: str,
    tool_input: Dict[str, Any],
    config_service: SilverConfigService,
    deploy_service: SilverDeployService,
    databricks_service: DatabricksService,
) -> Dict[str, Any]:
    """Dispatch a Silver tool call and return the result dict."""
    try:
        if tool_name == "profile_bronze_table":
            return _execute_profile(tool_input, databricks_service)
        elif tool_name == "preview_silver_model":
            return _execute_preview(tool_input, config_service)
        elif tool_name == "create_silver_entity":
            return _execute_create(tool_input, config_service, deploy_service)
        else:
            return {"status": "error", "error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        logger.exception("Silver tool execution failed: %s", tool_name)
        return {"status": "error", "error": str(e)}


def _execute_profile(
    params: Dict[str, Any],
    databricks_service: DatabricksService,
) -> Dict[str, Any]:
    """Profile a Bronze table — schema, stats, sample data."""
    catalog = params["catalog"]
    schema = params["schema"]
    table = params["table"]
    full_name = f"{catalog}.{schema}.{table}"

    if not databricks_service.available:
        return {
            "status": "error",
            "error": "Databricks connection is not available. Cannot profile table.",
        }

    try:
        # Get schema
        describe_rows = databricks_service.query_sql(f"DESCRIBE TABLE {full_name}")
        if not describe_rows:
            return {"status": "error", "error": f"Table {full_name} not found or empty"}

        columns = []
        for row in describe_rows:
            col_name = row.get("col_name", "")
            if col_name and not col_name.startswith("#"):
                columns.append({
                    "name": col_name,
                    "type": row.get("data_type", ""),
                    "comment": row.get("comment", ""),
                })

        # Get row count
        count_rows = databricks_service.query_sql(f"SELECT COUNT(*) as cnt FROM {full_name}")
        row_count = int(count_rows[0]["cnt"]) if count_rows else 0

        # Get sample data (current records preferred)
        sample_sql = f"SELECT * FROM {full_name}"
        # Try to get current records for SCD2 tables
        has_is_current = any(c["name"] == "_is_current" for c in columns)
        if has_is_current:
            sample_sql += " WHERE _is_current = true"
        sample_sql += " LIMIT 100"
        sample_data = databricks_service.query_sql(sample_sql)

        # Basic profiling for key columns
        data_columns = [c["name"] for c in columns if not c["name"].startswith("_")]
        profiling = []
        if data_columns:
            profile_exprs = []
            for col_name in data_columns[:10]:
                profile_exprs.append(
                    f"COUNT(DISTINCT `{col_name}`) as `{col_name}_distinct`"
                )
                profile_exprs.append(
                    f"SUM(CASE WHEN `{col_name}` IS NULL THEN 1 ELSE 0 END) as `{col_name}_nulls`"
                )

            profile_sql = f"SELECT {', '.join(profile_exprs)} FROM {full_name}"
            if has_is_current:
                profile_sql += " WHERE _is_current = true"
            profile_rows = databricks_service.query_sql(profile_sql)

            if profile_rows:
                stats = profile_rows[0]
                for col_name in data_columns[:10]:
                    profiling.append({
                        "column": col_name,
                        "distinct_count": stats.get(f"{col_name}_distinct", 0),
                        "null_count": stats.get(f"{col_name}_nulls", 0),
                    })

        return {
            "status": "ok",
            "table": full_name,
            "row_count": row_count,
            "columns": columns,
            "profiling": profiling,
            "sample_data": sample_data[:5] if sample_data else [],
            "has_scd2_columns": has_is_current,
        }

    except Exception as e:
        return {"status": "error", "error": f"Failed to profile {full_name}: {str(e)}"}


def _execute_preview(
    params: Dict[str, Any],
    config_service: SilverConfigService,
) -> Dict[str, Any]:
    """Generate YAML preview and validate — read-only."""
    name = params.get("name", "")

    if config_service.entity_exists(name):
        return {
            "status": "error",
            "error": f"A Silver entity named '{name}' already exists. Choose a different name.",
        }

    req = _build_entity_request(params)

    valid, errors = config_service.validate_config(req)
    if not valid:
        return {"status": "validation_error", "errors": errors}

    yaml_preview = config_service.render_yaml(req)
    return {"status": "ok", "yaml_preview": yaml_preview}


def _execute_create(
    params: Dict[str, Any],
    config_service: SilverConfigService,
    deploy_service: SilverDeployService,
) -> Dict[str, Any]:
    """Create the Silver entity end-to-end."""
    name = params.get("name", "")

    if config_service.entity_exists(name):
        return {
            "status": "error",
            "error": f"A Silver entity named '{name}' already exists.",
        }

    req = _build_entity_request(params)
    result = deploy_service.create_entity(req)

    return {
        "status": "ok",
        "name": result.name,
        "yaml_path": result.yaml_path,
        "git_commit": result.git_commit,
        "job_id": result.job_id,
        "message": result.message,
    }
