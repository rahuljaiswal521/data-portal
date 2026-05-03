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


class ProviderKeyStatus(BaseModel):
    configured: bool
    preview: Optional[str] = None  # e.g. "sk-ant-...XXXX"


class AvailableModel(BaseModel):
    id: str
    name: str
    description: str
    provider: str


class AccountSettingsResponse(BaseModel):
    anthropic: ProviderKeyStatus
    openai: ProviderKeyStatus
    gemini: ProviderKeyStatus
    selected_model: str
    selected_provider: str
    # Legacy fields kept for backward compatibility
    has_anthropic_key: bool
    anthropic_key_preview: Optional[str] = None


class AvailableModelsResponse(BaseModel):
    models: list[AvailableModel]
    default_model: str


class ProviderKeyUpdate(BaseModel):
    api_key: str = Field(..., min_length=10)


class SelectedModelUpdate(BaseModel):
    model_id: str = Field(..., min_length=1, max_length=100)


class AccountSettingsUpdate(BaseModel):
    anthropic_api_key: str = Field(..., min_length=10)
