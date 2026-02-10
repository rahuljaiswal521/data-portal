"""Health check endpoint."""

from fastapi import APIRouter

from app.config import settings
from app.models.responses import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(
        status="ok",
        framework_root=settings.framework_root,
        sources_dir_exists=settings.sources_dir.exists(),
        databricks_configured=bool(settings.databricks_host and settings.databricks_token),
    )
