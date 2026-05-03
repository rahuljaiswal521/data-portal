/** TypeScript interfaces mirroring portal/backend/app/models/testing.py */

export type TestStatus =
  | "PASSED"
  | "FAILED"
  | "RUNNING"
  | "SKIPPED"
  | "ERROR"
  | "NOT_RUN";

export type TestCategory =
  | "insert"
  | "update"
  | "delete"
  | "late_arriving"
  | "null_pk"
  | "duplicate"
  | "idempotency"
  | "audit"
  | "data_quality";

export interface AssertionSpec {
  type: string;
  sql: string;
  expected: number | string;
  description: string;
}

export interface TestCase {
  id: string;
  name: string;
  category: TestCategory;
  positive: boolean;
  data_file: string | null;
  setup_data_file: string | null;
  setup: string[];
  teardown: string[];
  assertions: AssertionSpec[];
}

export interface TestSuite {
  source_name: string;
  source_type: string;
  primary_keys: string[];
  target_table: string;
  test_catalog: string;
  test_schema: string;
  test_cases: TestCase[];
}

export interface AssertionResult {
  type: string;
  description: string;
  expected: number | string;
  actual: number | string | null;
  passed: boolean;
  sql: string;
  error?: string | null;
}

export interface TestCaseResult {
  id: string;
  name: string;
  category: TestCategory;
  positive: boolean;
  status: TestStatus;
  duration_seconds: number | null;
  assertions: AssertionResult[];
  error: string | null;
}

export interface TestRunSummary {
  total: number;
  passed: number;
  failed: number;
  skipped: number;
}

export interface TestRunResult {
  run_id: string;
  source_name: string;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  overall_status: TestStatus;
  environment: string;
  tester: string;
  summary: TestRunSummary;
  test_cases: TestCaseResult[];
}

export interface TestSuiteSummary {
  source_name: string;
  source_type: string;
  primary_keys: string[];
  target_table: string;
  test_count: number;
  last_run_status: TestStatus | null;
  last_run_at: string | null;
}

export interface TestSuiteListResponse {
  suites: TestSuiteSummary[];
  total: number;
}

export interface TestRunListResponse {
  source_name: string;
  runs: TestRunResult[];
  total: number;
}

export interface GenerateSuiteResponse {
  source_name: string;
  message: string;
  test_count: number;
}

export interface RunSuiteResponse {
  run_id: string;
  source_name: string;
  message: string;
}

// ── AI test case generator types ──────────────────────────────────────────────

export interface TcGeneratePreview {
  tc_id: string;
  name: string;
  category: string;
  positive: boolean;
  setup: string[];
  teardown: string[];
  assertions: AssertionSpec[];
  data_file_name: string;
  data_records: Record<string, unknown>[];
  explanation: string;
}

export interface TcConfirmResponse {
  tc_id: string;
  data_file: string;
  message: string;
  result: TestCaseResult;
}
