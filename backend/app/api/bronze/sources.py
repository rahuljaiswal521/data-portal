"""CRUD endpoints for bronze source configurations."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_config_service, get_deploy_service
from app.models.requests import SourceCreateRequest, SourceUpdateRequest
from app.models.responses import (
    SourceCreateResponse,
    SourceDeleteResponse,
    SourceDetail,
    SourceListResponse,
    ValidationResponse,
)
from app.services.config_service import ConfigService
from app.services.deploy_service import DeployService

router = APIRouter()


@router.get("/sources", response_model=SourceListResponse)
def list_sources(
    source_type: Optional[str] = None,
    domain: Optional[str] = None,
    enabled: Optional[bool] = None,
    config_svc: ConfigService = Depends(get_config_service),
):
    sources = config_svc.list_sources(source_type=source_type, domain=domain, enabled=enabled)
    return SourceListResponse(sources=sources, total=len(sources))


@router.get("/sources/{name}", response_model=SourceDetail)
def get_source(
    name: str,
    config_svc: ConfigService = Depends(get_config_service),
):
    source = config_svc.get_source(name)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")
    return source


@router.post("/sources", response_model=SourceCreateResponse, status_code=201)
def create_source(
    req: SourceCreateRequest,
    deploy_svc: DeployService = Depends(get_deploy_service),
    config_svc: ConfigService = Depends(get_config_service),
):
    if config_svc.source_exists(req.name):
        raise HTTPException(status_code=409, detail=f"Source '{req.name}' already exists")
    try:
        return deploy_svc.create_source(req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.put("/sources/{name}", response_model=SourceCreateResponse)
def update_source(
    name: str,
    req: SourceUpdateRequest,
    deploy_svc: DeployService = Depends(get_deploy_service),
    config_svc: ConfigService = Depends(get_config_service),
):
    if not config_svc.source_exists(name):
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")
    try:
        return deploy_svc.update_source(name, req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/sources/{name}", response_model=SourceDeleteResponse)
def delete_source(
    name: str,
    deploy_svc: DeployService = Depends(get_deploy_service),
):
    try:
        return deploy_svc.delete_source(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/sources/{name}/validate", response_model=ValidationResponse)
def validate_source(
    name: str,
    req: SourceCreateRequest,
    config_svc: ConfigService = Depends(get_config_service),
):
    valid, errors = config_svc.validate_config(req)
    yaml_preview = config_svc.render_yaml(req) if valid else None
    return ValidationResponse(valid=valid, errors=errors, yaml_preview=yaml_preview)
