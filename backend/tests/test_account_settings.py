"""Tests for account settings endpoints.

Covers:
- GET  /api/v1/account/settings
- PUT  /api/v1/account/settings  (legacy)
- PUT/DELETE /api/v1/account/settings/anthropic-key
- PUT/DELETE /api/v1/account/settings/openai-key
- PUT/DELETE /api/v1/account/settings/gemini-key
"""

BASE = "/api/v1/account"


class TestGetAccountSettings:
    def test_get_settings_no_key(self, client):
        """Fresh default tenant has no Anthropic key."""
        resp = client.get(f"{BASE}/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_anthropic_key"] is False
        assert data["anthropic_key_preview"] is None

    def test_get_settings_response_shape(self, client):
        """Response contains legacy fields and new provider objects."""
        resp = client.get(f"{BASE}/settings")
        assert resp.status_code == 200
        data = resp.json()
        # Legacy fields
        assert "has_anthropic_key" in data
        assert "anthropic_key_preview" in data
        # New per-provider fields
        for provider in ("anthropic", "openai", "gemini"):
            assert provider in data, f"Missing provider '{provider}' in response"
            assert "configured" in data[provider]
            assert "preview" in data[provider]

    def test_get_settings_all_providers_unconfigured_by_default(self, client):
        """All three providers show configured=False with no keys set."""
        resp = client.get(f"{BASE}/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["anthropic"]["configured"] is False
        assert data["openai"]["configured"] is False
        assert data["gemini"]["configured"] is False
        assert data["anthropic"]["preview"] is None
        assert data["openai"]["preview"] is None
        assert data["gemini"]["preview"] is None

    def test_get_settings_after_key_set(self, client, mock_tenant):
        """After setting a key, GET reflects has_anthropic_key=True with masked preview."""
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_anthropic_api_key("default", "sk-ant-api03-testkey1234567890")
        resp = client.get(f"{BASE}/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_anthropic_key"] is True
        assert data["anthropic_key_preview"] is not None
        assert "..." in data["anthropic_key_preview"]

    def test_get_settings_no_auth_required_in_dev_mode(self, client):
        """No X-API-Key header needed when rag_require_auth=False."""
        resp = client.get(f"{BASE}/settings")
        assert resp.status_code == 200

    def test_get_settings_auth_required_without_key_returns_401(self, client, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "rag_require_auth", True)
        resp = client.get(f"{BASE}/settings")
        assert resp.status_code == 401


class TestUpdateAccountSettings:
    def test_update_settings_saves_key(self, client, mock_tenant):
        """PUT with a valid key persists it and returns confirmation."""
        resp = client.put(
            f"{BASE}/settings",
            json={"anthropic_api_key": "sk-ant-api03-validkey1234567"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_anthropic_key"] is True
        assert data["anthropic_key_preview"] is not None
        # Verify actually persisted
        mock_tenant.ensure_default_tenant()
        stored = mock_tenant.get_anthropic_api_key("default")
        assert stored == "sk-ant-api03-validkey1234567"

    def test_update_settings_key_too_short_rejected(self, client):
        """Keys shorter than 10 characters fail validation."""
        resp = client.put(
            f"{BASE}/settings",
            json={"anthropic_api_key": "short"},
        )
        assert resp.status_code == 422

    def test_update_settings_empty_key_rejected(self, client):
        """Empty string fails validation."""
        resp = client.put(
            f"{BASE}/settings",
            json={"anthropic_api_key": ""},
        )
        assert resp.status_code == 422

    def test_update_settings_replaces_existing_key(self, client, mock_tenant):
        """Calling PUT twice replaces the old key."""
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_anthropic_api_key("default", "sk-ant-old-key-1234567890")
        resp = client.put(
            f"{BASE}/settings",
            json={"anthropic_api_key": "sk-ant-new-key-1234567890"},
        )
        assert resp.status_code == 200
        stored = mock_tenant.get_anthropic_api_key("default")
        assert stored == "sk-ant-new-key-1234567890"

    def test_update_settings_preview_is_masked(self, client):
        """Preview shows first 8 chars + '...' + last 4 chars."""
        resp = client.put(
            f"{BASE}/settings",
            json={"anthropic_api_key": "sk-ant-api03-ABCDEFGH"},
        )
        assert resp.status_code == 200
        preview = resp.json()["anthropic_key_preview"]
        assert preview.startswith("sk-ant-a")
        assert "..." in preview
        assert preview.endswith("EFGH")

    def test_update_settings_missing_body_rejected(self, client):
        """Missing request body is rejected."""
        resp = client.put(f"{BASE}/settings", json={})
        assert resp.status_code == 422


class TestDeleteAnthropicKey:
    def test_delete_key(self, client, mock_tenant):
        """DELETE removes the key and returns has_anthropic_key=False."""
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_anthropic_api_key("default", "sk-ant-api03-key1234567890")
        resp = client.delete(f"{BASE}/settings/anthropic-key")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_anthropic_key"] is False
        assert data["anthropic_key_preview"] is None
        # Verify actually removed
        assert mock_tenant.get_anthropic_api_key("default") is None

    def test_delete_key_when_none_set(self, client):
        """DELETE with no key set is idempotent — returns 200."""
        resp = client.delete(f"{BASE}/settings/anthropic-key")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_anthropic_key"] is False

    def test_delete_then_get_reflects_removal(self, client, mock_tenant):
        """After DELETE, GET also returns has_anthropic_key=False."""
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_anthropic_api_key("default", "sk-ant-api03-key1234567890")
        client.delete(f"{BASE}/settings/anthropic-key")
        resp = client.get(f"{BASE}/settings")
        assert resp.status_code == 200
        assert resp.json()["has_anthropic_key"] is False


# ── OpenAI key endpoints ───────────────────────────────────────────────────────

class TestOpenAIKey:
    def test_set_openai_key(self, client, mock_tenant):
        """PUT /openai-key stores the key and returns configured=True."""
        resp = client.put(
            f"{BASE}/settings/openai-key",
            json={"api_key": "sk-proj-validopenaikey123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["openai"]["configured"] is True
        assert data["openai"]["preview"] is not None
        assert "..." in data["openai"]["preview"]
        # Verify persisted
        mock_tenant.ensure_default_tenant()
        assert mock_tenant.get_openai_api_key("default") == "sk-proj-validopenaikey123"

    def test_set_openai_key_too_short_rejected(self, client):
        resp = client.put(f"{BASE}/settings/openai-key", json={"api_key": "short"})
        assert resp.status_code == 422

    def test_openai_key_preview_is_masked(self, client):
        resp = client.put(
            f"{BASE}/settings/openai-key",
            json={"api_key": "sk-proj-ABCDEFGH1234"},
        )
        assert resp.status_code == 200
        preview = resp.json()["openai"]["preview"]
        assert preview.startswith("sk-proj-")
        assert "..." in preview

    def test_delete_openai_key(self, client, mock_tenant):
        """DELETE /openai-key removes the key."""
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_openai_api_key("default", "sk-proj-key12345678")
        resp = client.delete(f"{BASE}/settings/openai-key")
        assert resp.status_code == 200
        data = resp.json()
        assert data["openai"]["configured"] is False
        assert data["openai"]["preview"] is None
        assert mock_tenant.get_openai_api_key("default") is None

    def test_delete_openai_key_idempotent(self, client):
        """DELETE with no key set returns 200."""
        resp = client.delete(f"{BASE}/settings/openai-key")
        assert resp.status_code == 200
        assert resp.json()["openai"]["configured"] is False

    def test_setting_openai_key_does_not_affect_anthropic(self, client, mock_tenant):
        """OpenAI and Anthropic keys are stored independently."""
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_anthropic_api_key("default", "sk-ant-api03-already-set1234")
        client.put(f"{BASE}/settings/openai-key", json={"api_key": "sk-proj-newkey12345"})
        resp = client.get(f"{BASE}/settings")
        data = resp.json()
        assert data["anthropic"]["configured"] is True
        assert data["openai"]["configured"] is True


# ── Gemini key endpoints ───────────────────────────────────────────────────────

class TestGeminiKey:
    def test_set_gemini_key(self, client, mock_tenant):
        """PUT /gemini-key stores the key and returns configured=True."""
        resp = client.put(
            f"{BASE}/settings/gemini-key",
            json={"api_key": "AIzaSy-validgeminikey1234"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["gemini"]["configured"] is True
        assert data["gemini"]["preview"] is not None
        mock_tenant.ensure_default_tenant()
        assert mock_tenant.get_gemini_api_key("default") == "AIzaSy-validgeminikey1234"

    def test_set_gemini_key_too_short_rejected(self, client):
        resp = client.put(f"{BASE}/settings/gemini-key", json={"api_key": "short"})
        assert resp.status_code == 422

    def test_gemini_key_preview_is_masked(self, client):
        resp = client.put(
            f"{BASE}/settings/gemini-key",
            json={"api_key": "AIzaSyABCDEFGH1234"},
        )
        assert resp.status_code == 200
        preview = resp.json()["gemini"]["preview"]
        assert preview.startswith("AIzaSyAB")
        assert "..." in preview

    def test_delete_gemini_key(self, client, mock_tenant):
        """DELETE /gemini-key removes the key."""
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_gemini_api_key("default", "AIzaSy-key123456789")
        resp = client.delete(f"{BASE}/settings/gemini-key")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gemini"]["configured"] is False
        assert mock_tenant.get_gemini_api_key("default") is None

    def test_delete_gemini_key_idempotent(self, client):
        resp = client.delete(f"{BASE}/settings/gemini-key")
        assert resp.status_code == 200
        assert resp.json()["gemini"]["configured"] is False

    def test_all_three_providers_independent(self, client, mock_tenant):
        """All three keys can be set independently and reported correctly."""
        mock_tenant.ensure_default_tenant()
        client.put(f"{BASE}/settings/anthropic-key", json={"api_key": "sk-ant-api03-key1234"})
        client.put(f"{BASE}/settings/openai-key",    json={"api_key": "sk-proj-key12345678"})
        client.put(f"{BASE}/settings/gemini-key",    json={"api_key": "AIzaSy-key12345678"})

        resp = client.get(f"{BASE}/settings")
        data = resp.json()
        assert data["anthropic"]["configured"] is True
        assert data["openai"]["configured"] is True
        assert data["gemini"]["configured"] is True
        # Legacy field must also reflect Anthropic
        assert data["has_anthropic_key"] is True


# ── Response shape after mixed operations ──────────────────────────────────────

class TestResponseShape:
    def test_provider_status_structure(self, client):
        """Each provider object has exactly 'configured' and 'preview' keys."""
        resp = client.get(f"{BASE}/settings")
        data = resp.json()
        for provider in ("anthropic", "openai", "gemini"):
            assert set(data[provider].keys()) == {"configured", "preview"}

    def test_legacy_fields_always_present(self, client):
        """Legacy has_anthropic_key and anthropic_key_preview always returned."""
        resp = client.get(f"{BASE}/settings")
        data = resp.json()
        assert "has_anthropic_key" in data
        assert "anthropic_key_preview" in data

    def test_legacy_fields_match_anthropic_provider(self, client, mock_tenant):
        """Legacy fields are in sync with anthropic provider object."""
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_anthropic_api_key("default", "sk-ant-api03-synctest1234")
        resp = client.get(f"{BASE}/settings")
        data = resp.json()
        assert data["has_anthropic_key"] == data["anthropic"]["configured"]
        assert data["anthropic_key_preview"] == data["anthropic"]["preview"]


# ── Selected model / model catalogue endpoints ────────────────────────────────


class TestListAvailableModels:
    """GET /account/settings/models — returns the public model catalogue."""

    def test_returns_200(self, client):
        resp = client.get(f"{BASE}/settings/models")
        assert resp.status_code == 200

    def test_response_has_models_and_default(self, client):
        resp = client.get(f"{BASE}/settings/models")
        data = resp.json()
        assert "models" in data and isinstance(data["models"], list)
        assert "default_model" in data and isinstance(data["default_model"], str)

    def test_models_include_all_three_providers(self, client):
        resp = client.get(f"{BASE}/settings/models")
        data = resp.json()
        providers = {m["provider"] for m in data["models"]}
        assert providers == {"anthropic", "openai", "gemini"}

    def test_each_model_has_required_fields(self, client):
        resp = client.get(f"{BASE}/settings/models")
        data = resp.json()
        assert len(data["models"]) >= 3
        for m in data["models"]:
            assert set(m.keys()) >= {"id", "name", "description", "provider"}
            assert m["provider"] in ("anthropic", "openai", "gemini")

    def test_default_model_is_in_list(self, client):
        resp = client.get(f"{BASE}/settings/models")
        data = resp.json()
        ids = {m["id"] for m in data["models"]}
        assert data["default_model"] in ids

    def test_endpoint_is_public_no_auth_needed(self, client, monkeypatch):
        """Model catalogue is metadata — no tenant context required."""
        from app.config import settings
        monkeypatch.setattr(settings, "rag_require_auth", True)
        resp = client.get(f"{BASE}/settings/models")
        assert resp.status_code == 200


class TestSetSelectedModel:
    """PUT /account/settings/selected-model — tenant's active model."""

    def test_set_valid_anthropic_model(self, client, mock_tenant):
        mock_tenant.ensure_default_tenant()
        resp = client.put(
            f"{BASE}/settings/selected-model",
            json={"model_id": "claude-haiku-4-5-20251001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["selected_model"] == "claude-haiku-4-5-20251001"
        assert data["selected_provider"] == "anthropic"

    def test_set_valid_openai_model_updates_selected_provider(self, client, mock_tenant):
        mock_tenant.ensure_default_tenant()
        resp = client.put(
            f"{BASE}/settings/selected-model",
            json={"model_id": "gpt-4.1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["selected_model"] == "gpt-4.1"
        assert data["selected_provider"] == "openai"

    def test_set_valid_gemini_model_updates_selected_provider(self, client, mock_tenant):
        mock_tenant.ensure_default_tenant()
        resp = client.put(
            f"{BASE}/settings/selected-model",
            json={"model_id": "gemini-2.5-flash"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["selected_model"] == "gemini-2.5-flash"
        assert data["selected_provider"] == "gemini"

    def test_set_unknown_model_returns_400(self, client, mock_tenant):
        mock_tenant.ensure_default_tenant()
        resp = client.put(
            f"{BASE}/settings/selected-model",
            json={"model_id": "gpt-9000-fantasy"},
        )
        assert resp.status_code == 400
        assert "Unknown model" in resp.json()["detail"] or "unknown" in resp.json()["detail"].lower()

    def test_selection_persists_and_reflects_in_get_settings(self, client, mock_tenant):
        mock_tenant.ensure_default_tenant()
        client.put(
            f"{BASE}/settings/selected-model",
            json={"model_id": "gpt-4.1-mini"},
        )
        resp = client.get(f"{BASE}/settings")
        data = resp.json()
        assert data["selected_model"] == "gpt-4.1-mini"
        assert data["selected_provider"] == "openai"

    def test_missing_model_id_returns_422(self, client):
        resp = client.put(f"{BASE}/settings/selected-model", json={})
        assert resp.status_code == 422

    def test_empty_model_id_returns_422(self, client):
        """Pydantic min_length=1 guards against empty strings."""
        resp = client.put(
            f"{BASE}/settings/selected-model",
            json={"model_id": ""},
        )
        assert resp.status_code == 422


class TestAccountSettingsIncludesSelectedModel:
    """After the multi-provider refactor, GET /account/settings returns
    the tenant's selected_model + selected_provider alongside legacy fields.
    """

    def test_default_selected_model_present_for_new_tenant(self, client):
        resp = client.get(f"{BASE}/settings")
        data = resp.json()
        assert "selected_model" in data
        assert "selected_provider" in data

    def test_default_selected_model_is_anthropic(self, client):
        """Fresh tenant falls back to the default claude model."""
        resp = client.get(f"{BASE}/settings")
        data = resp.json()
        assert data["selected_provider"] == "anthropic"
        # Default model id should be a claude-* id
        assert data["selected_model"].startswith("claude-")
