"""Pydantic models for tenant management."""

from typing import Optional

from pydantic import BaseModel, Field


class TenantCreateRequest(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9_-]+$", min_length=2, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)


class TenantCreateResponse(BaseModel):
    id: str
    name: str
    api_key: str


class TenantInfo(BaseModel):
    id: str
    name: str
    created_at: Optional[str] = None
    enabled: bool
