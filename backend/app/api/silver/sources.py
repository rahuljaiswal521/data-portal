"""CRUD endpoints for Silver entity configurations."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_silver_config_service, get_silver_deploy_service
from app.models.silver_requests import SilverEntityCreateRequest, SilverEntityUpdateRequest
from app.models.silver_responses import (
    SilverEntityCreateResponse,
    SilverEntityDeleteResponse,
    SilverEntityDetail,
    SilverEntityListResponse,
    SilverValidationResponse,
)
from app.services.silver_config_service import SilverConfigService
from app.services.silver_deploy_service import SilverDeployService

router = APIRouter()


@router.get("/entities", response_model=SilverEntityListResponse)
def list_entities(
    domain: Optional[str] = None,
    enabled: Optional[bool] = None,
    scd_type: Optional[str] = None,
    config_svc: SilverConfigService = Depends(get_silver_config_service),
):
    entities = config_svc.list_entities(domain=domain, enabled=enabled, scd_type=scd_type)
    return SilverEntityListResponse(entities=entities, total=len(entities))


@router.get("/entities/{name}", response_model=SilverEntityDetail)
def get_entity(
    name: str,
    config_svc: SilverConfigService = Depends(get_silver_config_service),
):
    entity = config_svc.get_entity(name)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Silver entity '{name}' not found")
    return entity


@router.post("/entities", response_model=SilverEntityCreateResponse, status_code=201)
def create_entity(
    req: SilverEntityCreateRequest,
    deploy_svc: SilverDeployService = Depends(get_silver_deploy_service),
    config_svc: SilverConfigService = Depends(get_silver_config_service),
):
    if config_svc.entity_exists(req.name):
        raise HTTPException(status_code=409, detail=f"Silver entity '{req.name}' already exists")
    try:
        return deploy_svc.create_entity(req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.put("/entities/{name}", response_model=SilverEntityCreateResponse)
def update_entity(
    name: str,
    req: SilverEntityUpdateRequest,
    deploy_svc: SilverDeployService = Depends(get_silver_deploy_service),
    config_svc: SilverConfigService = Depends(get_silver_config_service),
):
    if not config_svc.entity_exists(name):
        raise HTTPException(status_code=404, detail=f"Silver entity '{name}' not found")
    try:
        return deploy_svc.update_entity(name, req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/entities/{name}", response_model=SilverEntityDeleteResponse)
def delete_entity(
    name: str,
    deploy_svc: SilverDeployService = Depends(get_silver_deploy_service),
):
    try:
        return deploy_svc.delete_entity(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/entities/{name}/validate", response_model=SilverValidationResponse)
def validate_entity(
    name: str,
    req: SilverEntityCreateRequest,
    config_svc: SilverConfigService = Depends(get_silver_config_service),
):
    valid, errors = config_svc.validate_config(req)
    yaml_preview = config_svc.render_yaml(req) if valid else None
    return SilverValidationResponse(valid=valid, errors=errors, yaml_preview=yaml_preview)
