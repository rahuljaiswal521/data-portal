"""Deploy and trigger endpoints for Silver entities."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.dependencies import get_silver_deploy_service, require_databricks_service
from app.services.silver_deploy_service import SilverDeployService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/entities/{name}/deploy",
    dependencies=[Depends(require_databricks_service)],
)
def redeploy_entity(
    name: str,
    svc: SilverDeployService = Depends(get_silver_deploy_service),
):
    """Re-upload YAML to Databricks workspace and recreate the job."""
    try:
        result = svc.redeploy(name)
        return {"name": name, "job_id": result.job_id, "message": result.message}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Redeploy failed for '%s': %s", name, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/entities/{name}/trigger",
    dependencies=[Depends(require_databricks_service)],
)
def trigger_run(
    name: str,
    svc: SilverDeployService = Depends(get_silver_deploy_service),
):
    """Trigger an immediate Databricks job run for a Silver entity."""
    run_id = svc.trigger_run(name)
    if run_id is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not trigger run — Databricks may be unavailable or the job "
                f"'silver_portal_{name}_{settings.default_environment}' does not exist yet. "
                "Try deploying first."
            ),
        )
    return {"name": name, "run_id": run_id, "message": f"Run triggered (run_id={run_id})"}
