"""Unit tests for ai_client_service helpers.

Covers the pure-Python dispatch/validation helpers:
- get_provider(model_id) — prefix-based provider detection
- is_valid_model(model_id) — model id catalogue validation
- get_selected_model(tenant_service, tenant_id) — tenant-scoped lookup with default fallback
- AVAILABLE_MODELS catalogue shape and DEFAULT_MODEL_ID
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services import ai_client_service
from app.services.tenant_service import TenantService


class TestGetProvider:
    def test_claude_prefix_is_anthropic(self):
        assert ai_client_service.get_provider("claude-sonnet-4-5-20250929") == "anthropic"
        assert ai_client_service.get_provider("claude-opus-4-6") == "anthropic"
        assert ai_client_service.get_provider("claude-haiku-4-5-20251001") == "anthropic"

    def test_gpt_prefix_is_openai(self):
        assert ai_client_service.get_provider("gpt-4.1") == "openai"
        assert ai_client_service.get_provider("gpt-4.1-mini") == "openai"

    def test_o_series_prefixes_are_openai(self):
        assert ai_client_service.get_provider("o1-preview") == "openai"
        assert ai_client_service.get_provider("o3-mini") == "openai"
        assert ai_client_service.get_provider("o4-turbo") == "openai"

    def test_gemini_prefix_is_gemini(self):
        assert ai_client_service.get_provider("gemini-2.5-pro") == "gemini"
        assert ai_client_service.get_provider("gemini-2.5-flash") == "gemini"

    def test_none_falls_back_to_anthropic(self):
        assert ai_client_service.get_provider(None) == "anthropic"

    def test_empty_string_falls_back_to_anthropic(self):
        assert ai_client_service.get_provider("") == "anthropic"

    def test_unknown_prefix_falls_back_to_anthropic(self):
        assert ai_client_service.get_provider("mistral-large") == "anthropic"


class TestIsValidModel:
    def test_all_catalogue_ids_are_valid(self):
        for model in ai_client_service.AVAILABLE_MODELS:
            assert ai_client_service.is_valid_model(model["id"])

    def test_unknown_model_is_invalid(self):
        assert not ai_client_service.is_valid_model("gpt-9000")
        assert not ai_client_service.is_valid_model("")
        assert not ai_client_service.is_valid_model("claude-ultra")


class TestGetSelectedModel:
    def test_returns_default_when_no_tenant_service(self):
        result = ai_client_service.get_selected_model(tenant_service=None, tenant_id=None)
        assert result == ai_client_service.DEFAULT_MODEL_ID

    def test_returns_default_when_no_tenant_id(self):
        svc = MagicMock(spec=TenantService)
        result = ai_client_service.get_selected_model(tenant_service=svc, tenant_id=None)
        assert result == ai_client_service.DEFAULT_MODEL_ID

    def test_returns_tenant_selected_when_valid(self):
        svc = MagicMock(spec=TenantService)
        svc.get_selected_model.return_value = "gpt-4.1"
        result = ai_client_service.get_selected_model(svc, "tenant-xyz")
        assert result == "gpt-4.1"

    def test_falls_back_to_default_when_tenant_returns_none(self):
        svc = MagicMock(spec=TenantService)
        svc.get_selected_model.return_value = None
        result = ai_client_service.get_selected_model(svc, "tenant-xyz")
        assert result == ai_client_service.DEFAULT_MODEL_ID

    def test_falls_back_to_default_when_tenant_returns_unknown_model(self):
        """Protects against stale model IDs in the DB after catalogue changes."""
        svc = MagicMock(spec=TenantService)
        svc.get_selected_model.return_value = "gpt-legacy-unknown"
        result = ai_client_service.get_selected_model(svc, "tenant-xyz")
        assert result == ai_client_service.DEFAULT_MODEL_ID

    def test_falls_back_to_default_on_tenant_service_exception(self):
        """DB errors must not propagate — we always return a usable model."""
        svc = MagicMock(spec=TenantService)
        svc.get_selected_model.side_effect = RuntimeError("DB unreachable")
        result = ai_client_service.get_selected_model(svc, "tenant-xyz")
        assert result == ai_client_service.DEFAULT_MODEL_ID


class TestAvailableModelsCatalogue:
    def test_catalogue_is_nonempty(self):
        assert len(ai_client_service.AVAILABLE_MODELS) > 0

    def test_catalogue_has_expected_providers(self):
        providers = {m["provider"] for m in ai_client_service.AVAILABLE_MODELS}
        assert providers == {"anthropic", "openai", "gemini"}

    def test_each_model_has_required_fields(self):
        for m in ai_client_service.AVAILABLE_MODELS:
            assert "id" in m and isinstance(m["id"], str) and m["id"]
            assert "name" in m and isinstance(m["name"], str) and m["name"]
            assert "description" in m and isinstance(m["description"], str)
            assert "provider" in m and m["provider"] in ("anthropic", "openai", "gemini")

    def test_model_ids_are_unique(self):
        ids = [m["id"] for m in ai_client_service.AVAILABLE_MODELS]
        assert len(ids) == len(set(ids))

    def test_default_model_is_in_catalogue(self):
        assert ai_client_service.is_valid_model(ai_client_service.DEFAULT_MODEL_ID)

    def test_default_model_provider_is_anthropic(self):
        assert ai_client_service.get_provider(ai_client_service.DEFAULT_MODEL_ID) == "anthropic"


class TestNoApiKeyError:
    def test_is_runtime_error_subclass(self):
        """Callers catch RuntimeError — NoApiKeyError must inherit from it."""
        assert issubclass(ai_client_service.NoApiKeyError, RuntimeError)

    def test_can_be_raised_and_caught(self):
        import pytest
        with pytest.raises(RuntimeError, match="no key"):
            raise ai_client_service.NoApiKeyError("no key configured")
