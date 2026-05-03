"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure directories exist
    settings.sources_dir.mkdir(parents=True, exist_ok=True)
    Path(settings.chromadb_persist_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.tenant_db_path).parent.mkdir(parents=True, exist_ok=True)

    # Seed default admin user if not already present
    try:
        from app.dependencies import get_tenant_service
        tenant_svc = get_tenant_service()
        tenant_svc.ensure_default_admin(
            username=settings.portal_admin_username,
            password=settings.portal_admin_password,
        )
    except Exception as e:
        logger.warning("Failed to seed default admin: %s", e)

    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="Data Portal",
    description="Self-service portal for configuring data ingestion and transformation layers",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def api_key_auth(request: Request, call_next):
    key = settings.portal_api_key
    if not key:
        return await call_next(request)
    if request.method == "OPTIONS":          # allow CORS preflight through
        return await call_next(request)
    if request.url.path.startswith("/api/v1/health"):
        return await call_next(request)
    if request.url.path.startswith("/api/v1/auth/login"):
        return await call_next(request)
    incoming = request.headers.get("X-API-Key", "")
    if incoming != key:
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all handler that returns JSON + CORS headers so browsers see the error."""
    logger.exception("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    origin = request.headers.get("origin", "")
    extra_headers = {}
    if origin in settings.cors_origins:
        extra_headers["Access-Control-Allow-Origin"] = origin
        extra_headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again."},
        headers=extra_headers,
    )


app.include_router(api_router)
