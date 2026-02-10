"""Query audit and dead letter tables via Databricks SQL."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.services.databricks_service import DatabricksService

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, databricks_service: DatabricksService) -> None:
        self._db = databricks_service

    def get_run_history(
        self, source_name: str, catalog: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        sql = f"""
            SELECT source_name, environment, start_time, end_time,
                   status, records_read, records_written, records_quarantined, error
            FROM {catalog}.bronze_meta.ingestion_audit_log
            WHERE source_name = '{source_name}'
            ORDER BY start_time DESC
            LIMIT {limit}
        """
        return self._db.query_sql(sql)

    def get_dead_letter_count(
        self, source_name: str, catalog: str, table: str
    ) -> int:
        sql = f"""
            SELECT COUNT(*) as cnt
            FROM {catalog}.bronze_meta.dead_letter_{table}
        """
        result = self._db.query_sql(sql)
        if result:
            return int(result[0].get("cnt", 0))
        return 0

    def get_dead_letter_records(
        self, source_name: str, catalog: str, table: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        sql = f"""
            SELECT *
            FROM {catalog}.bronze_meta.dead_letter_{table}
            ORDER BY _ingest_timestamp DESC
            LIMIT {limit}
        """
        return self._db.query_sql(sql)

    def get_dashboard_stats(self, catalog: str) -> Dict[str, Any]:
        sql = f"""
            SELECT
                COUNT(*) as total_runs,
                SUM(CASE WHEN status = 'FAILURE' THEN 1 ELSE 0 END) as failures
            FROM {catalog}.bronze_meta.ingestion_audit_log
            WHERE start_time >= current_timestamp() - INTERVAL 24 HOURS
        """
        result = self._db.query_sql(sql)
        if result:
            return {
                "recent_runs": int(result[0].get("total_runs", 0)),
                "recent_failures": int(result[0].get("failures", 0)),
            }
        return {"recent_runs": 0, "recent_failures": 0}
