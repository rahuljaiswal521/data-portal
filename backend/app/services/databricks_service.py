"""Databricks SDK integration — job management and workspace upload."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class DatabricksService:
    def __init__(self) -> None:
        self._client = None
        if settings.databricks_host and settings.databricks_token:
            try:
                from databricks.sdk import WorkspaceClient
                self._client = WorkspaceClient(
                    host=settings.databricks_host,
                    token=settings.databricks_token,
                )
            except Exception as e:
                logger.warning("Databricks SDK not available: %s", e)

    @property
    def available(self) -> bool:
        return self._client is not None

    def upload_yaml(self, local_path: str, source_name: str) -> Optional[str]:
        if not self.available:
            return None

        try:
            remote_path = f"{settings.databricks_workspace_path}/conf/sources/{source_name}.yaml"
            with open(local_path, "rb") as f:
                self._client.workspace.upload(
                    remote_path, f, overwrite=True, format="AUTO"
                )
            logger.info("Uploaded YAML to %s", remote_path)
            return remote_path
        except Exception as e:
            logger.error("Workspace upload failed: %s", e)
            return None

    def create_or_update_job(
        self, source_name: str, environment: str, schedule: Optional[Dict] = None
    ) -> Optional[str]:
        if not self.available:
            return None

        job_name = f"bronze_portal_{source_name}_{environment}"

        try:
            from databricks.sdk.service.jobs import (
                CronSchedule,
                JobCluster,
                JobSettings,
                NotebookTask,
                PauseStatus,
                Task,
            )

            existing = self._find_job(job_name)

            notebook_task = NotebookTask(
                notebook_path=f"{settings.databricks_workspace_path}/notebooks/02_run_single_source.py",
                base_parameters={
                    "environment": environment,
                    "source_file": f"{source_name}.yaml",
                    "conf_dir": f"{settings.databricks_workspace_path}/conf",
                },
            )

            job_cluster = JobCluster(
                job_cluster_key="ingestion_cluster",
                new_cluster={
                    "spark_version": settings.databricks_spark_version,
                    "node_type_id": settings.databricks_node_type_id,
                    "num_workers": 2,
                    "autoscale": {"min_workers": 1, "max_workers": 4},
                    "spark_conf": {
                        "spark.databricks.delta.schema.autoMerge.enabled": "true",
                        "spark.sql.streaming.schemaInference": "true",
                    },
                    "data_security_mode": "USER_ISOLATION",
                },
            )

            if settings.databricks_cluster_policy_id:
                job_cluster.new_cluster["policy_id"] = settings.databricks_cluster_policy_id

            task = Task(
                task_key="run_source",
                job_cluster_key="ingestion_cluster",
                notebook_task=notebook_task,
                libraries=[
                    {"whl": f"{settings.databricks_workspace_path}/dist/bronze_framework-1.0.0-py3-none-any.whl"}
                ],
                timeout_seconds=7200,
                max_retries=1,
            )

            cron_schedule = None
            if schedule and schedule.get("cron_expression"):
                cron_schedule = CronSchedule(
                    quartz_cron_expression=schedule["cron_expression"],
                    timezone_id=schedule.get("timezone", "UTC"),
                    pause_status=PauseStatus(schedule.get("pause_status", "UNPAUSED")),
                )

            if existing:
                self._client.jobs.update(
                    job_id=existing,
                    new_settings=JobSettings(
                        name=job_name,
                        job_clusters=[job_cluster],
                        tasks=[task],
                        schedule=cron_schedule,
                        tags={"team": "data-engineering", "layer": "bronze", "source": source_name},
                    ),
                )
                logger.info("Updated job %s (id=%s)", job_name, existing)
                return str(existing)
            else:
                result = self._client.jobs.create(
                    name=job_name,
                    job_clusters=[job_cluster],
                    tasks=[task],
                    schedule=cron_schedule,
                    tags={"team": "data-engineering", "layer": "bronze", "source": source_name},
                )
                logger.info("Created job %s (id=%s)", job_name, result.job_id)
                return str(result.job_id)
        except Exception as e:
            logger.error("Job create/update failed: %s", e)
            return None

    def trigger_job(self, source_name: str, environment: str) -> Optional[str]:
        if not self.available:
            return None

        job_name = f"bronze_portal_{source_name}_{environment}"
        job_id = self._find_job(job_name)
        if not job_id:
            logger.error("Job %s not found", job_name)
            return None

        try:
            run = self._client.jobs.run_now(job_id=job_id)
            logger.info("Triggered run %s for job %s", run.run_id, job_name)
            return str(run.run_id)
        except Exception as e:
            logger.error("Job trigger failed: %s", e)
            return None

    def delete_job(self, source_name: str, environment: str) -> bool:
        if not self.available:
            return False

        job_name = f"bronze_portal_{source_name}_{environment}"
        job_id = self._find_job(job_name)
        if not job_id:
            return True  # already gone

        try:
            self._client.jobs.delete(job_id=job_id)
            logger.info("Deleted job %s (id=%s)", job_name, job_id)
            return True
        except Exception as e:
            logger.error("Job deletion failed: %s", e)
            return False

    def query_sql(self, sql: str) -> List[Dict[str, Any]]:
        if not self.available or not settings.databricks_warehouse_id:
            return []

        try:
            result = self._client.statement_execution.execute_statement(
                warehouse_id=settings.databricks_warehouse_id,
                statement=sql,
                wait_timeout="30s",
            )
            if result.result and result.result.data_array:
                columns = [c.name for c in result.manifest.schema.columns]
                return [dict(zip(columns, row)) for row in result.result.data_array]
            return []
        except Exception as e:
            logger.error("SQL query failed: %s", e)
            return []

    def _find_job(self, job_name: str) -> Optional[int]:
        try:
            for job in self._client.jobs.list(name=job_name):
                return job.job_id
        except Exception:
            pass
        return None
