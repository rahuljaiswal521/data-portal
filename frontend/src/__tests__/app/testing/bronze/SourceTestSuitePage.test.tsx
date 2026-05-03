import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SourceTestSuitePage from "@/app/testing/bronze/[source]/page";

// ── SWR mock ────────────────────────────────────────────────────────────────
// mutateFn is captured so tests can call it to simulate SWR updates
let mutateFn = vi.fn();

vi.mock("swr", () => ({
  default: vi.fn(),
}));

// ── next/navigation: override useParams to return { source: "my_source" } ──
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  usePathname: () => "/testing/bronze/my_source",
  useParams: () => ({ source: "my_source" }),
  redirect: vi.fn(),
}));

// ── api mock ─────────────────────────────────────────────────────────────────
vi.mock("@/lib/api", () => ({
  api: {
    runTestSuite: vi.fn(),
    cancelTestSuite: vi.fn(),
    runSingleTc: vi.fn(),
    getTestReportUrl: vi.fn(() => "http://localhost/report"),
  },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

import useSWR from "swr";
import { api } from "@/lib/api";

const mockUseSWR = useSWR as ReturnType<typeof vi.fn>;

// Shared suite fixture
const mockSuite = {
  source_name: "my_source",
  target_table: "dev.bronze.my_source",
  test_catalog: "dev",
  test_schema: "bronze_test",
  test_cases: [
    { id: "TC001", category: "row_count", name: "Row count matches", positive: true },
    { id: "TC002", category: "schema", name: "Schema validation", positive: false },
  ],
};

function setupSWR(suiteData: typeof mockSuite | null, resultData: unknown = null) {
  mutateFn = vi.fn();
  mockUseSWR.mockImplementation((key: string | null) => {
    if (key && key.includes("/results/latest")) {
      return { data: resultData, isLoading: false, mutate: mutateFn };
    }
    // suite
    return { data: suiteData, isLoading: false };
  });
}

beforeEach(() => {
  setupSWR(mockSuite);
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Rendering ─────────────────────────────────────────────────────────────────

describe("SourceTestSuitePage — rendering", () => {
  it("renders source name as heading", () => {
    render(<SourceTestSuitePage />);
    expect(screen.getByRole("heading", { name: /my_source/i })).toBeInTheDocument();
  });

  it("renders Run Suite button", () => {
    render(<SourceTestSuitePage />);
    expect(screen.getByRole("button", { name: /run suite/i })).toBeInTheDocument();
  });

  it("renders a row for each test case", () => {
    render(<SourceTestSuitePage />);
    expect(screen.getByText("TC001")).toBeInTheDocument();
    expect(screen.getByText("TC002")).toBeInTheDocument();
  });

  it("renders per-row Run buttons (one per test case)", () => {
    render(<SourceTestSuitePage />);
    const runButtons = screen.getAllByTitle("Run this test case");
    expect(runButtons).toHaveLength(2);
  });

  it("renders a 'Run' column header in the table", () => {
    render(<SourceTestSuitePage />);
    expect(screen.getByText("Run")).toBeInTheDocument();
  });

  it("shows NOT_RUN status badge when no results exist", () => {
    render(<SourceTestSuitePage />);
    const notRunBadges = screen.getAllByText("NOT_RUN");
    expect(notRunBadges.length).toBeGreaterThanOrEqual(1);
  });

  it("shows loading skeleton when suite is loading", () => {
    mockUseSWR.mockImplementation(() => ({ data: null, isLoading: true }));
    const { container } = render(<SourceTestSuitePage />);
    // Skeletons render div elements with animate-pulse
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("shows not-found card when suite is null", () => {
    setupSWR(null);
    render(<SourceTestSuitePage />);
    expect(screen.getByText(/no test suite found/i)).toBeInTheDocument();
  });
});

// ── Per-row Run button behaviour ──────────────────────────────────────────────

describe("SourceTestSuitePage — per-row Run button", () => {
  it("individual Run buttons are enabled when no suite is running", () => {
    render(<SourceTestSuitePage />);
    const runButtons = screen.getAllByTitle("Run this test case");
    runButtons.forEach((btn) => expect(btn).not.toBeDisabled());
  });

  it("individual Run buttons are disabled while suite is running", () => {
    setupSWR(mockSuite, { overall_status: "RUNNING", test_cases: [], summary: null, duration_seconds: null });
    render(<SourceTestSuitePage />);
    const runButtons = screen.getAllByTitle("Run this test case");
    runButtons.forEach((btn) => expect(btn).toBeDisabled());
  });

  it("calls api.runSingleTc with correct source and tcId on click", async () => {
    (api.runSingleTc as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "TC001",
      status: "PASSED",
      assertions: [],
      duration_seconds: 0.4,
    });
    render(<SourceTestSuitePage />);
    const runButtons = screen.getAllByTitle("Run this test case");
    fireEvent.click(runButtons[0]);
    await waitFor(() => {
      expect(api.runSingleTc).toHaveBeenCalledWith("my_source", "TC001");
    });
  });

  it("calls mutate to update cache after single TC run", async () => {
    (api.runSingleTc as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "TC001",
      status: "PASSED",
      assertions: [],
      duration_seconds: 0.4,
    });
    setupSWR(mockSuite, {
      overall_status: "PASSED",
      test_cases: [{ id: "TC001", status: "PASSED", assertions: [], duration_seconds: 0.3 }],
      summary: { passed: 1, failed: 0, skipped: 0 },
      duration_seconds: 0.3,
    });
    render(<SourceTestSuitePage />);
    const runButtons = screen.getAllByTitle("Run this test case");
    fireEvent.click(runButtons[0]);
    await waitFor(() => {
      expect(mutateFn).toHaveBeenCalled();
    });
  });

  it("does not pass revalidate:false to mutate — allows SWR to refetch persisted result", async () => {
    // The bug fix removed the `false` second arg from mutateResult(...).
    // This test verifies mutate is NEVER called with `false` as second argument,
    // ensuring SWR will revalidate against the server after the optimistic update.
    (api.runSingleTc as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "TC001",
      status: "PASSED",
      assertions: [],
      duration_seconds: 0.4,
    });
    setupSWR(mockSuite, {
      overall_status: "PASSED",
      test_cases: [{ id: "TC001", status: "PASSED", assertions: [], duration_seconds: 0.3 }],
      summary: { passed: 1, failed: 0, skipped: 0 },
      duration_seconds: 0.3,
    });
    render(<SourceTestSuitePage />);
    const runButtons = screen.getAllByTitle("Run this test case");
    fireEvent.click(runButtons[0]);
    await waitFor(() => {
      expect(mutateFn).toHaveBeenCalled();
    });
    // Verify none of the mutate calls used `false` as the second argument
    const callsWithFalse = mutateFn.mock.calls.filter(
      (args) => args[1] === false || args[1]?.revalidate === false
    );
    expect(callsWithFalse).toHaveLength(0);
  });
});

// ── Suite Run / Cancel buttons ────────────────────────────────────────────────

describe("SourceTestSuitePage — Run Suite button", () => {
  it("Run Suite button is enabled when not running", () => {
    render(<SourceTestSuitePage />);
    expect(screen.getByRole("button", { name: /run suite/i })).not.toBeDisabled();
  });

  it("shows Stop button when suite is running", () => {
    setupSWR(mockSuite, { overall_status: "RUNNING", test_cases: [], summary: null, duration_seconds: null });
    render(<SourceTestSuitePage />);
    expect(screen.getByRole("button", { name: /stop/i })).toBeInTheDocument();
  });

  it("shows Download Report button when results exist and not running", () => {
    setupSWR(mockSuite, {
      overall_status: "PASSED",
      test_cases: [],
      summary: { passed: 2, failed: 0, skipped: 0 },
      duration_seconds: 1.5,
    });
    render(<SourceTestSuitePage />);
    expect(screen.getByRole("button", { name: /download report/i })).toBeInTheDocument();
  });
});
