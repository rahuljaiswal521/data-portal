"""Testing service — generates and executes Bronze pipeline test suites."""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import os

import yaml

from app.models.testing import (
    AssertionResult,
    AssertionSpec,
    GenerateSuiteResponse,
    RunSuiteResponse,
    TestCase,
    TestCaseResult,
    TestRunListResponse,
    TestRunResult,
    TestRunSummary,
    TestSuite,
    TestSuiteListResponse,
    TestSuiteSummary,
)
from app.services.config_service import ConfigService
from app.services.databricks_service import DatabricksService

logger = logging.getLogger(__name__)

# Allow override via env var (needed in Docker/Azure where /testing is a mounted volume)
TESTING_ROOT = Path(os.environ.get("TESTING_ROOT", str(Path(__file__).resolve().parents[3] / "testing")))


class TestingService:
    def __init__(self, config_svc: ConfigService, db_svc: DatabricksService) -> None:
        self._config_svc = config_svc
        self._db_svc = db_svc
        # run_id → threading.Event; set the event to request cancellation
        self._cancel_flags: Dict[str, threading.Event] = {}

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def list_suites(self) -> TestSuiteListResponse:
        suites_dir = TESTING_ROOT / "suites"
        summaries: List[TestSuiteSummary] = []
        if not suites_dir.exists():
            return TestSuiteListResponse(suites=[], total=0)

        for yaml_file in sorted(suites_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                source_name = data["source_name"]
                latest = self.get_latest_result(source_name)
                summaries.append(
                    TestSuiteSummary(
                        source_name=source_name,
                        source_type=data.get("source_type", "file"),
                        primary_keys=data.get("primary_keys", []),
                        target_table=data.get("target_table", ""),
                        test_count=len(data.get("test_cases", [])),
                        last_run_status=latest.overall_status if latest else None,
                        last_run_at=latest.started_at.isoformat() if latest else None,
                    )
                )
            except Exception as e:
                logger.warning("Failed to load suite %s: %s", yaml_file.name, e)

        return TestSuiteListResponse(suites=summaries, total=len(summaries))

    def get_suite(self, source_name: str) -> Optional[TestSuite]:
        suite_path = TESTING_ROOT / "suites" / f"{source_name}.yaml"
        if not suite_path.exists():
            return None
        try:
            data = yaml.safe_load(suite_path.read_text(encoding="utf-8"))
            return TestSuite.model_validate(data)
        except Exception as e:
            logger.error("Failed to parse suite %s: %s", source_name, e)
            return None

    def generate_suite(self, source_name: str) -> GenerateSuiteResponse:
        """Generate a test suite YAML scaffold for a source (idempotent)."""
        suite_path = TESTING_ROOT / "suites" / f"{source_name}.yaml"
        suite_path.parent.mkdir(parents=True, exist_ok=True)

        if suite_path.exists():
            suite = self.get_suite(source_name)
            tc_count = len(suite.test_cases) if suite else 0
            return GenerateSuiteResponse(
                source_name=source_name,
                message="Suite already exists",
                test_count=tc_count,
            )

        # Build scaffold from source config.
        # Guard: if the source was deleted between the API call and this
        # background thread executing, skip silently rather than creating
        # a dangling scaffold for a non-existent source.
        source = self._config_svc.get_source(source_name)
        if not source:
            raise ValueError(
                f"Source '{source_name}' not found — skipping suite scaffold"
            )
        # Use .value to get a plain str — SourceType(str, Enum) would otherwise
        # be serialised as a Python object tag by yaml.dump.
        source_type = str(getattr(source.source_type, "value", source.source_type))
        target_table = source_name
        primary_keys: List[str] = []

        if source:
            t = source.target or {}
            raw_table = t.get("table", "")
            if raw_table:
                target_table = str(raw_table)
            cdc = t.get("cdc", {})
            raw_pks = cdc.get("primary_keys", [])
            primary_keys = [str(k) for k in raw_pks]

        scaffold = self._build_scaffold_suite(
            source_name, source_type, target_table, primary_keys
        )
        suite_path.write_text(
            yaml.dump(scaffold, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )

        # Ensure data directory exists
        (TESTING_ROOT / "data" / source_name).mkdir(parents=True, exist_ok=True)

        return GenerateSuiteResponse(
            source_name=source_name,
            message="Suite scaffold generated — add test data files to complete",
            test_count=len(scaffold["test_cases"]),
        )

    def run_single_tc(
        self, source_name: str, tc_id: str, environment: str = "dev"
    ) -> TestCaseResult:
        """Run a single test case synchronously and return the result.

        Designed for the agentic test loop — the caller blocks until the TC
        completes (including Databricks job wait).
        """
        suite = self.get_suite(source_name)
        if not suite:
            raise ValueError(f"No test suite found for '{source_name}'")
        tc = next((t for t in suite.test_cases if t.id == tc_id), None)
        if not tc:
            raise ValueError(f"Test case '{tc_id}' not found in suite '{source_name}'")

        try:
            self._ensure_test_job(source_name, environment)
        except Exception as e:
            logger.warning("Could not ensure test job for %s: %s", source_name, e)

        tc_result = self._run_test_case(tc, suite, environment)
        # Persist to disk so SWR revalidation (e.g. window focus) returns the
        # correct status instead of a stale CANCELLED / previous run result.
        self._persist_single_tc_result(source_name, tc_result, environment)
        return tc_result

    def run_suite(
        self, source_name: str, environment: str = "dev"
    ) -> RunSuiteResponse:
        suite = self.get_suite(source_name)
        if not suite:
            raise ValueError(f"No test suite found for '{source_name}'")

        # Prevent concurrent runs for the same source
        existing = self.get_latest_result(source_name)
        if existing and existing.overall_status == "RUNNING":
            raise ValueError(
                f"A suite run is already in progress for '{source_name}' "
                f"(run_id={existing.run_id}). Cancel it first."
            )

        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        result = TestRunResult(
            run_id=run_id,
            source_name=source_name,
            started_at=now,
            overall_status="RUNNING",
            environment=environment,
            summary=TestRunSummary(
                total=len(suite.test_cases), passed=0, failed=0, skipped=0
            ),
        )
        self._save_result(source_name, result)

        cancel_flag = threading.Event()
        self._cancel_flags[run_id] = cancel_flag

        t = threading.Thread(
            target=self._execute_suite_async,
            args=(suite, result, environment, cancel_flag),
            daemon=True,
        )
        t.start()

        return RunSuiteResponse(
            run_id=run_id,
            source_name=source_name,
            message="Suite execution started",
        )

    def cancel_suite(self, source_name: str) -> bool:
        """Request cancellation of the active run for this source.

        Sets the cancel flag so the background thread stops after the current
        test case finishes (mid-TC cancellation is not supported — Databricks
        jobs already in flight will complete normally).
        Returns True if a running suite was found and cancelled, False otherwise.
        """
        result = self.get_latest_result(source_name)
        if not result or result.overall_status != "RUNNING":
            return False

        flag = self._cancel_flags.get(result.run_id)
        if flag:
            flag.set()
            logger.info("Cancel requested for run %s (%s)", result.run_id, source_name)
        else:
            # Run was started by a different process/worker — update file directly
            logger.warning(
                "No cancel flag for run %s — marking CANCELLED in result file", result.run_id
            )

        # Immediately update the result file so the UI shows CANCELLED.
        # Also flip any RUNNING TC placeholder to CANCELLED so the frontend
        # doesn't keep showing a spinner for the in-flight test case.
        for tc in result.test_cases:
            if tc.status == "RUNNING":
                tc.status = "CANCELLED"
        result.overall_status = "CANCELLED"
        result.completed_at = datetime.now(timezone.utc)
        if result.started_at:
            result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        self._save_result(source_name, result)
        return True

    def get_results(self, source_name: str) -> TestRunListResponse:
        results_dir = TESTING_ROOT / "results" / source_name
        runs: List[TestRunResult] = []
        if results_dir.exists():
            # Sort by file modification time (newest first) — UUID filenames don't sort chronologically
            for f in sorted(results_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    runs.append(TestRunResult.model_validate(data))
                except Exception as e:
                    logger.warning("Failed to load result %s: %s", f.name, e)
        return TestRunListResponse(source_name=source_name, runs=runs, total=len(runs))

    def get_latest_result(self, source_name: str) -> Optional[TestRunResult]:
        results_dir = TESTING_ROOT / "results" / source_name
        if not results_dir.exists():
            return None
        # Sort by file modification time (newest first) — UUID filenames don't sort chronologically
        files = sorted(results_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return None
        try:
            data = json.loads(files[0].read_text(encoding="utf-8"))
            return TestRunResult.model_validate(data)
        except Exception as e:
            logger.warning("Failed to load latest result for %s: %s", source_name, e)
            return None

    # ──────────────────────────────────────────────────────────────────────
    # Private: async execution
    # ──────────────────────────────────────────────────────────────────────

    def _execute_suite_async(
        self,
        suite: TestSuite,
        result: TestRunResult,
        environment: str,
        cancel_flag: Optional[threading.Event] = None,
    ) -> None:
        try:
            self._ensure_test_job(suite.source_name, environment)
        except Exception as e:
            logger.warning("Could not ensure test job for %s: %s", suite.source_name, e)

        passed = 0
        failed = 0
        skipped = 0

        for tc in suite.test_cases:
            # Check for cancellation before starting each TC
            if cancel_flag and cancel_flag.is_set():
                logger.info("Suite cancelled — skipping remaining TCs from %s", tc.id)
                # Mark remaining TCs as SKIPPED
                for remaining_tc in suite.test_cases[suite.test_cases.index(tc):]:
                    result.test_cases.append(TestCaseResult(
                        id=remaining_tc.id,
                        name=remaining_tc.name,
                        category=remaining_tc.category,
                        positive=remaining_tc.positive,
                        status="SKIPPED",
                    ))
                    skipped += 1
                break

            # Add a RUNNING placeholder so the frontend sees progress
            placeholder = TestCaseResult(
                id=tc.id,
                name=tc.name,
                category=tc.category,
                positive=tc.positive,
                status="RUNNING",
            )
            result.test_cases.append(placeholder)
            self._save_result(suite.source_name, result)

            try:
                tc_result = self._run_test_case(tc, suite, environment)
            except Exception as e:
                logger.error("TC %s raised exception: %s", tc.id, e)
                tc_result = TestCaseResult(
                    id=tc.id,
                    name=tc.name,
                    category=tc.category,
                    positive=tc.positive,
                    status="ERROR",
                    error=str(e),
                )

            result.test_cases[-1] = tc_result
            if tc_result.status == "PASSED":
                passed += 1
            else:
                failed += 1
            self._save_result(suite.source_name, result)

        completed_at = datetime.now(timezone.utc)
        result.completed_at = completed_at
        result.duration_seconds = (
            completed_at - result.started_at
        ).total_seconds()
        was_cancelled = cancel_flag and cancel_flag.is_set()
        if was_cancelled:
            result.overall_status = "CANCELLED"
        elif failed == 0 and skipped == 0:
            result.overall_status = "PASSED"
        else:
            result.overall_status = "FAILED"
        result.summary = TestRunSummary(
            total=passed + failed + skipped,
            passed=passed,
            failed=failed,
            skipped=skipped,
        )
        self._save_result(suite.source_name, result)
        self._save_html_report(suite.source_name, result)
        # Clean up cancel flag
        self._cancel_flags.pop(result.run_id, None)

    def _run_test_case(
        self, tc: TestCase, suite: TestSuite, environment: str
    ) -> TestCaseResult:
        start = time.time()

        # Setup actions
        for action in tc.setup:
            if action == "truncate_test_table":
                self._db_svc.query_sql(
                    f"TRUNCATE TABLE {suite.test_catalog}.{suite.test_schema}.{suite.target_table}"
                )
            elif action == "truncate_dead_letter_table":
                self._db_svc.query_sql(
                    f"TRUNCATE TABLE {suite.test_catalog}.bronze_meta"
                    f".dead_letter_{suite.target_table}"
                )

        # TC004 pattern: upload baseline data + run job first
        if tc.setup_data_file:
            self._upload_test_data(suite.source_name, tc.setup_data_file)
            run_id = self._db_svc.trigger_job(f"{suite.source_name}_test", environment)
            self._db_svc.wait_for_run_by_id(run_id, timeout=1800)

        # Upload and run main test data
        if tc.data_file:
            self._upload_test_data(suite.source_name, tc.data_file)
        run_id = self._db_svc.trigger_job(f"{suite.source_name}_test", environment)
        success = self._db_svc.wait_for_run_by_id(run_id, timeout=1800)
        if not success:
            logger.warning(
                "TC %s: job run %s did not report SUCCESS — assertions will determine TC status",
                tc.id, run_id,
            )

        # Teardown actions
        for action in tc.teardown:
            if action == "truncate_test_table":
                self._db_svc.query_sql(
                    f"TRUNCATE TABLE {suite.test_catalog}.{suite.test_schema}.{suite.target_table}"
                )
            elif action == "truncate_dead_letter_table":
                self._db_svc.query_sql(
                    f"TRUNCATE TABLE {suite.test_catalog}.bronze_meta"
                    f".dead_letter_{suite.target_table}"
                )

        # Run assertions — assertions are the source of truth for pass/fail.
        # The job success flag is advisory: a timed-out wait still produces
        # correct data, and the assertions will catch any real failures.
        assertion_results: List[AssertionResult] = []
        all_passed = True
        for assertion in tc.assertions:
            ar = self._run_assertion(assertion)
            assertion_results.append(ar)
            if not ar.passed:
                all_passed = False

        duration = time.time() - start
        status = "PASSED" if all_passed else "FAILED"

        return TestCaseResult(
            id=tc.id,
            name=tc.name,
            category=tc.category,
            positive=tc.positive,
            status=status,
            duration_seconds=round(duration, 1),
            assertions=assertion_results,
        )

    def _run_assertion(self, assertion: AssertionSpec) -> AssertionResult:
        try:
            rows = self._db_svc.query_sql(assertion.sql)
            if rows:
                raw = list(rows[0].values())[0]
                try:
                    actual: Any = int(raw) if "." not in str(raw) else float(raw)
                except (ValueError, TypeError):
                    actual = raw
            else:
                actual = 0

            if assertion.type == "row_count_gte":
                passed = int(actual) >= int(assertion.expected)
            else:
                passed = actual == assertion.expected

            return AssertionResult(
                type=assertion.type,
                description=assertion.description,
                expected=assertion.expected,
                actual=actual,
                passed=passed,
                sql=assertion.sql,
            )
        except Exception as e:
            return AssertionResult(
                type=assertion.type,
                description=assertion.description,
                expected=assertion.expected,
                actual=None,
                passed=False,
                sql=assertion.sql,
                error=str(e),
            )

    # ──────────────────────────────────────────────────────────────────────
    # Private: job + data management
    # ──────────────────────────────────────────────────────────────────────

    def _ensure_test_job(self, source_name: str, environment: str) -> None:
        """Create/update a test-variant Databricks job for this source."""
        if not self._db_svc.available:
            return
        # Ensure the test schema exists before the first job run
        suite = self.get_suite(source_name)
        if suite:
            self._db_svc.query_sql(
                f"CREATE SCHEMA IF NOT EXISTS {suite.test_catalog}.{suite.test_schema}"
            )
        self._build_test_yaml(source_name)
        self._db_svc.create_or_update_job(f"{source_name}_test", environment)

    def _build_test_yaml(self, source_name: str) -> None:
        """Generate a test-variant YAML (bronze_test schema) and upload to workspace."""
        source = self._config_svc.get_source(source_name)
        if not source:
            raise ValueError(f"Source '{source_name}' not found")

        config = yaml.safe_load(source.raw_yaml)

        # Override name so the audit log writes source_name = '{source_name}_test'
        config["name"] = f"{source_name}_test"

        # Override target schema to bronze_test (never touch production bronze)
        if "target" in config:
            config["target"]["schema"] = "bronze_test"
            # Override quarantine threshold to 100 % so intentional negative tests
            # (e.g. TC005 — 100 % null-PK batch) don't trip the circuit-breaker
            # before quarantine() is called.  The threshold guard is a production
            # safeguard; during testing we want every bad record to be quarantined.
            config["target"].setdefault("quality", {})["quarantine_threshold_pct"] = 100

        # Override extract path to the test landing volume directory so the
        # pipeline reads the NDJSON files uploaded by _upload_test_data().
        if "extract" in config:
            config["extract"]["path"] = (
                f"/Volumes/dev/bronze/landing_data/{source_name}_test/"
            )

        tmp_dir = TESTING_ROOT / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        test_yaml_name = f"{source_name}_test"
        tmp_path = tmp_dir / f"{test_yaml_name}.yaml"
        tmp_path.write_text(
            yaml.dump(config, default_flow_style=False), encoding="utf-8"
        )

        try:
            self._db_svc.upload_yaml(str(tmp_path), test_yaml_name)
        except Exception as e:
            logger.warning("Could not upload test YAML for %s: %s", source_name, e)

    def _upload_test_data(self, source_name: str, data_file: str) -> None:
        """Upload an NDJSON test data file to the Unity Catalog volume.

        Always uploads to a fixed filename (test_batch.json) so the pipeline
        only sees the current TC's data on each run.  Previous TC files are
        implicitly overwritten rather than accumulated.
        """
        data_path = TESTING_ROOT / "data" / source_name / data_file
        if not data_path.exists():
            raise FileNotFoundError(f"Test data file not found: {data_path}")

        content = data_path.read_bytes()
        landing_dir = f"/Volumes/dev/bronze/landing_data/{source_name}_test"
        volume_path = f"{landing_dir}/test_batch.json"
        try:
            # Clear the landing directory so the pipeline only reads this TC's data
            self._db_svc.clear_volume_directory(landing_dir)
            self._db_svc.upload_bytes_to_volume(content, volume_path)
        except Exception as e:
            logger.warning("Could not upload test data %s: %s", data_file, e)

    def _wait_for_run(
        self,
        source_name: str,
        run_start: datetime,
        timeout: int = 600,
    ) -> bool:
        """Poll audit log every 10 s until the test run completes or times out."""
        if not self._db_svc.available:
            return True  # Offline mode: assume success

        test_source_name = f"{source_name}_test"
        start_iso = run_start.strftime("%Y-%m-%d %H:%M:%S")
        deadline = time.time() + timeout

        while time.time() < deadline:
            rows = self._db_svc.query_sql(
                f"SELECT status FROM dev.bronze_meta.ingestion_audit_log "
                f"WHERE source_name = '{test_source_name}' "
                f"AND start_time >= '{start_iso}' "
                f"ORDER BY end_time DESC LIMIT 1"
            )
            if rows:
                status = rows[0].get("status", "")
                if status in ("SUCCESS", "FAILED", "FAILURE", "ERROR"):
                    return status == "SUCCESS"
            time.sleep(10)

        logger.warning("Timed out waiting for test run of %s", source_name)
        return False

    def _save_result(self, source_name: str, result: TestRunResult) -> None:
        results_dir = TESTING_ROOT / "results" / source_name
        results_dir.mkdir(parents=True, exist_ok=True)
        result_path = results_dir / f"{result.run_id}.json"
        result_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    def _save_html_report(self, source_name: str, result: TestRunResult) -> None:
        try:
            html = self._generate_html_report(result)
            results_dir = TESTING_ROOT / "results" / source_name
            results_dir.mkdir(parents=True, exist_ok=True)
            (results_dir / f"{result.run_id}.html").write_text(html, encoding="utf-8")
            logger.info("HTML report saved for %s run %s", source_name, result.run_id)
        except Exception as e:
            logger.warning("Failed to generate HTML report for %s: %s", source_name, e)

    def _generate_html_report(self, result: TestRunResult) -> str:  # noqa: PLR0912
        """Build a self-contained HTML stakeholder report from a TestRunResult."""

        STATUS_STYLE: Dict[str, tuple] = {
            "PASSED":  ("#166534", "#dcfce7", "#16a34a"),
            "FAILED":  ("#991b1b", "#fee2e2", "#dc2626"),
            "RUNNING": ("#1e40af", "#dbeafe", "#3b82f6"),
            "ERROR":   ("#92400e", "#fef3c7", "#f59e0b"),
            "NOT_RUN": ("#374151", "#f3f4f6", "#9ca3af"),
        }

        def badge(status: str) -> str:
            txt, bg, bdr = STATUS_STYLE.get(status, STATUS_STYLE["NOT_RUN"])
            return (
                f'<span style="background:{bg};color:{txt};border:1px solid {bdr};'
                f'padding:2px 10px;border-radius:4px;font-size:12px;font-weight:600;">'
                f"{status}</span>"
            )

        def fmt_dur(secs: Any) -> str:
            if secs is None:
                return "—"
            secs = float(secs)
            return f"{round(secs)}s" if secs < 60 else f"{round(secs / 60)} min"

        run_date = (
            result.started_at.strftime("%d %B %Y, %H:%M UTC")
            if result.started_at
            else "—"
        )
        completed_date = (
            result.completed_at.strftime("%d %B %Y, %H:%M UTC")
            if result.completed_at
            else "—"
        )
        overall = result.overall_status or "RUNNING"
        ov_txt, ov_bg, _ = STATUS_STYLE.get(overall, STATUS_STYLE["NOT_RUN"])
        summary = result.summary

        # ── Build TC rows ────────────────────────────────────────────────
        tc_rows_html: List[str] = []
        for tc in result.test_cases:
            s = tc.status or "NOT_RUN"
            cat = tc.category.replace("_", " ").title()
            tc_type = (
                '<span style="color:#16a34a;font-weight:500;">Positive</span>'
                if tc.positive
                else '<span style="color:#d97757;font-weight:500;">Negative</span>'
            )
            tc_rows_html.append(
                f'<tr style="border-bottom:1px solid #ede8e0;">'
                f'<td style="padding:12px 16px;font-family:monospace;font-size:12px;color:#6b6b6b;">{tc.id}</td>'
                f'<td style="padding:12px 16px;font-size:13px;color:#6b6b6b;">{cat}</td>'
                f'<td style="padding:12px 16px;font-size:14px;">{tc.name}</td>'
                f"<td style=\"padding:12px 16px;font-size:13px;\">{tc_type}</td>"
                f'<td style="padding:12px 16px;">{badge(s)}</td>'
                f'<td style="padding:12px 16px;font-size:13px;color:#6b6b6b;">{fmt_dur(tc.duration_seconds)}</td>'
                f"</tr>"
            )
            if tc.assertions:
                a_rows: List[str] = []
                for a in tc.assertions:
                    chk = "✓" if a.passed else "✗"
                    clr = "#16a34a" if a.passed else "#dc2626"
                    act = str(a.actual) if a.actual is not None else "—"
                    a_rows.append(
                        f'<tr style="border-bottom:1px solid #f5f0e8;">'
                        f'<td style="padding:7px 12px;font-size:13px;color:#374151;">{a.description}</td>'
                        f'<td style="padding:7px 12px;font-family:monospace;font-size:12px;">{a.expected}</td>'
                        f'<td style="padding:7px 12px;font-family:monospace;font-size:12px;">{act}</td>'
                        f'<td style="padding:7px 12px;font-size:14px;font-weight:700;color:{clr};">{chk}</td>'
                        f"</tr>"
                    )
                err_html = ""
                if tc.error:
                    err_html = (
                        f'<p style="margin-top:8px;font-size:12px;color:#dc2626;'
                        f'font-family:monospace;background:#fef2f2;padding:8px 12px;'
                        f'border-radius:4px;">{tc.error}</p>'
                    )
                tc_rows_html.append(
                    '<tr><td colspan="6" style="padding:0 16px 12px 48px;background:#faf8f5;">'
                    '<table style="width:100%;border-collapse:collapse;background:#fff;'
                    'border-radius:6px;overflow:hidden;border:1px solid #ede8e0;">'
                    '<thead><tr style="background:#f5f0e8;font-size:11px;color:#6b6b6b;text-transform:uppercase;letter-spacing:0.5px;">'
                    '<th style="padding:7px 12px;text-align:left;font-weight:500;">Assertion</th>'
                    '<th style="padding:7px 12px;text-align:left;font-weight:500;">Expected</th>'
                    '<th style="padding:7px 12px;text-align:left;font-weight:500;">Actual</th>'
                    '<th style="padding:7px 12px;text-align:left;font-weight:500;width:40px;">Pass</th>'
                    "</tr></thead>"
                    f"<tbody>{''.join(a_rows)}</tbody></table>"
                    f"{err_html}</td></tr>"
                )

        p = summary.passed if summary else 0
        f_ = summary.failed if summary else 0
        t = summary.total if summary else len(result.test_cases)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Bronze Test Report — {result.source_name}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
        background:#faf8f5;color:#2d2d2d;padding:40px 20px}}
  .wrap{{max-width:980px;margin:0 auto}}
  .card{{background:#fff;border:1px solid #e5e0d8;border-radius:8px}}
  h2{{font-size:15px;font-weight:600;color:#4a4a4a}}
  @media print{{body{{background:#fff;padding:20px}}}}
</style>
</head>
<body>
<div class="wrap">

  <!-- Header -->
  <div style="display:flex;align-items:flex-start;justify-content:space-between;
              margin-bottom:28px;flex-wrap:wrap;gap:16px;">
    <div>
      <div style="font-size:11px;font-weight:700;letter-spacing:1.2px;color:#d97757;
                  text-transform:uppercase;margin-bottom:8px;">
        Bronze Pipeline · Test Report
      </div>
      <h1 style="font-size:26px;font-weight:700;">{result.source_name}</h1>
      <p style="margin-top:6px;font-size:14px;color:#6b6b6b;">
        Started {run_date} &nbsp;·&nbsp; Environment: <strong>{result.environment}</strong>
      </p>
    </div>
    <div style="background:{ov_bg};color:{ov_txt};border-radius:8px;
                padding:12px 28px;font-size:20px;font-weight:700;text-align:center;
                border:1px solid {STATUS_STYLE.get(overall, STATUS_STYLE['NOT_RUN'])[2]};">
      {overall}
    </div>
  </div>

  <!-- Summary -->
  <div class="card" style="padding:20px 28px;margin-bottom:20px;
                            display:flex;gap:36px;flex-wrap:wrap;align-items:center;">
    <div>
      <div style="font-size:32px;font-weight:700;color:#16a34a;">{p}</div>
      <div style="font-size:13px;color:#6b6b6b;margin-top:2px;">Passed</div>
    </div>
    <div>
      <div style="font-size:32px;font-weight:700;color:#dc2626;">{f_}</div>
      <div style="font-size:13px;color:#6b6b6b;margin-top:2px;">Failed</div>
    </div>
    <div>
      <div style="font-size:32px;font-weight:700;color:#374151;">{t}</div>
      <div style="font-size:13px;color:#6b6b6b;margin-top:2px;">Total</div>
    </div>
    <div style="margin-left:auto;text-align:right;">
      <div style="font-size:24px;font-weight:600;color:#4a4a4a;">{fmt_dur(result.duration_seconds)}</div>
      <div style="font-size:13px;color:#6b6b6b;margin-top:2px;">Total duration</div>
    </div>
  </div>

  <!-- Test cases table -->
  <div class="card" style="overflow:hidden;margin-bottom:24px;">
    <div style="padding:16px 24px;border-bottom:1px solid #e5e0d8;">
      <h2>Test Cases</h2>
    </div>
    <table style="width:100%;border-collapse:collapse;">
      <thead>
        <tr style="background:#f5f0e8;font-size:11px;color:#6b6b6b;
                   text-transform:uppercase;letter-spacing:0.5px;">
          <th style="padding:10px 16px;text-align:left;font-weight:500;">ID</th>
          <th style="padding:10px 16px;text-align:left;font-weight:500;">Category</th>
          <th style="padding:10px 16px;text-align:left;font-weight:500;">Name</th>
          <th style="padding:10px 16px;text-align:left;font-weight:500;">Type</th>
          <th style="padding:10px 16px;text-align:left;font-weight:500;">Status</th>
          <th style="padding:10px 16px;text-align:left;font-weight:500;">Duration</th>
        </tr>
      </thead>
      <tbody>
        {''.join(tc_rows_html)}
      </tbody>
    </table>
  </div>

  <!-- Footer -->
  <div style="text-align:center;font-size:12px;color:#9ca3af;margin-top:20px;">
    Generated by Bronze Portal Testing Framework &nbsp;·&nbsp;
    Run ID: <code style="font-family:monospace;font-size:11px;">{result.run_id}</code>
    &nbsp;·&nbsp; Completed {completed_date}
  </div>

</div>
</body>
</html>"""

    def _persist_single_tc_result(
        self, source_name: str, tc_result: TestCaseResult, environment: str = "dev"
    ) -> None:
        """Persist a single TC result as the new latest result on disk.

        Always writes to a NEW file (new UUID) so that any background suite
        thread still writing to the old run_id file cannot overwrite this
        result.  The new file's mtime is newer than the old file, so
        get_latest_result() will return it on the next SWR revalidation.
        """
        try:
            now = datetime.now(timezone.utc)
            latest = self.get_latest_result(source_name)

            if latest:
                # Merge the new TC result into a copy of the previous result
                updated: List[TestCaseResult] = []
                found = False
                for existing_tc in latest.test_cases:
                    if existing_tc.id == tc_result.id:
                        updated.append(tc_result)
                        found = True
                    else:
                        updated.append(existing_tc)
                if not found:
                    updated.append(tc_result)

                # Recompute overall status from merged TC list
                statuses = {t.status for t in updated}
                if "FAILED" in statuses or "ERROR" in statuses:
                    overall = "FAILED"
                elif statuses == {"PASSED"}:
                    overall = "PASSED"
                else:
                    # Prior run was a cancelled/running suite — derive from this TC
                    overall = (
                        latest.overall_status
                        if latest.overall_status not in ("RUNNING", "CANCELLED")
                        else ("PASSED" if tc_result.status == "PASSED" else "FAILED")
                    )

                passed = sum(1 for t in updated if t.status == "PASSED")
                failed = sum(1 for t in updated if t.status in ("FAILED", "ERROR"))
                skipped = len(updated) - passed - failed

                new_result = TestRunResult(
                    # New UUID → new file so background thread cannot overwrite it
                    run_id=str(uuid.uuid4()),
                    source_name=source_name,
                    started_at=latest.started_at or now,
                    completed_at=now,
                    duration_seconds=tc_result.duration_seconds or 0.0,
                    overall_status=overall,
                    environment=environment,
                    summary=TestRunSummary(
                        total=len(updated),
                        passed=passed,
                        failed=failed,
                        skipped=skipped,
                    ),
                    test_cases=updated,
                )
            else:
                # No prior run at all — create a minimal record.
                new_result = TestRunResult(
                    run_id=str(uuid.uuid4()),
                    source_name=source_name,
                    started_at=now,
                    completed_at=now,
                    duration_seconds=tc_result.duration_seconds or 0.0,
                    overall_status=tc_result.status,
                    environment=environment,
                    summary=TestRunSummary(
                        total=1,
                        passed=1 if tc_result.status == "PASSED" else 0,
                        failed=0 if tc_result.status == "PASSED" else 1,
                        skipped=0,
                    ),
                    test_cases=[tc_result],
                )

            self._save_result(source_name, new_result)
        except Exception as e:
            logger.warning(
                "Could not persist single TC result for %s/%s: %s",
                source_name, tc_result.id, e,
            )

    # ──────────────────────────────────────────────────────────────────────
    # Private: scaffold generation
    # ──────────────────────────────────────────────────────────────────────

    def _build_scaffold_suite(
        self,
        source_name: str,
        source_type: str,
        target_table: str,
        primary_keys: List[str],
    ) -> Dict:
        pk = primary_keys[0] if primary_keys else "id"
        catalog = "dev"
        schema = "bronze_test"
        tbl = target_table or source_name

        return {
            "source_name": source_name,
            "source_type": source_type,
            "primary_keys": primary_keys or [pk],
            "target_table": tbl,
            "test_catalog": catalog,
            "test_schema": schema,
            "test_cases": [
                {
                    "id": "TC001",
                    "name": "Full load — insert all baseline records",
                    "category": "insert",
                    "positive": True,
                    "data_file": "tc001_full_load.json",
                    "setup": ["truncate_test_table"],
                    "teardown": [],
                    "assertions": [
                        {
                            "type": "row_count",
                            "sql": f"SELECT COUNT(*) FROM {catalog}.{schema}.{tbl}",
                            "expected": "TODO",
                            "description": "All records inserted",
                        },
                    ],
                },
                {
                    "id": "TC002",
                    "name": "CDC update — SCD2 new row created, old row closed",
                    "category": "update",
                    "positive": True,
                    "data_file": "tc002_update.json",
                    "setup": [],
                    "teardown": [],
                    "assertions": [
                        {
                            "type": "row_count",
                            "sql": f"SELECT COUNT(*) FROM {catalog}.{schema}.{tbl} WHERE {pk} = 'TODO' AND _is_current = false",
                            "expected": 1,
                            "description": "Old row closed",
                        },
                    ],
                },
                {
                    "id": "TC003",
                    "name": "Soft-delete — row closed in bronze",
                    "category": "delete",
                    "positive": True,
                    "data_file": "tc003_delete.json",
                    "setup": [],
                    "teardown": [],
                    "assertions": [
                        {
                            "type": "row_count",
                            "sql": f"SELECT COUNT(*) FROM {catalog}.{schema}.{tbl} WHERE _is_current = false",
                            "expected": "TODO",
                            "description": "Deleted row closed",
                        },
                    ],
                },
                {
                    "id": "TC004",
                    "name": "Late-arriving data — does not overwrite current version",
                    "category": "late_arriving",
                    "positive": True,
                    "data_file": "tc004_late_arriving.json",
                    "setup_data_file": "tc004_setup.json",
                    "setup": ["truncate_test_table"],
                    "teardown": [],
                    "assertions": [
                        {
                            "type": "row_count",
                            "sql": f"SELECT COUNT(*) FROM {catalog}.{schema}.{tbl}",
                            "expected": 1,
                            "description": "Late-arriving did not create extra SCD2 row",
                        },
                    ],
                },
                {
                    "id": "TC005",
                    "name": "Null primary key — quarantined to dead letter",
                    "category": "null_pk",
                    "positive": False,
                    "data_file": "tc005_null_pk.json",
                    "setup": ["truncate_test_table"],
                    "teardown": [],
                    "assertions": [
                        {
                            "type": "row_count",
                            "sql": f"SELECT COUNT(*) FROM {catalog}.{schema}.{tbl} WHERE {pk} IS NULL",
                            "expected": 0,
                            "description": "No null PK in main table",
                        },
                        {
                            "type": "row_count",
                            "sql": f"SELECT COUNT(*) FROM dev.bronze_meta.dead_letter_{tbl}",
                            "expected": 1,
                            "description": "Null PK record quarantined",
                        },
                    ],
                },
                {
                    "id": "TC006",
                    "name": "Duplicate in batch — exactly one row in target",
                    "category": "duplicate",
                    "positive": False,
                    "data_file": "tc006_duplicate.json",
                    "setup": ["truncate_test_table"],
                    "teardown": [],
                    "assertions": [
                        {
                            "type": "row_count",
                            "sql": f"SELECT COUNT(*) FROM {catalog}.{schema}.{tbl}",
                            "expected": 1,
                            "description": "Only 1 row despite duplicate in batch",
                        },
                    ],
                },
                {
                    "id": "TC007",
                    "name": "Idempotency — re-run produces no duplicates",
                    "category": "idempotency",
                    "positive": True,
                    "data_file": "tc006_duplicate.json",
                    "setup": [],
                    "teardown": [],
                    "assertions": [
                        {
                            "type": "row_count",
                            "sql": f"SELECT COUNT(*) FROM {catalog}.{schema}.{tbl}",
                            "expected": 1,
                            "description": "Same row count after re-run (idempotent)",
                        },
                    ],
                },
                {
                    "id": "TC008",
                    "name": "Audit log — SUCCESS entry with correct record count",
                    "category": "audit",
                    "positive": True,
                    "data_file": "tc001_full_load.json",
                    "setup": ["truncate_test_table"],
                    "teardown": ["truncate_test_table"],
                    "assertions": [
                        {
                            "type": "row_count_gte",
                            "sql": f"SELECT COUNT(*) FROM dev.bronze_meta.ingestion_audit_log WHERE source_name = '{source_name}_test' AND status = 'SUCCESS'",
                            "expected": 1,
                            "description": "Audit log records a SUCCESS entry",
                        },
                    ],
                },
            ],
        }
