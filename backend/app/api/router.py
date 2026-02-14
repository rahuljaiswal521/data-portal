"""Top-level API router aggregating all sub-routers."""

import yaml
from fastapi import APIRouter

from app.api.bronze.deploy import router as deploy_router
from app.api.bronze.monitoring import router as monitoring_router
from app.api.bronze.sources import router as sources_router
from app.api.common.health import router as health_router
from app.api.rag.chat import router as rag_chat_router
from app.api.rag.index import router as rag_index_router
from app.config import settings
from app.models.responses import EnvironmentInfo

api_router = APIRouter(prefix="/api/v1")

# Common
api_router.include_router(health_router, tags=["health"])

# Bronze
api_router.include_router(sources_router, prefix="/bronze", tags=["bronze-sources"])
api_router.include_router(deploy_router, prefix="/bronze", tags=["bronze-deploy"])
api_router.include_router(monitoring_router, prefix="/bronze", tags=["bronze-monitoring"])

# RAG Assistant
api_router.include_router(rag_chat_router, prefix="/rag", tags=["rag-assistant"])
api_router.include_router(rag_index_router, prefix="/rag", tags=["rag-index"])


@api_router.get("/environments", response_model=list[EnvironmentInfo], tags=["environments"])
def list_environments():
    envs = []
    env_dir = settings.environments_dir
    if env_dir.exists():
        for env_file in sorted(env_dir.glob("*.yaml")):
            with open(env_file, "r") as f:
                variables = yaml.safe_load(f) or {}
            envs.append(EnvironmentInfo(name=env_file.stem, variables=variables))
    return envs
