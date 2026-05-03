"""Pydantic models for the Bronze testing framework."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel


class AssertionSpec(BaseModel):
    """SQL-based assertion to run after a test case."""

    type: str  # row_count | scalar_equals | row_count_gte
    sql: str
    expected: Union[int, float, str]
    description: str


class TestCase(BaseModel):
    """A single test scenario within a suite."""

    id: str
    name: str
    category: str  # insert | update | delete | late_arriving | null_pk | duplicate | idempotency | audit
    positive: bool
    data_file: Optional[str] = None
    setup_data_file: Optional[str] = None  # TC004 pattern: upload + run this first
    setup: List[str] = []  # e.g. ["truncate_test_table"]
    teardown: List[str] = []
    assertions: List[AssertionSpec] = []


class TestSuite(BaseModel):
    """Complete test suite definition for a source."""

    source_name: str
    source_type: str
    primary_keys: List[str]
    target_table: str
    test_catalog: str
    test_schema: str
    test_cases: List[TestCase]


class AssertionResult(BaseModel):
    """Result of a single SQL assertion."""

    type: str
    description: str
    expected: Union[int, float, str]
    actual: Optional[Union[int, float, str]] = None
    passed: bool
    sql: str
    error: Optional[str] = None


class TestCaseResult(BaseModel):
    """Result of executing one test case."""

    id: str
    name: str
    category: str
    positive: bool
    status: str  # PASSED | FAILED | RUNNING | SKIPPED | ERROR
    duration_seconds: Optional[float] = None
    assertions: List[AssertionResult] = []
    error: Optional[str] = None


class TestRunSummary(BaseModel):
    """Aggregate counts for a test run."""

    total: int
    passed: int
    failed: int
    skipped: int


class TestRunResult(BaseModel):
    """Full result record for one suite execution."""

    run_id: str
    source_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    overall_status: str  # PASSED | FAILED | RUNNING
    environment: str
    tester: str = "portal-test-framework"
    summary: TestRunSummary
    test_cases: List[TestCaseResult] = []


class TestSuiteSummary(BaseModel):
    """Lightweight summary for the suite list view."""

    source_name: str
    source_type: str
    primary_keys: List[str]
    target_table: str
    test_count: int
    last_run_status: Optional[str] = None
    last_run_at: Optional[str] = None


class TestSuiteListResponse(BaseModel):
    suites: List[TestSuiteSummary]
    total: int


class TestRunListResponse(BaseModel):
    source_name: str
    runs: List[TestRunResult]
    total: int


class GenerateSuiteResponse(BaseModel):
    source_name: str
    message: str
    test_count: int


class RunSuiteResponse(BaseModel):
    run_id: str
    source_name: str
    message: str


# ── AI test case generator models ─────────────────────────────────────────────

class TcGenerateRequest(BaseModel):
    prompt: str


class TcGeneratePreview(BaseModel):
    tc_id: str
    name: str
    category: str
    positive: bool
    setup: List[str] = []
    teardown: List[str] = []
    assertions: List[AssertionSpec] = []
    data_file_name: str
    data_records: List[dict] = []
    explanation: str


class TcConfirmRequest(BaseModel):
    tc_id: str
    name: str
    category: str
    positive: bool
    setup: List[str] = []
    teardown: List[str] = []
    assertions: List[AssertionSpec] = []
    data_file_name: str
    data_records: List[dict] = []


class TcConfirmResponse(BaseModel):
    tc_id: str
    data_file: str
    message: str
    result: TestCaseResult
