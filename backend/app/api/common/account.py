"""Account settings endpoints — per-tenant AI configuration."""

from fastapi import APIRouter, Depends

from app.api.common.auth import get_current_tenant
from app.dependencies import get_tenant_service
from app.models.tenant import (
    AccountSettingsResponse,
    AccountSettingsUpdate,
    AvailableModel,
    AvailableModelsResponse,
    ProviderKeyStatus,
    ProviderKeyUpdate,
    SelectedModelUpdate,
)
from app.services import ai_client_service
from app.services.tenant_service import TenantService

router = APIRouter()


def _mask_key(key: str) -> str:
    """Return a masked preview like 'sk-ant-...XXXX'."""
    if len(key) <= 8:
        return "****"
    return key[:8] + "..." + key[-4:]


def _build_response(tenant_id: str, tenant_svc: TenantService) -> AccountSettingsResponse:
    """Build full AccountSettingsResponse from all three providers + selected model."""
    ak = tenant_svc.get_anthropic_api_key(tenant_id)
    ok = tenant_svc.get_openai_api_key(tenant_id)
    gk = tenant_svc.get_gemini_api_key(tenant_id)
    selected_model = ai_client_service.get_selected_model(tenant_svc, tenant_id)
    selected_provider = ai_client_service.get_provider(selected_model)
    return AccountSettingsResponse(
        anthropic=ProviderKeyStatus(configured=ak is not None, preview=_mask_key(ak) if ak else None),
        openai=ProviderKeyStatus(configured=ok is not None, preview=_mask_key(ok) if ok else None),
        gemini=ProviderKeyStatus(configured=gk is not None, preview=_mask_key(gk) if gk else None),
        selected_model=selected_model,
        selected_provider=selected_provider,
        # Legacy
        has_anthropic_key=ak is not None,
        anthropic_key_preview=_mask_key(ak) if ak else None,
    )


@router.get("/account/settings", response_model=AccountSettingsResponse)
def get_account_settings(
    tenant_id: str = Depends(get_current_tenant),
    tenant_svc: TenantService = Depends(get_tenant_service),
) -> AccountSettingsResponse:
    return _build_response(tenant_id, tenant_svc)


@router.put("/account/settings", response_model=AccountSettingsResponse)
def update_account_settings(
    body: AccountSettingsUpdate,
    tenant_id: str = Depends(get_current_tenant),
    tenant_svc: TenantService = Depends(get_tenant_service),
) -> AccountSettingsResponse:
    """Save Anthropic API key (legacy endpoint — kept for backward compat)."""
    tenant_svc.set_anthropic_api_key(tenant_id, body.anthropic_api_key)
    return _build_response(tenant_id, tenant_svc)


# ── Per-provider PUT / DELETE ─────────────────────────────────────────────────

@router.put("/account/settings/anthropic-key", response_model=AccountSettingsResponse)
def set_anthropic_key(
    body: ProviderKeyUpdate,
    tenant_id: str = Depends(get_current_tenant),
    tenant_svc: TenantService = Depends(get_tenant_service),
) -> AccountSettingsResponse:
    tenant_svc.set_anthropic_api_key(tenant_id, body.api_key)
    return _build_response(tenant_id, tenant_svc)


@router.delete("/account/settings/anthropic-key", response_model=AccountSettingsResponse)
def delete_anthropic_key(
    tenant_id: str = Depends(get_current_tenant),
    tenant_svc: TenantService = Depends(get_tenant_service),
) -> AccountSettingsResponse:
    tenant_svc.clear_anthropic_api_key(tenant_id)
    return _build_response(tenant_id, tenant_svc)


@router.put("/account/settings/openai-key", response_model=AccountSettingsResponse)
def set_openai_key(
    body: ProviderKeyUpdate,
    tenant_id: str = Depends(get_current_tenant),
    tenant_svc: TenantService = Depends(get_tenant_service),
) -> AccountSettingsResponse:
    tenant_svc.set_openai_api_key(tenant_id, body.api_key)
    return _build_response(tenant_id, tenant_svc)


@router.delete("/account/settings/openai-key", response_model=AccountSettingsResponse)
def delete_openai_key(
    tenant_id: str = Depends(get_current_tenant),
    tenant_svc: TenantService = Depends(get_tenant_service),
) -> AccountSettingsResponse:
    tenant_svc.clear_openai_api_key(tenant_id)
    return _build_response(tenant_id, tenant_svc)


@router.put("/account/settings/gemini-key", response_model=AccountSettingsResponse)
def set_gemini_key(
    body: ProviderKeyUpdate,
    tenant_id: str = Depends(get_current_tenant),
    tenant_svc: TenantService = Depends(get_tenant_service),
) -> AccountSettingsResponse:
    tenant_svc.set_gemini_api_key(tenant_id, body.api_key)
    return _build_response(tenant_id, tenant_svc)


@router.delete("/account/settings/gemini-key", response_model=AccountSettingsResponse)
def delete_gemini_key(
    tenant_id: str = Depends(get_current_tenant),
    tenant_svc: TenantService = Depends(get_tenant_service),
) -> AccountSettingsResponse:
    tenant_svc.clear_gemini_api_key(tenant_id)
    return _build_response(tenant_id, tenant_svc)


# ── Model selection ──────────────────────────────────────────────────────────

@router.get("/account/settings/models", response_model=AvailableModelsResponse)
def list_available_models() -> AvailableModelsResponse:
    """Return the catalogue of AI models the user can choose from."""
    return AvailableModelsResponse(
        models=[AvailableModel(**m) for m in ai_client_service.AVAILABLE_MODELS],
        default_model=ai_client_service.DEFAULT_MODEL_ID,
    )


@router.put("/account/settings/selected-model", response_model=AccountSettingsResponse)
def set_selected_model(
    body: SelectedModelUpdate,
    tenant_id: str = Depends(get_current_tenant),
    tenant_svc: TenantService = Depends(get_tenant_service),
) -> AccountSettingsResponse:
    """Set the active model for this tenant. Must be one of AVAILABLE_MODELS."""
    if not ai_client_service.is_valid_model(body.model_id):
        from fastapi import HTTPException
        raise HTTPException(400, detail=f"Unknown model id '{body.model_id}'")
    tenant_svc.set_selected_model(tenant_id, body.model_id)
    return _build_response(tenant_id, tenant_svc)
