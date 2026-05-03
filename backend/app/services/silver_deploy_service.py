"""Orchestrator: validate → write YAML → git commit → deploy Silver entity."""

from __future__ import annotations

import logging
from typing import Optional

from app.config import settings
from app.models.silver_requests import SilverEntityCreateRequest, SilverEntityUpdateRequest
from app.models.silver_responses import SilverEntityCreateResponse, SilverEntityDeleteResponse
from app.services.databricks_service import DatabricksService
from app.services.git_service import GitService
from app.services.silver_config_service import SilverConfigService

logger = logging.getLogger(__name__)


class SilverDeployService:
    def __init__(
        self,
        config_service: SilverConfigService,
        git_service: GitService,
        databricks_service: DatabricksService,
    ) -> None:
        self._config = config_service
        self._git = git_service
        self._db = databricks_service

    def create_entity(self, req: SilverEntityCreateRequest) -> SilverEntityCreateResponse:
        # 1. Validate
        valid, errors = self._config.validate_config(req)
        if not valid:
            raise ValueError("; ".join(errors))

        # 2. Write YAML
        yaml_path = self._config.write_entity(req)
        logger.info("Wrote Silver YAML to %s", yaml_path)

        # 3. Git commit
        git_sha = self._git.commit_file(
            yaml_path,
            f"portal: add silver entity {req.name} ({req.domain})",
        )

        # 4. Upload to Databricks workspace
        self._upload_yaml(yaml_path, req.name)

        # 5. Create/update Databricks job
        schedule = req.schedule.model_dump() if req.schedule else None
        job_id = self._create_silver_job(req.name, schedule)

        return SilverEntityCreateResponse(
            name=req.name,
            yaml_path=yaml_path,
            git_commit=git_sha,
            job_id=job_id,
            message=f"Silver entity '{req.name}' created successfully",
        )

    def update_entity(self, name: str, req: SilverEntityUpdateRequest) -> SilverEntityCreateResponse:
        # 1. Update YAML
        yaml_path = self._config.update_entity(name, req)
        logger.info("Updated Silver YAML at %s", yaml_path)

        # 2. Git commit
        git_sha = self._git.commit_file(
            yaml_path,
            f"portal: update silver entity {name}",
        )

        # 3. Re-upload to Databricks
        self._upload_yaml(yaml_path, name)

        # 4. Update job if schedule changed
        if req.schedule:
            schedule = req.schedule.model_dump()
            self._create_silver_job(name, schedule)

        return SilverEntityCreateResponse(
            name=name,
            yaml_path=yaml_path,
            git_commit=git_sha,
            message=f"Silver entity '{name}' updated successfully",
        )

    def delete_entity(self, name: str) -> SilverEntityDeleteResponse:
        entity = self._config.get_entity(name)
        if not entity:
            raise FileNotFoundError(f"Silver entity '{name}' not found")

        yaml_path = str(self._config._entity_path(name))
        self._config.delete_entity(name)

        self._git.commit_delete(
            yaml_path,
            f"portal: delete silver entity {name}",
        )

        self._delete_silver_job(name)

        return SilverEntityDeleteResponse(
            name=name,
            message=f"Silver entity '{name}' deleted successfully",
        )

    def redeploy(self, name: str) -> SilverEntityCreateResponse:
        """Re-upload YAML + recreate Databricks job (no git commit)."""
        entity = self._config.get_entity(name)
        if not entity:
            raise FileNotFoundError(f"Silver entity '{name}' not found")

        yaml_path = str(self._config._entity_path(name))
        self._upload_yaml(yaml_path, name)

        schedule = None
        if isinstance(entity, dict) and entity.get("schedule"):
            schedule = entity["schedule"]

        job_id = self._create_silver_job(name, schedule)

        return SilverEntityCreateResponse(
            name=name,
            yaml_path=yaml_path,
            git_commit=None,
            job_id=job_id,
            message=f"Silver entity '{name}' redeployed successfully",
        )

    def trigger_run(self, name: str) -> Optional[str]:
        """Trigger an immediate Databricks job run for a Silver entity."""
        if not self._db.available:
            return None

        job_name = f"silver_portal_{name}_{settings.default_environment}"
        job_id = self._db._find_job(job_name)
        if not job_id:
            logger.error("Silver job '%s' not found on Databricks", job_name)
            return None

        try:
            run = self._db._client.jobs.run_now(job_id=job_id)
            logger.info("Triggered Silver run %s for job %s", run.run_id, job_name)
            return str(run.run_id)
        except Exception as e:
            logger.error("Silver job trigger failed: %s", e)
            return None

    def _upload_yaml(self, local_path: str, entity_name: str) -> Optional[str]:
        """Upload Silver entity YAML to Databricks workspace."""
        if not self._db.available:
            return None
        import base64
        from databricks.sdk.service.workspace import ImportFormat
        try:
            remote_path = f"{settings.databricks_silver_workspace_path}/conf/entities/{entity_name}.yaml"
            # workspace.import_ requires delete-before for AUTO format (no overwrite)
            try:
                self._db._client.workspace.delete(remote_path)
            except Exception:
                pass
            with open(local_path, "rb") as f:
                content_b64 = base64.b64encode(f.read()).decode("utf-8")
            self._db._client.workspace.import_(
                path=remote_path,
                content=content_b64,
                format=ImportFormat.AUTO,
            )
            logger.info("Uploaded Silver YAML to %s", remote_path)
            return remote_path
        except Exception as e:
            logger.error("Silver workspace upload failed: %s", e)
            raise RuntimeError(f"YAML upload to Databricks failed: {e}") from e

    def _create_silver_job(self, entity_name: str, schedule: Optional[dict] = None) -> Optional[str]:
        """Create or update a Databricks job for a Silver entity."""
        if not self._db.available:
            return None
        try:
            from databricks.sdk.service.jobs import (
                JobSettings,
                NotebookTask,
                Task,
            )

            job_name = f"silver_portal_{entity_name}_{settings.default_environment}"
            notebook_path = f"{settings.databricks_silver_workspace_path}/notebooks/02_run_single_entity"

            base_params = {
                "environment": settings.default_environment,
                "entity_file": f"{entity_name}.yaml",
                "conf_dir": f"{settings.databricks_silver_workspace_path}/conf",
            }

            from databricks.sdk.service.compute import Library

            wheel_path = (
                f"{settings.databricks_silver_workspace_path}"
                f"/dist/silver_framework-1.0.0-py3-none-any.whl"
            )

            task = Task(
                task_key="run_silver_entity",
                notebook_task=NotebookTask(
                    notebook_path=notebook_path,
                    base_parameters=base_params,
                ),
                existing_cluster_id=getattr(settings, "databricks_cluster_id", None),
                libraries=[Library(whl=wheel_path)],
            )

            job_settings = JobSettings(
                name=job_name,
                tasks=[task],
            )

            # Schedule
            if schedule and schedule.get("cron_expression"):
                from databricks.sdk.service.jobs import CronSchedule
                job_settings.schedule = CronSchedule(
                    quartz_cron_expression=schedule["cron_expression"],
                    timezone_id=schedule.get("timezone", "UTC"),
                )

            # Find existing job — _find_job returns the job_id int directly
            existing_id = self._db._find_job(job_name)
            if existing_id:
                self._db._client.jobs.update(
                    job_id=existing_id,
                    new_settings=job_settings,
                )
                logger.info("Updated Silver job: %s (id=%s)", job_name, existing_id)
                return str(existing_id)
            else:
                result = self._db._client.jobs.create(
                    name=job_name,
                    tasks=[task],
                    schedule=job_settings.schedule,
                    tags={"team": "data-engineering", "layer": "silver", "entity": entity_name},
                )
                logger.info("Created Silver job: %s (id=%s)", job_name, result.job_id)
                return str(result.job_id)

        except Exception as e:
            logger.error("Silver job creation failed: %s", e)
            raise RuntimeError(f"Databricks job create/update failed: {e}") from e

    def _delete_silver_job(self, entity_name: str) -> None:
        """Delete the Databricks job for a Silver entity."""
        if not self._db.available:
            return
        try:
            job_name = f"silver_portal_{entity_name}_{settings.default_environment}"
            existing = self._db._find_job(job_name)
            if existing:
                self._db._client.jobs.delete(job_id=existing)
                logger.info("Deleted Silver job: %s", job_name)
        except Exception as e:
            logger.error("Silver job deletion failed: %s", e)
