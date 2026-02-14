"""RAG index management endpoints."""

from fastapi import APIRouter, Depends

from app.api.common.auth import get_current_tenant
from app.dependencies import get_embedding_service, get_rag_service
from app.models.rag import IndexRebuildResponse, IndexStatusResponse
from app.services.embedding_service import EmbeddingService
from app.services.rag_service import RAGService

router = APIRouter()


@router.post("/index/rebuild", response_model=IndexRebuildResponse)
async def rebuild_index(
    tenant_id: str = Depends(get_current_tenant),
    rag_svc: RAGService = Depends(get_rag_service),
):
    result = rag_svc.build_index(tenant_id)
    return IndexRebuildResponse(
        shared_docs_indexed=result["shared_docs"],
        source_configs_indexed=result["source_configs"],
        message="Index rebuilt successfully",
    )


@router.get("/index/status", response_model=IndexStatusResponse)
async def get_index_status(
    tenant_id: str = Depends(get_current_tenant),
    embedding_svc: EmbeddingService = Depends(get_embedding_service),
):
    status = embedding_svc.get_index_status(tenant_id)
    return IndexStatusResponse(**status)
