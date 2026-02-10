"""Orchestrator: validate → write YAML → git commit → deploy job."""

from __future__ import annotations

import logging
from typing import Optional

from app.config import settings
from app.models.requests import SourceCreateRequest, SourceUpdateRequest
from app.models.responses import SourceCreateResponse, SourceDeleteResponse
from app.services.config_service import ConfigService
from app.services.databricks_service import DatabricksService
from app.services.git_service import GitService

logger = logging.getLogger(__name__)


class DeployService:
    def __init__(
        self,
        config_service: ConfigService,
        git_service: GitService,
        databricks_service: DatabricksService,
    ) -> None:
        self._config = config_service
        self._git = git_service
        self._db = databricks_service

    def create_source(self, req: SourceCreateRequest) -> SourceCreateResponse:
        # 1. Validate
        valid, errors = self._config.validate_config(req)
        if not valid:
            raise ValueError("; ".join(errors))

        # 2. Write YAML
        yaml_path = self._config.write_source(req)
        logger.info("Wrote YAML to %s", yaml_path)

        # 3. Git commit
        git_sha = self._git.commit_file(
            yaml_path,
            f"portal: add source {req.name} ({req.source_type.value})",
        )

        # 4. Upload to Databricks workspace
        self._db.upload_yaml(yaml_path, req.name)

        # 5. Create/update Databricks job
        schedule = req.schedule.model_dump() if req.schedule else None
        job_id = self._db.create_or_update_job(
            req.name, settings.default_environment, schedule
        )

        return SourceCreateResponse(
            name=req.name,
            yaml_path=yaml_path,
            git_commit=git_sha,
            job_id=job_id,
            message=f"Source '{req.name}' created successfully",
        )

    def update_source(self, name: str, req: SourceUpdateRequest) -> SourceCreateResponse:
        # 1. Update YAML
        yaml_path = self._config.update_source(name, req)
        logger.info("Updated YAML at %s", yaml_path)

        # 2. Git commit
        git_sha = self._git.commit_file(
            yaml_path,
            f"portal: update source {name}",
        )

        # 3. Re-upload to Databricks
        self._db.upload_yaml(yaml_path, name)

        # 4. Update job if schedule changed
        if req.schedule:
            schedule = req.schedule.model_dump()
            self._db.create_or_update_job(name, settings.default_environment, schedule)

        return SourceCreateResponse(
            name=name,
            yaml_path=yaml_path,
            git_commit=git_sha,
            message=f"Source '{name}' updated successfully",
        )

    def delete_source(self, name: str) -> SourceDeleteResponse:
        # 1. Find and delete YAML
        source = self._config.get_source(name)
        if not source:
            raise FileNotFoundError(f"Source '{name}' not found")

        yaml_path = str(self._config._source_path(name))
        self._config.delete_source(name)

        # 2. Git commit
        self._git.commit_delete(
            yaml_path,
            f"portal: delete source {name}",
        )

        # 3. Delete Databricks job
        self._db.delete_job(name, settings.default_environment)

        return SourceDeleteResponse(
            name=name,
            message=f"Source '{name}' deleted successfully",
        )

    def redeploy(self, name: str) -> SourceCreateResponse:
        source = self._config.get_source(name)
        if not source:
            raise FileNotFoundError(f"Source '{name}' not found")

        yaml_path = str(self._config._source_path(name))

        self._db.upload_yaml(yaml_path, name)

        schedule = source.schedule
        job_id = self._db.create_or_update_job(
            name, settings.default_environment, schedule
        )

        return SourceCreateResponse(
            name=name,
            yaml_path=yaml_path,
            job_id=job_id,
            message=f"Source '{name}' redeployed successfully",
        )

    def trigger_run(self, name: str) -> Optional[str]:
        source = self._config.get_source(name)
        if not source:
            raise FileNotFoundError(f"Source '{name}' not found")

        run_id = self._db.trigger_job(name, settings.default_environment)
        return run_id
