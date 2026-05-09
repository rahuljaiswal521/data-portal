"""Databricks SDK integration — job management and workspace upload."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class DatabricksService:
    """Per-tenant wrapper over the Databricks SDK.

    Construct with explicit ``host`` / ``token`` / ``warehouse_id`` (per-tenant
    credentials) — passing ``None`` for any of them yields an unavailable
    instance whose Databricks-touching methods return None / raise.

    The constructor falls back to env-var settings only when ALL three
    arguments are None. This preserves backward compatibility for tests and
    legacy callers that rely on the singleton-with-env behaviour.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        token: Optional[str] = None,
        warehouse_id: Optional[str] = None,
    ) -> None:
        # Back-compat: when no arguments at all, use env-var settings.
        if host is None and token is None and warehouse_id is None:
            host = settings.databricks_host
            token = settings.databricks_token
            warehouse_id = settings.databricks_warehouse_id

        self._host = host
        self._token = token
        self._warehouse_id = warehouse_id
        self._client = None
        if host and token:
            try:
                from databricks.sdk import WorkspaceClient
                self._client = WorkspaceClient(host=host, token=token)
            except Exception as e:
                logger.warning("Databricks SDK not available: %s", e)

    @property
    def available(self) -> bool:
        return self._client is not None

    @property
    def warehouse_id(self) -> Optional[str]:
        """The active warehouse_id — for callers that previously read settings directly."""
        return self._warehouse_id

    def current_user_email(self) -> Optional[str]:
        """Return the authenticated user's email, or None if not available.

        Used by the test-connection endpoint to validate host + token without
        any side-effects.
        """
        if not self.available:
            return None
        try:
            me = self._client.current_user.me()
            return getattr(me, "user_name", None) or getattr(me, "userName", None)
        except Exception as e:
            logger.warning("current_user.me() failed: %s", e)
            return None

    def upload_yaml(self, local_path: str, source_name: str) -> str:
        if not self.available:
            raise RuntimeError("Databricks client not initialised — check DATABRICKS_HOST and DATABRICKS_TOKEN")

        remote_path = f"{settings.databricks_workspace_path}/conf/sources/{source_name}.yaml"
        try:
            from databricks.sdk.service.workspace import ImportFormat
            # Delete first — overwrite=True is incompatible with ImportFormat.AUTO
            try:
                self._client.workspace.delete(remote_path)
            except Exception:
                pass  # file doesn't exist yet, that's fine
            with open(local_path, "rb") as f:
                self._client.workspace.upload(
                    remote_path, f, format=ImportFormat.AUTO
                )
            logger.info("Uploaded YAML to %s", remote_path)
            return remote_path
        except Exception as e:
            logger.error("Workspace upload failed: %s", e)
            raise RuntimeError(f"Workspace upload failed: {e}") from e

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
            from databricks.sdk.service.compute import Library

            existing = self._find_job(job_name)

            notebook_task = NotebookTask(
                notebook_path=f"{settings.databricks_workspace_path}/notebooks/02_run_single_source.py",
                base_parameters={
                    "environment": environment,
                    "source_file": f"{source_name}.yaml",
                    "conf_dir": f"{settings.databricks_workspace_path}/conf",
                },
            )

            libraries = [
                Library(whl=f"{settings.databricks_workspace_path}/dist/bronze_framework-1.0.0-py3-none-any.whl")
            ]

            # Prefer existing cluster (avoids new-cluster provisioning which requires Azure VM quota).
            # Set DATABRICKS_CLUSTER_ID in .env to use an existing interactive/all-purpose cluster.
            if settings.databricks_cluster_id:
                task = Task(
                    task_key="run_source",
                    existing_cluster_id=settings.databricks_cluster_id,
                    notebook_task=notebook_task,
                    libraries=libraries,
                    timeout_seconds=7200,
                    max_retries=1,
                )
                job_clusters = []
                logger.info("Job will run on existing cluster %s", settings.databricks_cluster_id)
            else:
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
                    libraries=libraries,
                    timeout_seconds=7200,
                    max_retries=1,
                )
                job_clusters = [job_cluster]
                logger.warning(
                    "No DATABRICKS_CLUSTER_ID set — job will provision a new cluster on each run"
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
                        job_clusters=job_clusters,
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
                    job_clusters=job_clusters,
                    tasks=[task],
                    schedule=cron_schedule,
                    tags={"team": "data-engineering", "layer": "bronze", "source": source_name},
                )
                logger.info("Created job %s (id=%s)", job_name, result.job_id)
                return str(result.job_id)
        except Exception as e:
            logger.error("Job create/update failed: %s", e)
            raise RuntimeError(f"Job create/update failed: {e}") from e

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
        if not self.available or not self._warehouse_id:
            return []

        try:
            result = self._client.statement_execution.execute_statement(
                warehouse_id=self._warehouse_id,
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

    def list_tables(self, catalog: str, schema: str) -> List[Dict[str, Any]]:
        """List tables in a Unity Catalog schema."""
        rows = self.query_sql(f"SHOW TABLES IN `{catalog}`.`{schema}`")
        return [
            {"table": r["tableName"], "full_name": f"{catalog}.{schema}.{r['tableName']}"}
            for r in (rows or [])
        ]

    def clear_volume_directory(self, directory_path: str) -> None:
        """Delete all files in a Unity Catalog Volume directory.

        Used to ensure each test run sees only its own data files.
        Silently skips directories that do not exist.
        """
        if not self.available:
            return
        try:
            for f in self._client.files.list_directory_contents(directory_path):
                try:
                    self._client.files.delete(f.path)
                except Exception as e:
                    logger.warning("Could not delete volume file %s: %s", f.path, e)
            logger.info("Cleared volume directory %s", directory_path)
        except Exception as e:
            logger.debug("Could not list volume directory %s (may not exist): %s", directory_path, e)

    def upload_bytes_to_volume(self, content: bytes, volume_path: str) -> None:
        """Upload raw bytes to a Unity Catalog Volume path.

        Requires databricks-sdk >= 0.30 which exposes the Files API.
        ``volume_path`` must be of the form
        ``/Volumes/<catalog>/<schema>/<volume>/<path>``.
        """
        if not self.available:
            raise RuntimeError(
                "Databricks client not initialised — check DATABRICKS_HOST and DATABRICKS_TOKEN"
            )
        try:
            import io

            self._client.files.upload(volume_path, io.BytesIO(content), overwrite=True)
            logger.info("Uploaded %d bytes to %s", len(content), volume_path)
        except Exception as e:
            logger.error("Volume upload failed: %s", e)
            raise RuntimeError(f"Volume upload failed: {e}") from e

    def wait_for_run_by_id(self, run_id: Optional[str], timeout: int = 600) -> bool:
        """Poll a specific Databricks job run until it completes.

        Returns True on SUCCESS, False on FAILED/TIMEDOUT/CANCELED or timeout.
        Uses the Jobs API run-state (not the audit log) so there is no
        risk of matching a stale audit-log entry from a previous run.
        """
        if not self.available or not run_id:
            return True  # Offline / no run id — assume success

        import time

        try:
            run_id_int = int(run_id)
        except (TypeError, ValueError):
            logger.warning("Invalid run_id %s — skipping wait", run_id)
            return True

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                run = self._client.jobs.runs.get(run_id=run_id_int)
                lc = str(getattr(run.state, "life_cycle_state", "") or "")
                if lc in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
                    result = str(getattr(run.state, "result_state", "") or "")
                    return result == "SUCCESS"
            except Exception as e:
                logger.warning("Error polling run %s: %s", run_id, e)
            time.sleep(10)

        logger.warning("Timed out waiting for Databricks run %s", run_id)
        return False

    def _find_job(self, job_name: str) -> Optional[int]:
        try:
            for job in self._client.jobs.list(name=job_name):
                return job.job_id
        except Exception:
            pass
        return None
