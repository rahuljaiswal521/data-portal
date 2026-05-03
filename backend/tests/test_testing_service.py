"""Unit tests for TestingService._persist_single_tc_result and run_single_tc.

These tests exercise the new disk-persistence behaviour introduced to fix the
bug where single-TC results were never written to disk, causing SWR
revalidation to fetch a stale CANCELLED status from the previous suite run.

Strategy:
- Monkeypatch TESTING_ROOT so all file I/O goes to tmp_path (no real disk side-effects)
- Use a real TestingService instance with a mocked DatabricksService
- Keep mocks minimal — only patch external I/O that we don't want to hit
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.testing import (
    TestCaseResult,
    TestRunResult,
    TestRunSummary,
)
from app.services.config_service import ConfigService
from app.services.databricks_service import DatabricksService
from app.services.testing_service import TestingService


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def testing_root(tmp_path):
    """Isolated TESTING_ROOT directory for all file I/O."""
    root = tmp_path / "testing"
    (root / "suites").mkdir(parents=True)
    (root / "results").mkdir(parents=True)
    return root


@pytest.fixture
def svc(testing_root, config_svc):
    """Real TestingService with mocked Databricks and patched TESTING_ROOT."""
    mock_db = MagicMock(spec=DatabricksService)
    mock_db.available = False
    service = TestingService(config_svc, mock_db)
    # Patch the module-level constant so all path operations use tmp_path
    with patch("app.services.testing_service.TESTING_ROOT", testing_root):
        yield service


def _make_tc_result(tc_id="TC001", status="PASSED") -> TestCaseResult:
    return TestCaseResult(
        id=tc_id,
        name=f"Test {tc_id}",
        category="insert",
        positive=True,
        status=status,
        duration_seconds=1.5,
        assertions=[],
    )


def _make_run_result(source_name: str, testing_root: Path, tc_ids=None, status="PASSED") -> TestRunResult:
    """Create a TestRunResult and write it to the results directory."""
    tc_ids = tc_ids or ["TC001"]
    run_id = str(uuid.uuid4())
    test_cases = [
        TestCaseResult(
            id=tc_id,
            name=f"Test {tc_id}",
            category="insert",
            positive=True,
            status=status,
            duration_seconds=1.0,
        )
        for tc_id in tc_ids
    ]
    result = TestRunResult(
        run_id=run_id,
        source_name=source_name,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        duration_seconds=2.0,
        overall_status=status,
        environment="dev",
        summary=TestRunSummary(total=len(tc_ids), passed=len(tc_ids), failed=0, skipped=0),
        test_cases=test_cases,
    )
    results_dir = testing_root / "results" / source_name
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / f"{run_id}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result


# ── Tests for _persist_single_tc_result ─────────────────────────────────────


class TestPersistSingleTcResult:
    """Tests for TestingService._persist_single_tc_result."""

    def test_creates_new_record_when_no_prior_run_exists(self, svc, testing_root):
        """When no prior run file exists, a new minimal TestRunResult is created."""
        source = "new_source_persist"
        tc_result = _make_tc_result("TC001", "PASSED")

        svc._persist_single_tc_result(source, tc_result, environment="dev")

        results_dir = testing_root / "results" / source
        files = list(results_dir.glob("*.json"))
        assert len(files) == 1, "Expected exactly one result file to be created"

        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["source_name"] == source
        assert data["overall_status"] == "PASSED"
        assert data["summary"]["total"] == 1
        assert data["summary"]["passed"] == 1
        assert data["summary"]["failed"] == 0
        assert len(data["test_cases"]) == 1
        assert data["test_cases"][0]["id"] == "TC001"
        assert data["test_cases"][0]["status"] == "PASSED"

    def test_creates_failed_summary_when_tc_fails(self, svc, testing_root):
        """When tc_result.status is FAILED, the new record summary shows failed=1."""
        source = "fail_persist_source"
        tc_result = _make_tc_result("TC001", "FAILED")

        svc._persist_single_tc_result(source, tc_result, environment="dev")

        results_dir = testing_root / "results" / source
        files = list(results_dir.glob("*.json"))
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["overall_status"] == "FAILED"
        assert data["summary"]["passed"] == 0
        assert data["summary"]["failed"] == 1

    def test_merges_result_into_existing_run_when_tc_already_present(self, svc, testing_root):
        """When a prior run exists with TC001, the updated TC result is written to a NEW file.

        The new file gets a fresh UUID so any background suite thread writing to
        the old file cannot overwrite the result.
        """
        source = "merge_existing_source"
        existing = _make_run_result(source, testing_root, tc_ids=["TC001", "TC002"], status="PASSED")

        new_tc_result = _make_tc_result("TC001", "FAILED")
        svc._persist_single_tc_result(source, new_tc_result, environment="dev")

        results_dir = testing_root / "results" / source
        files = list(results_dir.glob("*.json"))
        assert len(files) == 2, "A new result file should be created (new UUID), leaving the old one intact"

        # The newest file (by mtime) is the one written by _persist_single_tc_result
        newest = max(files, key=lambda p: p.stat().st_mtime)
        data = json.loads(newest.read_text(encoding="utf-8"))
        assert data["run_id"] != existing.run_id, "New file must have a different run_id"
        tc_map = {tc["id"]: tc for tc in data["test_cases"]}
        assert tc_map["TC001"]["status"] == "FAILED", "TC001 status should be updated to FAILED"
        assert tc_map["TC002"]["status"] == "PASSED", "TC002 status should remain unchanged"

    def test_appends_result_when_tc_not_in_existing_run(self, svc, testing_root):
        """When a prior run exists but does NOT include this TC, the result is appended in a new file."""
        source = "append_tc_source"
        _make_run_result(source, testing_root, tc_ids=["TC001"], status="PASSED")

        new_tc_result = _make_tc_result("TC005", "PASSED")
        svc._persist_single_tc_result(source, new_tc_result, environment="dev")

        results_dir = testing_root / "results" / source
        files = list(results_dir.glob("*.json"))
        assert len(files) == 2, "A new result file should be created"
        # Read the newest file
        newest = max(files, key=lambda p: p.stat().st_mtime)
        data = json.loads(newest.read_text(encoding="utf-8"))
        tc_ids = [tc["id"] for tc in data["test_cases"]]
        assert "TC001" in tc_ids
        assert "TC005" in tc_ids

    def test_does_not_raise_on_error(self, svc, testing_root):
        """Errors in _persist_single_tc_result are caught and logged, never raised."""
        tc_result = _make_tc_result("TC001", "PASSED")
        # Force an error by making get_latest_result raise
        with patch.object(svc, "get_latest_result", side_effect=RuntimeError("disk error")):
            # Should not raise — errors are swallowed and logged
            svc._persist_single_tc_result("some_source", tc_result, environment="dev")

    def test_creates_new_file_with_uuid_run_id(self, svc, testing_root):
        """The new record created when no prior run exists gets a valid UUID run_id."""
        source = "uuid_check_source"
        tc_result = _make_tc_result("TC001", "PASSED")
        svc._persist_single_tc_result(source, tc_result, environment="dev")

        results_dir = testing_root / "results" / source
        files = list(results_dir.glob("*.json"))
        data = json.loads(files[0].read_text(encoding="utf-8"))
        # Should be a valid UUID (no exception raised)
        uuid.UUID(data["run_id"])

    def test_environment_is_stored_in_new_record(self, svc, testing_root):
        """The environment string is propagated to the new record when no prior run exists."""
        source = "env_store_source"
        tc_result = _make_tc_result("TC001", "PASSED")
        svc._persist_single_tc_result(source, tc_result, environment="staging")

        results_dir = testing_root / "results" / source
        files = list(results_dir.glob("*.json"))
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["environment"] == "staging"


# ── Tests for run_single_tc calls _persist_single_tc_result ─────────────────


class TestRunSingleTcPersists:
    """Verify that run_single_tc calls _persist_single_tc_result before returning."""

    def _make_suite_yaml(self, testing_root: Path, source: str) -> None:
        """Write a minimal suite YAML so get_suite() returns a real TestSuite."""
        suite_data = {
            "source_name": source,
            "source_type": "file",
            "primary_keys": ["id"],
            "target_table": f"dev.bronze.{source}",
            "test_catalog": "dev",
            "test_schema": "bronze_test",
            "test_cases": [
                {
                    "id": "TC001",
                    "name": "Basic insert test",
                    "category": "insert",
                    "positive": True,
                    "data_file": None,
                    "setup_data_file": None,
                    "setup": [],
                    "teardown": [],
                    "assertions": [],
                }
            ],
        }
        import yaml
        suite_path = testing_root / "suites" / f"{source}.yaml"
        suite_path.write_text(yaml.dump(suite_data), encoding="utf-8")

    def test_run_single_tc_calls_persist(self, svc, testing_root):
        """run_single_tc must call _persist_single_tc_result exactly once."""
        source = "persist_call_source"
        self._make_suite_yaml(testing_root, source)

        fake_tc_result = _make_tc_result("TC001", "PASSED")

        with patch.object(svc, "_run_test_case", return_value=fake_tc_result), \
             patch.object(svc, "_ensure_test_job"), \
             patch.object(svc, "_persist_single_tc_result") as mock_persist:

            result = svc.run_single_tc(source, "TC001", environment="dev")

            mock_persist.assert_called_once_with(source, fake_tc_result, "dev")

    def test_run_single_tc_persist_receives_correct_tc_result(self, svc, testing_root):
        """The tc_result passed to _persist_single_tc_result is the one returned by _run_test_case."""
        source = "persist_value_source"
        self._make_suite_yaml(testing_root, source)

        fake_tc_result = _make_tc_result("TC001", "PASSED")

        captured_args = []

        def capture_persist(sn, tc_res, env):
            captured_args.append((sn, tc_res, env))

        with patch.object(svc, "_run_test_case", return_value=fake_tc_result), \
             patch.object(svc, "_ensure_test_job"), \
             patch.object(svc, "_persist_single_tc_result", side_effect=capture_persist):

            svc.run_single_tc(source, "TC001", environment="dev")

        assert len(captured_args) == 1
        sn, tc_res, env = captured_args[0]
        assert sn == source
        assert tc_res.id == "TC001"
        assert tc_res.status == "PASSED"
        assert env == "dev"

    def test_run_single_tc_returns_tc_result(self, svc, testing_root):
        """run_single_tc returns the TestCaseResult (not None) after persisting."""
        source = "return_value_source"
        self._make_suite_yaml(testing_root, source)

        fake_tc_result = _make_tc_result("TC001", "PASSED")

        with patch.object(svc, "_run_test_case", return_value=fake_tc_result), \
             patch.object(svc, "_ensure_test_job"), \
             patch.object(svc, "_persist_single_tc_result"):

            result = svc.run_single_tc(source, "TC001", environment="dev")

        assert result is fake_tc_result

    def test_run_single_tc_raises_for_unknown_source(self, svc, testing_root):
        """run_single_tc raises ValueError when the source has no suite."""
        with pytest.raises(ValueError, match="No test suite found"):
            svc.run_single_tc("nonexistent_source", "TC001")

    def test_run_single_tc_raises_for_unknown_tc_id(self, svc, testing_root):
        """run_single_tc raises ValueError when the tc_id is not in the suite."""
        source = "unknown_tc_source"
        self._make_suite_yaml(testing_root, source)

        with patch.object(svc, "_ensure_test_job"):
            with pytest.raises(ValueError, match="TC999"):
                svc.run_single_tc(source, "TC999")
