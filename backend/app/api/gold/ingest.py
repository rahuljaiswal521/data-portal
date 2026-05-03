"""Business-rules-sheet ingest endpoints.

Two-step UX:
    1. POST /gold/ingest/preview — upload .xlsx, return parsed IR + diff
    2. POST /gold/ingest/commit  — POST the IR back to persist as YAML files
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.dependencies import get_gold_ingest_service
from app.services.gold_ingest_service import GoldIngestError, GoldIngestService

router = APIRouter()


# ── Models ───────────────────────────────────────────────────────────────────


class CommitRequest(BaseModel):
    ir: Dict[str, Any] = Field(..., description="Parsed mart IR (from /preview)")
    overwrite: bool = Field(False, description="Overwrite existing mart on disk")


# ── Routes ───────────────────────────────────────────────────────────────────


@router.post("/ingest/preview", response_model=Dict[str, Any])
async def preview_ingest(
    file: UploadFile = File(..., description=".xlsx workbook"),
    default_mart_name: str = Form("new_mart"),
    svc: GoldIngestService = Depends(get_gold_ingest_service),
) -> Dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename in upload")

    data = await file.read()
    try:
        return svc.preview(
            upload_bytes=data,
            filename=file.filename,
            default_mart_name=default_mart_name,
        )
    except GoldIngestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        # BusinessRulesParseError is a ValueError subclass
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ingest/commit", response_model=Dict[str, Any])
def commit_ingest(
    body: CommitRequest,
    svc: GoldIngestService = Depends(get_gold_ingest_service),
) -> Dict[str, Any]:
    try:
        return svc.commit(ir=body.ir, overwrite=body.overwrite)
    except GoldIngestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
