"""Tool definitions and execution logic for AI-assisted pipeline creation."""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.models.enums import CdcMode, LoadType, SourceType
from app.models.requests import (
    CdcRequest,
    ExtractRequest,
    LandingRequest,
    MetadataColumnRequest,
    QualityRequest,
    ScheduleRequest,
    SourceCreateRequest,
    TargetRequest,
)
from app.services.config_service import ConfigService
from app.services.deploy_service import DeployService

logger = logging.getLogger(__name__)


# ── Tool Definitions (Claude API format) ──

_SHARED_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["name", "source_type", "target"],
    "properties": {
        "name": {
            "type": "string",
            "description": "Source name in snake_case (e.g. sales_orders)",
        },
        "source_type": {
            "type": "string",
            "enum": ["file", "jdbc", "api", "stream"],
            "description": "Type of data source",
        },
        "description": {
            "type": "string",
            "description": "Human-readable description of the source",
        },
        "tags": {
            "type": "object",
            "description": "Key-value tags (e.g. {\"domain\": \"sales\"})",
            "additionalProperties": {"type": "string"},
        },
        "extract": {
            "type": "object",
            "description": "Extract configuration",
            "properties": {
                "load_type": {
                    "type": "string",
                    "enum": ["full", "incremental"],
                    "description": "Load strategy (default: full)",
                },
                "path": {
                    "type": "string",
                    "description": "File path for file sources",
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "csv", "parquet", "avro", "delta"],
                    "description": "File format (default: parquet)",
                },
                "format_options": {
                    "type": "object",
                    "description": "Format-specific options (e.g. {\"header\": \"true\"} for CSV)",
                    "additionalProperties": {"type": "string"},
                },
                "auto_loader": {
                    "type": "boolean",
                    "description": "Use Auto Loader for incremental file ingestion",
                },
                "table": {
                    "type": "string",
                    "description": "Source table name for JDBC sources",
                },
                "query": {
                    "type": "string",
                    "description": "SQL query for JDBC sources",
                },
                "base_url": {
                    "type": "string",
                    "description": "Base URL for API sources",
                },
                "endpoint": {
                    "type": "string",
                    "description": "API endpoint path",
                },
                "kafka_bootstrap_servers": {
                    "type": "string",
                    "description": "Kafka bootstrap servers for stream sources",
                },
                "kafka_topic": {
                    "type": "string",
                    "description": "Kafka topic for stream sources",
                },
            },
        },
        "target": {
            "type": "object",
            "required": ["catalog", "table"],
            "description": "Target table configuration",
            "properties": {
                "catalog": {
                    "type": "string",
                    "description": "Unity Catalog name (e.g. dev)",
                },
                "schema_name": {
                    "type": "string",
                    "description": "Schema name (default: bronze)",
                },
                "table": {
                    "type": "string",
                    "description": "Target table name",
                },
                "cdc": {
                    "type": "object",
                    "description": "Change data capture settings",
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "mode": {
                            "type": "string",
                            "enum": ["append", "upsert", "scd2"],
                        },
                        "primary_keys": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Primary key columns for upsert/scd2",
                        },
                        "sequence_column": {
                            "type": "string",
                            "description": "Column to determine record ordering",
                        },
                        "delete_condition_column": {"type": "string"},
                        "delete_condition_value": {"type": "string"},
                    },
                },
                "landing": {
                    "type": "object",
                    "description": "Landing zone settings",
                    "properties": {
                        "path": {"type": "string"},
                        "retention_days": {"type": "integer"},
                    },
                },
            },
        },
        "schedule": {
            "type": "object",
            "description": "Job schedule",
            "properties": {
                "cron_expression": {
                    "type": "string",
                    "description": "Quartz cron expression (e.g. 0 0 6 * * ?)",
                },
                "timezone": {
                    "type": "string",
                    "description": "Timezone (default: UTC)",
                },
            },
        },
    },
}

PIPELINE_TOOLS = [
    {
        "name": "preview_bronze_pipeline",
        "description": (
            "Generate a YAML preview of a bronze pipeline configuration and validate it. "
            "Use this BEFORE create_bronze_pipeline so the user can review the config. "
            "This is safe and read-only — it does not write any files or deploy anything."
        ),
        "input_schema": _SHARED_INPUT_SCHEMA,
    },
    {
        "name": "create_bronze_pipeline",
        "description": (
            "Deploy a bronze pipeline: write YAML config, git commit, upload to Databricks, "
            "and create a job. Only call this AFTER the user has reviewed the preview and "
            "explicitly confirmed they want to proceed."
        ),
        "input_schema": _SHARED_INPUT_SCHEMA,
    },
]


# ── Build SourceCreateRequest from simplified tool params ──

