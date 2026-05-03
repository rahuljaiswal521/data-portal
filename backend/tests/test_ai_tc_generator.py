"""Tests for AI test case generator endpoints.

Covers:
- POST /api/v1/testing/suites/{source_name}/ai-generate
- POST /api/v1/testing/suites/{source_name}/ai-confirm

Strategy:
- Override get_testing_service and get_tc_generator_service via dependency_overrides
- Mock TcGeneratorService with controlled return values / side effects
- Use real TestingService with mock Databricks for suite-existence checks where needed
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_tc_generator_service, get_tenant_service, get_testing_service
from app.main import app
from app.models.testing import (
    AssertionResult,
    AssertionSpec,
    TcConfirmResponse,
    TcGeneratePreview,
    TestCaseResult,
    TestSuite,
)
from app.services.tc_generator_service import TcGeneratorService
from app.services.tenant_service import TenantService
from app.services.testing_service import TestingService

TESTING_BASE = "/api/v1/testing/suites"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_preview() -> TcGeneratePreview:
    return TcGeneratePreview(
        tc_id="TC009",
        name="Ensure status column only accepts valid values",
        category="data_quality",
        positive=False,
        setup=["truncate_test_table"],
        teardown=[],
        assertions=[
            AssertionSpec(
                type="row_count",
                sql="SELECT COUNT(*) FROM dev.bronze_test.crm_customers WHERE status NOT IN ('active','inactive','pending')",
                expected=0,
                description="No records with invalid status should reach the main table",
            )
        ],
        data_file_name="tc009_invalid_status.json",
        data_records=[
            {"id": "C001", "name": "Alice", "status": "banned"},
            {"id": "C002", "name": "Bob", "status": "pending"},
        ],
        explanation="Tests that records with an invalid status value are quarantined.",
    )


def _make_confirm_response() -> TcConfirmResponse:
    return TcConfirmResponse(
        tc_id="TC009",
        data_file="tc009_invalid_status.json",
        message="Test case TC009 added to suite and executed.",
        result=TestCaseResult(
            id="TC009",
            name="Ensure status column only accepts valid values",
            category="data_quality",
            positive=False,
            status="PASSED",
            duration_seconds=3.2,
            assertions=[
                AssertionResult(
                    type="row_count",
                    description="No records with invalid status should reach the main table",
                    expected=0,
                    actual=0,
                    passed=True,
                    sql="SELECT COUNT(*) FROM ...",
                )
            ],
        ),
    )


def _make_suite() -> TestSuite:
    return TestSuite(
        source_name="crm_customers",
        source_type="file",
        primary_keys=["id"],
        target_table="dev.bronze.crm_customers",
        test_catalog="dev",
        test_schema="bronze_test",
        test_cases=[],
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_gen_svc_unavailable():
    """TcGeneratorService where .available returns False (no API key)."""
    mock = MagicMock(spec=TcGeneratorService)
    mock.available = False
    return mock


@pytest.fixture
def mock_gen_svc_available():
    """TcGeneratorService where .available returns True and generate_preview succeeds."""
    mock = MagicMock(spec=TcGeneratorService)
    mock.available = True
    mock.generate_preview.return_value = _make_preview()
    mock.confirm_and_run.return_value = _make_confirm_response()
    return mock


@pytest.fixture
def mock_testing_with_suite():
    """TestingService mock that returns a real suite for 'crm_customers'."""
    mock = MagicMock(spec=TestingService)
    mock.get_suite.return_value = _make_suite()
    return mock


@pytest.fixture
def mock_testing_no_suite():
    """TestingService mock that returns None (suite not found)."""
    mock = MagicMock(spec=TestingService)
    mock.get_suite.return_value = None
    return mock


def _make_mock_tenant(api_key=None):
    """Build a TenantService mock with a controlled anthropic_api_key return value."""
    mock = MagicMock(spec=TenantService)
    mock.ensure_default_tenant.return_value = "default"
    mock.validate_api_key.return_value = None
    mock.get_anthropic_api_key.return_value = api_key
    return mock


def _make_client(gen_svc, test_svc, tenant_svc=None) -> TestClient:
    """Build a TestClient with the given service mocks injected."""
    if tenant_svc is None:
        tenant_svc = _make_mock_tenant()
    overrides = {
        get_tc_generator_service: lambda: gen_svc,
        get_testing_service: lambda: test_svc,
        get_tenant_service: lambda: tenant_svc,
    }
    app.dependency_overrides.update(overrides)
    client = TestClient(app)
    return client


# ── ai-generate endpoint ──────────────────────────────────────────────────────


class TestAiGenerateTc:
    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_ai_generate_tc_no_key_returns_503(
        self, mock_testing_with_suite
    ):
        """When no provider key is configured for the selected model, service
        raises RuntimeError and the route converts it to 503.
        """
        # The route no longer pre-fetches a key — it invokes the service and
        # the service raises RuntimeError(NoApiKeyError) when no key is set.
        gen_svc = MagicMock(spec=TcGeneratorService)
        gen_svc.available = False
        gen_svc.generate_preview.side_effect = RuntimeError(
            "No Anthropic API key configured for tenant 'default'"
        )
        client = _make_client(gen_svc, mock_testing_with_suite)
        resp = client.post(
            f"{TESTING_BASE}/crm_customers/ai-generate",
            json={"prompt": "Test that null ids are quarantined"},
        )
        assert resp.status_code == 503
        assert "Anthropic API key" in resp.json()["detail"]

    def test_ai_generate_tc_suite_not_found_returns_404(
        self, mock_gen_svc_available, mock_testing_no_suite
    ):
        """When no suite exists for the source, the endpoint returns 404."""
        tenant_svc = _make_mock_tenant(api_key="sk-ant-tenant-key-xyz1234567890")
        client = _make_client(mock_gen_svc_available, mock_testing_no_suite, tenant_svc)
        resp = client.post(
            f"{TESTING_BASE}/nonexistent_source/ai-generate",
            json={"prompt": "Any prompt"},
        )
        assert resp.status_code == 404
        assert "nonexistent_source" in resp.json()["detail"]

    def test_ai_generate_tc_success_returns_200_with_preview(
        self, mock_gen_svc_available, mock_testing_with_suite
    ):
        """A valid request with API key and existing suite returns 200 + TcGeneratePreview."""
        tenant_svc = _make_mock_tenant(api_key="sk-ant-tenant-key-xyz1234567890")
        client = _make_client(mock_gen_svc_available, mock_testing_with_suite, tenant_svc)
        resp = client.post(
            f"{TESTING_BASE}/crm_customers/ai-generate",
            json={"prompt": "Ensure status column only accepts: active, inactive, pending"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Verify all TcGeneratePreview fields are present
        assert data["tc_id"] == "TC009"
        assert data["name"] == "Ensure status column only accepts valid values"
        assert data["category"] == "data_quality"
        assert data["positive"] is False
        assert isinstance(data["assertions"], list)
        assert len(data["assertions"]) == 1
        assert data["assertions"][0]["type"] == "row_count"
        assert data["assertions"][0]["expected"] == 0
        assert data["data_file_name"] == "tc009_invalid_status.json"
        assert isinstance(data["data_records"], list)
        assert len(data["data_records"]) == 2
        assert isinstance(data["explanation"], str)

    def test_ai_generate_tc_calls_generate_preview_with_correct_args(
        self, mock_gen_svc_available, mock_testing_with_suite
    ):
        """generate_preview is called with source_name, prompt, and tenant_id."""
        client = _make_client(mock_gen_svc_available, mock_testing_with_suite)
        prompt_text = "Check that duplicate IDs are deduplicated"
        client.post(
            f"{TESTING_BASE}/crm_customers/ai-generate",
            json={"prompt": prompt_text},
        )
        mock_gen_svc_available.generate_preview.assert_called_once_with(
            "crm_customers", prompt_text, tenant_id="default"
        )

    def test_ai_generate_tc_forwards_tenant_id(
        self, mock_gen_svc_available, mock_testing_with_suite
    ):
        """The route forwards tenant_id (not api_key) — the service resolves
        the provider key via ai_client_service based on the selected model.
        """
        client = _make_client(mock_gen_svc_available, mock_testing_with_suite)
        client.post(
            f"{TESTING_BASE}/crm_customers/ai-generate",
            json={"prompt": "check nulls"},
        )
        call_kwargs = mock_gen_svc_available.generate_preview.call_args
        assert "api_key" not in call_kwargs.kwargs
        assert call_kwargs.kwargs.get("tenant_id") == "default"

    def test_ai_generate_tc_no_server_key_but_tenant_key_succeeds(
        self, mock_testing_with_suite
    ):
        """When server has no key but tenant has one, request succeeds (not 503)."""
        gen_svc_unavailable = MagicMock(spec=TcGeneratorService)
        gen_svc_unavailable.available = False
        gen_svc_unavailable.generate_preview.return_value = _make_preview()
        tenant_svc = _make_mock_tenant(api_key="sk-ant-tenant-only-key123456")
        client = _make_client(gen_svc_unavailable, mock_testing_with_suite, tenant_svc)
        resp = client.post(
            f"{TESTING_BASE}/crm_customers/ai-generate",
            json={"prompt": "any prompt"},
        )
        assert resp.status_code == 200

    def test_ai_generate_tc_service_exception_returns_500(
        self, mock_gen_svc_available, mock_testing_with_suite
    ):
        """If generate_preview raises an unexpected exception, endpoint returns 500.

        Note: RuntimeError is now caught as 503 (no-key signal). Other generic
        exceptions still fall through to the 500 catch-all.
        """
        mock_gen_svc_available.generate_preview.side_effect = Exception("Unexpected parse failure")
        tenant_svc = _make_mock_tenant(api_key="sk-ant-tenant-key-xyz1234567890")
        client = _make_client(mock_gen_svc_available, mock_testing_with_suite, tenant_svc)
        resp = client.post(
            f"{TESTING_BASE}/crm_customers/ai-generate",
            json={"prompt": "Some prompt"},
        )
        assert resp.status_code == 500
        assert "AI generation failed" in resp.json()["detail"]

    def test_ai_generate_tc_runtime_error_returns_503(
        self, mock_gen_svc_available, mock_testing_with_suite
    ):
        """RuntimeError from generate_preview signals missing provider key → 503."""
        mock_gen_svc_available.generate_preview.side_effect = RuntimeError(
            "No OpenAI API key configured"
        )
        client = _make_client(mock_gen_svc_available, mock_testing_with_suite)
        resp = client.post(
            f"{TESTING_BASE}/crm_customers/ai-generate",
            json={"prompt": "Some prompt"},
        )
        assert resp.status_code == 503
        assert "OpenAI" in resp.json()["detail"]

    def test_ai_generate_tc_value_error_returns_422(
        self, mock_gen_svc_available, mock_testing_with_suite
    ):
        """If generate_preview raises ValueError, endpoint returns 422."""
        mock_gen_svc_available.generate_preview.side_effect = ValueError("No JSON in response")
        tenant_svc = _make_mock_tenant(api_key="sk-ant-tenant-key-xyz1234567890")
        client = _make_client(mock_gen_svc_available, mock_testing_with_suite, tenant_svc)
        resp = client.post(
            f"{TESTING_BASE}/crm_customers/ai-generate",
            json={"prompt": "Some prompt"},
        )
        assert resp.status_code == 422
        assert "No JSON in response" in resp.json()["detail"]


# ── ai-confirm endpoint ───────────────────────────────────────────────────────


def _confirm_body() -> dict:
    """Build a valid TcConfirmRequest payload."""
    return {
        "tc_id": "TC009",
        "name": "Ensure status column only accepts valid values",
        "category": "data_quality",
        "positive": False,
        "setup": ["truncate_test_table"],
        "teardown": [],
        "assertions": [
            {
                "type": "row_count",
                "sql": "SELECT COUNT(*) FROM dev.bronze_test.crm_customers WHERE status NOT IN ('active','inactive','pending')",
                "expected": 0,
                "description": "No invalid status records in main table",
            }
        ],
        "data_file_name": "tc009_invalid_status.json",
        "data_records": [
            {"id": "C001", "name": "Alice", "status": "banned"},
        ],
    }


class TestAiConfirmTc:
    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_ai_confirm_tc_success_returns_200_with_response(
        self, mock_gen_svc_available, mock_testing_with_suite
    ):
        """A valid confirm request returns 200 + TcConfirmResponse with result."""
        client = _make_client(mock_gen_svc_available, mock_testing_with_suite)
        resp = client.post(
            f"{TESTING_BASE}/crm_customers/ai-confirm",
            json=_confirm_body(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tc_id"] == "TC009"
        assert data["data_file"] == "tc009_invalid_status.json"
        assert "TC009" in data["message"]
        assert data["result"]["status"] == "PASSED"
        assert isinstance(data["result"]["assertions"], list)

    def test_ai_confirm_tc_calls_confirm_and_run(
        self, mock_gen_svc_available, mock_testing_with_suite
    ):
        """confirm_and_run is called once with correct source_name and body."""
        client = _make_client(mock_gen_svc_available, mock_testing_with_suite)
        client.post(
            f"{TESTING_BASE}/crm_customers/ai-confirm",
            json=_confirm_body(),
        )
        assert mock_gen_svc_available.confirm_and_run.call_count == 1
        call_args = mock_gen_svc_available.confirm_and_run.call_args
        assert call_args[0][0] == "crm_customers"  # source_name positional arg

    def test_ai_confirm_tc_duplicate_tc_id_returns_409(
        self, mock_gen_svc_available, mock_testing_with_suite
    ):
        """When confirm_and_run raises ValueError('already exists'), endpoint returns 409."""
        mock_gen_svc_available.confirm_and_run.side_effect = ValueError(
            "Test case 'TC009' already exists in suite 'crm_customers'"
        )
        client = _make_client(mock_gen_svc_available, mock_testing_with_suite)
        resp = client.post(
            f"{TESTING_BASE}/crm_customers/ai-confirm",
            json=_confirm_body(),
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    def test_ai_confirm_tc_suite_not_found_returns_404(
        self, mock_gen_svc_available, mock_testing_with_suite
    ):
        """When confirm_and_run raises ValueError without 'already exists', returns 404."""
        mock_gen_svc_available.confirm_and_run.side_effect = ValueError(
            "No test suite found for 'crm_customers'"
        )
        client = _make_client(mock_gen_svc_available, mock_testing_with_suite)
        resp = client.post(
            f"{TESTING_BASE}/crm_customers/ai-confirm",
            json=_confirm_body(),
        )
        assert resp.status_code == 404
        assert "No test suite" in resp.json()["detail"]

    def test_ai_confirm_tc_service_exception_returns_500(
        self, mock_gen_svc_available, mock_testing_with_suite
    ):
        """Unexpected exceptions from confirm_and_run are returned as 500."""
        mock_gen_svc_available.confirm_and_run.side_effect = RuntimeError("Disk full")
        client = _make_client(mock_gen_svc_available, mock_testing_with_suite)
        resp = client.post(
            f"{TESTING_BASE}/crm_customers/ai-confirm",
            json=_confirm_body(),
        )
        assert resp.status_code == 500
        assert "Failed to add/run test case" in resp.json()["detail"]

    def test_ai_confirm_tc_response_result_fields(
        self, mock_gen_svc_available, mock_testing_with_suite
    ):
        """The nested result object in the response includes all required fields."""
        client = _make_client(mock_gen_svc_available, mock_testing_with_suite)
        resp = client.post(
            f"{TESTING_BASE}/crm_customers/ai-confirm",
            json=_confirm_body(),
        )
        result = resp.json()["result"]
        assert "id" in result
        assert "name" in result
        assert "category" in result
        assert "positive" in result
        assert "status" in result
        assert "assertions" in result
