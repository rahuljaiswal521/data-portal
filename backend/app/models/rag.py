"""Pydantic models for RAG chat requests and responses."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(
        default=None,
        description="Chat session ID for conversation continuity.",
    )


class ChatResponse(BaseModel):
    answer: str
    query_type: str
    sources_used: List[str]
    session_id: str


class ChatMessage(BaseModel):
    role: str
    content: str
    created_at: Optional[str] = None


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: List[ChatMessage]


class IndexRebuildResponse(BaseModel):
    shared_docs_indexed: int
    source_configs_indexed: int
    message: str


class IndexStatusResponse(BaseModel):
    shared_doc_chunks: int
    tenant_source_chunks: int
