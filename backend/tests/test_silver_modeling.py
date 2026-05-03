"""Tests for Silver modeling endpoints: profile-table, suggest-model, enterprise-model."""

BASE = "/api/v1/silver/modeling"


class TestProfileTable:
    def test_profile_table_success(self, client, mock_modeling):
        payload = {"catalog": "dev", "schema": "bronze", "table": "orders"}
        resp = client.post(f"{BASE}/profile-table", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["table"] == "dev.bronze.orders"
        assert "row_count" in data
        assert "columns" in data

    def test_profile_table_missing_catalog(self, client):
        payload = {"schema": "bronze", "table": "orders"}
        resp = client.post(f"{BASE}/profile-table", json=payload)
        assert resp.status_code == 422

    def test_profile_table_missing_table(self, client):
        payload = {"catalog": "dev", "schema": "bronze"}
        resp = client.post(f"{BASE}/profile-table", json=payload)
        assert resp.status_code == 422

    def test_profile_table_calls_service(self, client, mock_modeling):
        payload = {"catalog": "dev", "schema": "bronze", "table": "customers"}
        client.post(f"{BASE}/profile-table", json=payload)
        mock_modeling.profile_table.assert_called_once_with("dev", "bronze", "customers")


class TestListBronzeTables:
    def test_list_tables_default_params(self, client, mock_modeling):
        mock_modeling.list_bronze_tables.return_value = [
            {"full_name": "dev.bronze.orders"},
            {"full_name": "dev.bronze.customers"},
        ]
        resp = client.get(f"{BASE}/bronze-tables")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_list_tables_with_params(self, client, mock_modeling):
        resp = client.get(f"{BASE}/bronze-tables?catalog=prod&schema=raw")
        assert resp.status_code == 200
        mock_modeling.list_bronze_tables.assert_called_once_with("prod", "raw")

    def test_list_tables_empty(self, client, mock_modeling):
        mock_modeling.list_bronze_tables.return_value = []
        resp = client.get(f"{BASE}/bronze-tables")
        assert resp.status_code == 200
        assert resp.json() == []


class TestSuggestModel:
    def test_suggest_model_success(self, client, mock_modeling):
        from app.models.silver_modeling import SuggestModelResponse

        mock_modeling.suggest_model.return_value = SuggestModelResponse(
            name="customer",
            domain="customer",
            description="Customer canonical entity",
        )
        payload = {
            "tables": [
                {"full_table_name": "dev.bronze.customers"},
            ],
            "domain_hint": "customer",
            "entity_name_hint": "customer",
        }
        resp = client.post(f"{BASE}/suggest-model", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "customer"
        assert data["domain"] == "customer"

    def test_suggest_model_invalid_table_name(self, client):
        payload = {
            "tables": [{"full_table_name": "bad_name"}],
        }
        resp = client.post(f"{BASE}/suggest-model", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] is not None
        assert "Invalid table name" in data["error"]

    def test_suggest_model_empty_tables(self, client):
        payload = {"tables": []}
        resp = client.post(f"{BASE}/suggest-model", json=payload)
        assert resp.status_code == 200


class TestSuggestEnterpriseModel:
    def test_enterprise_model_success(self, client, mock_modeling):
        from app.models.silver_modeling import (
            DomainSuggestion,
            EnterpriseModelResponse,
            EntitySuggestion,
        )

        mock_modeling.suggest_enterprise_model.return_value = EnterpriseModelResponse(
            domains=[
                DomainSuggestion(
                    domain="customer",
                    schema="slv_customer",
                    entities=[
                        EntitySuggestion(name="customer", description="Customer entity")
                    ],
                )
            ],
            overall_reasoning="Analyzed 2 tables",
        )
        payload = {
            "tables": ["dev.bronze.customers", "dev.bronze.orders"],
            "catalog": "dev",
        }
        resp = client.post(f"{BASE}/suggest-enterprise-model", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["domains"]) == 1
        assert data["domains"][0]["domain"] == "customer"
        assert data["overall_reasoning"] == "Analyzed 2 tables"

    def test_enterprise_model_empty_tables(self, client):
        payload = {"tables": [], "catalog": "dev"}
        resp = client.post(f"{BASE}/suggest-enterprise-model", json=payload)
        assert resp.status_code == 200

    def test_enterprise_model_stream(self, client, mock_modeling):
        def _gen():
            yield "data: {}\n\n"

        mock_modeling.suggest_enterprise_model_stream.return_value = _gen()
        payload = {"tables": ["dev.bronze.orders"], "catalog": "dev"}
        resp = client.post(f"{BASE}/suggest-enterprise-model/stream", json=payload)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")


class TestTenantIdThreading:
    """Verify that the current tenant_id is threaded through to service calls.

    After the multi-provider refactor, the route no longer pre-fetches an
    Anthropic key — it passes the tenant_id and lets ai_client_service resolve
    the correct provider/key based on the tenant's selected model.
    """

    def test_suggest_enterprise_model_passes_tenant_id(
        self, client, mock_modeling, mock_tenant
    ):
        """The route forwards tenant_id (not api_key) to suggest_enterprise_model."""
        mock_tenant.ensure_default_tenant()
        payload = {"tables": ["dev.bronze.orders"], "catalog": "dev"}
        resp = client.post(f"{BASE}/suggest-enterprise-model", json=payload)
        assert resp.status_code == 200
        mock_modeling.suggest_enterprise_model.assert_called_once_with(
            ["dev.bronze.orders"], "dev", tenant_id="default"
        )

    def test_suggest_enterprise_model_does_not_pass_api_key(
        self, client, mock_modeling
    ):
        """The route no longer passes api_key — the service resolves it itself."""
        payload = {"tables": ["dev.bronze.orders"], "catalog": "dev"}
        client.post(f"{BASE}/suggest-enterprise-model", json=payload)
        call_kwargs = mock_modeling.suggest_enterprise_model.call_args
        assert "api_key" not in call_kwargs.kwargs
        assert call_kwargs.kwargs.get("tenant_id") == "default"

    def test_suggest_model_passes_tenant_id(
        self, client, mock_modeling, mock_tenant
    ):
        """The route forwards tenant_id (not api_key) to suggest_model."""
        from app.models.silver_modeling import SuggestModelResponse
        mock_modeling.suggest_model.return_value = SuggestModelResponse(
            name="customer", domain="customer", description="Customer entity"
        )
        mock_tenant.ensure_default_tenant()
        payload = {"tables": [{"full_table_name": "dev.bronze.customers"}]}
        resp = client.post(f"{BASE}/suggest-model", json=payload)
        assert resp.status_code == 200
        call_kwargs = mock_modeling.suggest_model.call_args
        assert "api_key" not in call_kwargs.kwargs
        assert call_kwargs.kwargs.get("tenant_id") == "default"


class TestSuggestModelNoKey:
    """Silver modeling suggest-model returns error when no tenant API key is set."""

    def test_suggest_model_no_key_returns_error_field(self, client, mock_modeling):
        """When no tenant key is set, suggest_model returns a response with error set."""
        from app.models.silver_modeling import SuggestModelResponse

        mock_modeling.suggest_model.return_value = SuggestModelResponse(
            error="AI modeling is not available. Set your Anthropic API key in Settings.",
        )
        payload = {"tables": [{"full_table_name": "dev.bronze.customers"}]}
        resp = client.post(f"{BASE}/suggest-model", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] is not None
        assert "Anthropic API key" in data["error"]

    def test_suggest_model_no_key_passes_none_to_service(self, client, mock_modeling):
        """When no tenant key is configured, api_key=None is passed to suggest_model."""
        from app.models.silver_modeling import SuggestModelResponse

        mock_modeling.suggest_model.return_value = SuggestModelResponse(
            error="AI modeling is not available. Set your Anthropic API key in Settings.",
        )
        payload = {"tables": [{"full_table_name": "dev.bronze.customers"}]}
        client.post(f"{BASE}/suggest-model", json=payload)
        call_kwargs = mock_modeling.suggest_model.call_args
        assert call_kwargs.kwargs.get("api_key") is None

    def test_suggest_enterprise_model_no_key_returns_error_field(
        self, client, mock_modeling
    ):
        """When no tenant key is set, suggest_enterprise_model returns a response with error."""
        from app.models.silver_modeling import EnterpriseModelResponse

        mock_modeling.suggest_enterprise_model.return_value = EnterpriseModelResponse(
            error="AI modeling is not available. Set your Anthropic API key in Settings.",
        )
        payload = {"tables": ["dev.bronze.customers"], "catalog": "dev"}
        resp = client.post(f"{BASE}/suggest-enterprise-model", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] is not None
        assert "Anthropic API key" in data["error"]
