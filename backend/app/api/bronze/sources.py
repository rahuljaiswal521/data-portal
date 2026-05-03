"""CRUD endpoints for bronze source configurations."""

import logging
import threading
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_config_service, get_deploy_service, get_testing_service
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
from app.services.testing_service import TestingService

logger = logging.getLogger(__name__)

router = APIRouter()


def _generate_suite_background(testing_svc: TestingService, source_name: str) -> None:
    """Fire-and-forget wrapper — failures are logged, never surfaced."""
    try:
        testing_svc.generate_suite(source_name)
        logger.info("Auto-generated test suite for '%s'", source_name)
    except Exception as e:
        logger.warning("Auto-generate suite failed for '%s': %s", source_name, e)


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
    testing_svc: TestingService = Depends(get_testing_service),
):
    if config_svc.source_exists(req.name):
        raise HTTPException(status_code=409, detail=f"Source '{req.name}' already exists")
    try:
        result = deploy_svc.create_source(req)
        # Auto-generate test suite scaffold in background (non-blocking)
        threading.Thread(
            target=_generate_suite_background,
            args=(testing_svc, req.name),
            daemon=True,
        ).start()
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=409, detail=f"Source '{req.name}' could not be created: {e}")


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
    except (FileNotFoundError, OSError) as e:
        # TOCTOU: source was deleted between exists() check and update
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")


@router.delete("/sources/{name}", response_model=SourceDeleteResponse)
def delete_source(
    name: str,
    deploy_svc: DeployService = Depends(get_deploy_service),
):
    try:
        return deploy_svc.delete_source(name)
    except (FileNotFoundError, OSError) as e:
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
