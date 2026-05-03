"""Gold readiness endpoint — gates the build on bronze + silver readiness.

Takes a parsed mart IR (from /preview) and returns a ReadinessReport telling
the caller whether each referenced source is in bronze, in silver, and has the
columns the gold mart needs. Optionally enriches missing-column issues with
AI suggestions for the closest column names.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import get_gold_readiness_service, get_tenant_service
from app.services.gold_readiness_service import GoldReadinessService
from app.services.tenant_service import TenantService

router = APIRouter()


class ReadinessRequest(BaseModel):
    ir: Dict[str, Any] = Field(..., description="Gold mart IR (from /preview)")
    include_ai_suggestions: bool = Field(
        False,
        description="If true, run an LLM pass to suggest replacements for missing columns",
    )


@router.post("/ingest/readiness", response_model=Dict[str, Any])
def check_readiness(
    body: ReadinessRequest,
    svc: GoldReadinessService = Depends(get_gold_readiness_service),
    tenants: TenantService = Depends(get_tenant_service),
) -> Dict[str, Any]:
    if not body.ir:
        raise HTTPException(status_code=400, detail="IR is required")

    report = svc.check(body.ir)

    if body.include_ai_suggestions and report.column_issues:
        try:
            report = svc.enrich_with_ai_suggestions(
                report, tenant_service=tenants, tenant_id=None
            )
        except Exception:
            # AI enrichment is best-effort; never fail the readiness check on it
            pass

    return report.to_dict()
