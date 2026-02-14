"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure directories exist
    settings.sources_dir.mkdir(parents=True, exist_ok=True)
    Path(settings.chromadb_persist_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.tenant_db_path).parent.mkdir(parents=True, exist_ok=True)
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

app.include_router(api_router)
