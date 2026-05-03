"""Tool definition for querying the bronze ingestion audit log via Databricks SQL."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)

AUDIT_TOOLS = [
    {
        "name": "query_audit_log",
        "description": (
            "Query the Databricks ingestion audit log to retrieve operational data "
            "about bronze pipeline runs. Use this whenever the user asks about: "
            "when a table was last loaded, run history, record counts, failures, "
            "errors, quarantined records, load duration, or pipeline health. "
            "Always use this tool for operational questions — never guess or fabricate numbers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_name": {
                    "type": "string",
                    "description": (
                        "Filter results to a specific source (e.g. 'file_customers'). "
                        "Omit or leave empty to return runs across all sources."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of recent runs to return. Default: 10. Max: 50.",
                },
                "status_filter": {
                    "type": "string",
                    "enum": ["SUCCESS", "FAILURE", "all"],
                    "description": "Filter by run status. Default: all.",
                },
            },
        },
    }
]

# Safe identifier: only alphanumeric + underscore
_SAFE_ID = re.compile(r"^[a-zA-Z0-9_]+$")


def execute_audit_tool(
    tool_name: str,
    tool_input: Dict[str, Any],
    databricks_service,
) -> Dict[str, Any]:
    """Dispatch an audit tool call and return the result dict."""
    try:
        if tool_name == "query_audit_log":
            return _query_audit_log(tool_input, databricks_service)
        return {"status": "error", "error": f"Unknown audit tool: {tool_name}"}
    except Exception as e:
        logger.exception("Audit tool execution failed: %s", tool_name)
        return {"status": "error", "error": str(e)}


def _query_audit_log(
    params: Dict[str, Any],
    databricks_service,
) -> Dict[str, Any]:
    """Query dev.bronze_meta.ingestion_audit_log and return structured results."""
    if not databricks_service.available:
        return {
            "status": "error",
            "error": "Databricks is not configured — cannot query audit log.",
        }

    source_name: str = params.get("source_name", "") or ""
    limit: int = min(int(params.get("limit", 10)), 50)
    status_filter: str = (params.get("status_filter") or "all").upper()

    # Build WHERE clause — only safe, validated identifiers go into SQL
    conditions = []

    if source_name:
        if not _SAFE_ID.match(source_name):
            return {"status": "error", "error": f"Invalid source name: '{source_name}'"}
        conditions.append(f"source_name = '{source_name}'")

    if status_filter in ("SUCCESS", "FAILURE"):
        conditions.append(f"status = '{status_filter}'")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    sql = f"""
        SELECT
            source_name,
            status,
            start_time,
            end_time,
            records_read,
            records_written,
            records_quarantined,
            error_message,
            environment
        FROM dev.bronze_meta.ingestion_audit_log
        {where}
        ORDER BY start_time DESC
        LIMIT {limit}
    """.strip()

    rows = databricks_service.query_sql(sql)

    if not rows:
        parts = ["No audit log entries found"]
        if source_name:
            parts.append(f"for source '{source_name}'")
        if status_filter != "ALL":
            parts.append(f"with status '{status_filter}'")
        return {"status": "ok", "message": " ".join(parts), "rows": []}

    return {
        "status": "ok",
        "row_count": len(rows),
        "rows": rows,
    }
