"""RAG chat endpoints."""

import secrets

from fastapi import APIRouter, Depends

from app.api.common.auth import get_current_tenant
from app.dependencies import get_rag_service, get_tenant_service
from app.models.rag import (
    ChatHistoryResponse,
    ChatMessage,
    ChatRequest,
    ChatResponse,
)
from app.services.rag_service import RAGService
from app.services.tenant_service import TenantService

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    tenant_id: str = Depends(get_current_tenant),
    rag_svc: RAGService = Depends(get_rag_service),
):
    session_id = req.session_id or secrets.token_urlsafe(16)

    result = rag_svc.answer(
        tenant_id=tenant_id,
        question=req.question,
        session_id=session_id,
    )

    return ChatResponse(
        answer=result["answer"],
        query_type=result["query_type"],
        sources_used=result["sources_used"],
        session_id=session_id,
    )


@router.get("/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str,
    limit: int = 20,
    tenant_id: str = Depends(get_current_tenant),
    tenant_svc: TenantService = Depends(get_tenant_service),
):
    messages = tenant_svc.get_chat_history(tenant_id, session_id, limit)

    return ChatHistoryResponse(
        session_id=session_id,
        messages=[
            ChatMessage(
                role=m["role"],
                content=m["content"],
                created_at=m.get("created_at"),
            )
            for m in messages
        ],
    )