def _build_source_request(params: Dict[str, Any]) -> SourceCreateRequest:
    """Convert simplified tool parameters into a full SourceCreateRequest.

    Applies smart defaults for metadata_columns, exclude_columns_from_hash,
    landing path, schema evolution, and quality settings.
    """
    source_type = SourceType(params["source_type"])

    # Extract config
    extract_raw = params.get("extract", {})
    extract = ExtractRequest(
        load_type=LoadType(extract_raw.get("load_type", "full")),
        path=extract_raw.get("path"),
        format=extract_raw.get("format", "parquet"),
        format_options=extract_raw.get("format_options", {}),
        auto_loader=extract_raw.get("auto_loader", False),
        table=extract_raw.get("table"),
        query=extract_raw.get("query"),
        base_url=extract_raw.get("base_url"),
        endpoint=extract_raw.get("endpoint"),
        kafka_bootstrap_servers=extract_raw.get("kafka_bootstrap_servers"),
        kafka_topic=extract_raw.get("kafka_topic"),
    )

    # Target config
    target_raw = params.get("target", {})
    cdc_raw = target_raw.get("cdc", {})

    cdc_mode = CdcMode(cdc_raw.get("mode", "append")) if cdc_raw else CdcMode.APPEND
    cdc_enabled = cdc_raw.get("enabled", cdc_mode != CdcMode.APPEND)

    cdc = CdcRequest(
        enabled=cdc_enabled,
        mode=cdc_mode,
        primary_keys=cdc_raw.get("primary_keys", []),
        sequence_column=cdc_raw.get("sequence_column"),
        delete_condition_column=cdc_raw.get("delete_condition_column"),
        delete_condition_value=cdc_raw.get("delete_condition_value"),
        exclude_columns_from_hash=[
            "_ingest_timestamp", "_ingest_date", "_source_file",
        ],
    )

    landing_raw = target_raw.get("landing", {})
    landing_path = landing_raw.get("path")
    if not landing_path and source_type == SourceType.FILE and extract.path:
        landing_path = extract.path
    landing = LandingRequest(
        path=landing_path,
        retention_days=landing_raw.get("retention_days", 10),
    )

    quality = QualityRequest(enabled=True)

    # Smart default metadata columns
    source_name = params["name"]
    metadata_columns = [
        MetadataColumnRequest(name="_ingest_timestamp", expression="current_timestamp()"),
        MetadataColumnRequest(name="_ingest_date", expression="current_date()"),
        MetadataColumnRequest(name="_source_system", expression=f"lit('{source_name}')"),
    ]

    target = TargetRequest(
        catalog=target_raw.get("catalog", ""),
        schema_name=target_raw.get("schema_name", "bronze"),
        table=target_raw.get("table", ""),
        metadata_columns=metadata_columns,
        quality=quality,
        cdc=cdc,
        landing=landing,
    )

    # Schedule
    schedule = None
    schedule_raw = params.get("schedule")
    if schedule_raw:
        schedule = ScheduleRequest(
            cron_expression=schedule_raw.get("cron_expression"),
            timezone=schedule_raw.get("timezone", "UTC"),
        )

    return SourceCreateRequest(
        name=source_name,
        source_type=source_type,
        description=params.get("description", ""),
        tags=params.get("tags", {}),
        extract=extract,
        target=target,
        schedule=schedule,
    )


# ── Tool Execution ──

def execute_tool(
    tool_name: str,
    tool_input: Dict[str, Any],
    config_service: ConfigService,
    deploy_service: DeployService,
) -> Dict[str, Any]:
    """Dispatch a tool call and return the result dict."""
    try:
        if tool_name == "preview_bronze_pipeline":
            return _execute_preview(tool_input, config_service)
        elif tool_name == "create_bronze_pipeline":
            return _execute_create(tool_input, config_service, deploy_service)
        else:
            return {"status": "error", "error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        logger.exception("Tool execution failed: %s", tool_name)
        return {"status": "error", "error": str(e)}


def _execute_preview(
    params: Dict[str, Any],
    config_service: ConfigService,
) -> Dict[str, Any]:
    """Generate YAML preview and validate — read-only, no side effects."""
    name = params.get("name", "")

    # Check for duplicates
    if config_service.source_exists(name):
        return {
            "status": "error",
            "error": f"A source named '{name}' already exists. Choose a different name.",
        }

    req = _build_source_request(params)

    # Validate
    valid, errors = config_service.validate_config(req)
    if not valid:
        return {"status": "validation_error", "errors": errors}

    # Render YAML
    yaml_preview = config_service.render_yaml(req)
    return {"status": "ok", "yaml_preview": yaml_preview}


def _execute_create(
    params: Dict[str, Any],
    config_service: ConfigService,
    deploy_service: DeployService,
) -> Dict[str, Any]:
    """Create the source end-to-end via DeployService."""
    name = params.get("name", "")

    if config_service.source_exists(name):
        return {
            "status": "error",
            "error": f"A source named '{name}' already exists. Choose a different name.",
        }

    req = _build_source_request(params)
    result = deploy_service.create_source(req)

    return {
        "status": "ok",
        "name": result.name,
        "yaml_path": result.yaml_path,
        "git_commit": result.git_commit,
        "job_id": result.job_id,
        "message": result.message,
    }
