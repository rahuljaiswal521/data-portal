"""Gold mart CRUD endpoints (list / read / delete)."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_gold_config_service
from app.services.gold_config_service import GoldConfigService

router = APIRouter()


@router.get("/marts", response_model=List[Dict[str, Any]])
def list_marts(svc: GoldConfigService = Depends(get_gold_config_service)) -> List[Dict[str, Any]]:
    return svc.list_marts()


@router.get("/marts/{name}", response_model=Dict[str, Any])
def get_mart(name: str, svc: GoldConfigService = Depends(get_gold_config_service)) -> Dict[str, Any]:
    try:
        return svc.get_mart(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/marts/{name}", status_code=204)
def delete_mart(name: str, svc: GoldConfigService = Depends(get_gold_config_service)) -> None:
    try:
        svc.delete_mart(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
