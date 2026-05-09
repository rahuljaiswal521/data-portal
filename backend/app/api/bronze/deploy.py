"""Deploy and trigger endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_deploy_service, require_databricks_service
from app.models.responses import SourceCreateResponse
from app.services.deploy_service import DeployService

router = APIRouter()


@router.post(
    "/sources/{name}/deploy",
    response_model=SourceCreateResponse,
    dependencies=[Depends(require_databricks_service)],
)
def redeploy_source(
    name: str,
    deploy_svc: DeployService = Depends(get_deploy_service),
):
    try:
        return deploy_svc.redeploy(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post(
    "/sources/{name}/trigger",
    dependencies=[Depends(require_databricks_service)],
)
def trigger_run(
    name: str,
    deploy_svc: DeployService = Depends(get_deploy_service),
):
    try:
        run_id = deploy_svc.trigger_run(name)
        if run_id:
            return {"message": f"Run triggered for '{name}'", "run_id": run_id}
        return {"message": f"Run triggered for '{name}' (Databricks not configured)", "run_id": None}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
