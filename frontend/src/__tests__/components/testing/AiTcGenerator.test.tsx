import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AiTcGenerator } from "@/components/testing/AiTcGenerator";
import { ToastProvider } from "@/components/ui/toast";
import type { TcConfirmResponse, TcGeneratePreview } from "@/types/testing";

// ── Mock the api module ────────────────────────────────────────────────────────

vi.mock("@/lib/api", () => ({
  api: {
    aiGenerateTc: vi.fn(),
    aiConfirmTc: vi.fn(),
  },
}));

import { api } from "@/lib/api";

const mockedAiGenerateTc = vi.mocked(api.aiGenerateTc);
const mockedAiConfirmTc = vi.mocked(api.aiConfirmTc);

// ── Fixtures ──────────────────────────────────────────────────────────────────

const PREVIEW: TcGeneratePreview = {
  tc_id: "TC009",
  name: "Ensure status column only accepts valid values",
  category: "data_quality",
  positive: false,
  setup: ["truncate_test_table"],
  teardown: [],
  assertions: [
    {
      type: "row_count",
      sql: "SELECT COUNT(*) FROM dev.bronze_test.crm WHERE status NOT IN ('active','inactive')",
      expected: 0,
      description: "No invalid status records in main table",
    },
  ],
  data_file_name: "tc009_invalid_status.json",
  data_records: [
    { id: "C001", name: "Alice", status: "banned" },
    { id: "C002", name: "Bob", status: "pending" },
  ],
  explanation: "Tests that records with an invalid status value are quarantined.",
};

const CONFIRM_RESPONSE: TcConfirmResponse = {
  tc_id: "TC009",
  data_file: "tc009_invalid_status.json",
  message: "Test case TC009 added to suite and executed.",
  result: {
    id: "TC009",
    name: "Ensure status column only accepts valid values",
    category: "data_quality",
    positive: false,
    status: "PASSED",
    duration_seconds: 3.2,
    assertions: [],
    error: null,
  },
};

const CONFIRM_RESPONSE_FAILED: TcConfirmResponse = {
  ...CONFIRM_RESPONSE,
  result: { ...CONFIRM_RESPONSE.result, status: "FAILED" },
};

// ── Render helper ─────────────────────────────────────────────────────────────

function renderComponent(onTcAdded = vi.fn()) {
  return render(
    <ToastProvider>
      <AiTcGenerator sourceName="crm_customers" onTcAdded={onTcAdded} />
    </ToastProvider>
  );
}

// ── Tests ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AiTcGenerator — idle state", () => {
  it("renders the textarea in idle state", () => {
    renderComponent();
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  it("renders the Generate TC button in idle state", () => {
    renderComponent();
    expect(screen.getByRole("button", { name: /generate tc/i })).toBeInTheDocument();
  });

  it("shows the header label", () => {
    renderComponent();
    expect(screen.getByText(/generate a test case with ai/i)).toBeInTheDocument();
  });

  it("Generate TC button is disabled when prompt is empty", () => {
    renderComponent();
    const btn = screen.getByRole("button", { name: /generate tc/i });
    expect(btn).toBeDisabled();
  });

  it("Generate TC button is enabled after typing a prompt", async () => {
    const user = userEvent.setup();
    renderComponent();
    await user.type(screen.getByRole("textbox"), "Check null ids are quarantined");
    const btn = screen.getByRole("button", { name: /generate tc/i });
    expect(btn).not.toBeDisabled();
  });
});

describe("AiTcGenerator — generating state", () => {
  it("shows Generating… label while API call is in-flight", async () => {
    // Return a promise that never resolves so we stay in generating state
    mockedAiGenerateTc.mockReturnValue(new Promise(() => {}));

    const user = userEvent.setup();
    renderComponent();
    await user.type(screen.getByRole("textbox"), "Some prompt");
    await user.click(screen.getByRole("button", { name: /generate tc/i }));

    expect(screen.getByText(/generating…/i)).toBeInTheDocument();
  });

  it("disables the Generate TC button while generating", async () => {
    mockedAiGenerateTc.mockReturnValue(new Promise(() => {}));

    const user = userEvent.setup();
    renderComponent();
    await user.type(screen.getByRole("textbox"), "Some prompt");
    await user.click(screen.getByRole("button", { name: /generate tc/i }));

    const btn = screen.getByRole("button", { name: /generating…/i });
    expect(btn).toBeDisabled();
  });
});

describe("AiTcGenerator — preview state", () => {
  beforeEach(() => {
    mockedAiGenerateTc.mockResolvedValue(PREVIEW);
  });

  async function renderWithPreview() {
    const user = userEvent.setup();
    const onTcAdded = vi.fn();
    renderComponent(onTcAdded);
    await user.type(screen.getByRole("textbox"), "Ensure status column only accepts valid values");
    await user.click(screen.getByRole("button", { name: /generate tc/i }));
    await waitFor(() => screen.getByText("TC009"));
    return { user, onTcAdded };
  }

  it("shows the TC ID after generation", async () => {
    await renderWithPreview();
    expect(screen.getByText("TC009")).toBeInTheDocument();
  });

  it("shows the TC name in the preview", async () => {
    await renderWithPreview();
    expect(
      screen.getByText("Ensure status column only accepts valid values")
    ).toBeInTheDocument();
  });

  it("shows the explanation text", async () => {
    await renderWithPreview();
    expect(
      screen.getByText(/records with an invalid status value are quarantined/i)
    ).toBeInTheDocument();
  });

  it("shows assertion count", async () => {
    await renderWithPreview();
    expect(screen.getByText(/assertions \(1\)/i)).toBeInTheDocument();
  });

  it("shows Add & Run button in preview state", async () => {
    await renderWithPreview();
    expect(screen.getByRole("button", { name: /add & run/i })).toBeInTheDocument();
  });

  it("shows Try again button in preview state", async () => {
    await renderWithPreview();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows data records toggle button", async () => {
    await renderWithPreview();
    expect(screen.getByText(/test data \(2 records\)/i)).toBeInTheDocument();
  });

  it("clicking Try again resets to idle state", async () => {
    const { user } = await renderWithPreview();
    await user.click(screen.getByRole("button", { name: /try again/i }));
    // Back to idle: textarea is visible, Generate TC button present
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /generate tc/i })).toBeInTheDocument();
  });

  it("clicking Add & Run calls aiConfirmTc with correct args", async () => {
    mockedAiConfirmTc.mockResolvedValue(CONFIRM_RESPONSE);
    const { user } = await renderWithPreview();
    await user.click(screen.getByRole("button", { name: /add & run/i }));
    await waitFor(() => expect(mockedAiConfirmTc).toHaveBeenCalledTimes(1));
    const [calledSourceName, calledPreview] = mockedAiConfirmTc.mock.calls[0];
    expect(calledSourceName).toBe("crm_customers");
    expect(calledPreview.tc_id).toBe("TC009");
  });
});

describe("AiTcGenerator — done state (PASSED)", () => {
  beforeEach(() => {
    mockedAiGenerateTc.mockResolvedValue(PREVIEW);
    mockedAiConfirmTc.mockResolvedValue(CONFIRM_RESPONSE);
  });

  async function renderDone() {
    const user = userEvent.setup();
    const onTcAdded = vi.fn();
    renderComponent(onTcAdded);
    await user.type(screen.getByRole("textbox"), "Ensure status column only accepts valid values");
    await user.click(screen.getByRole("button", { name: /generate tc/i }));
    await waitFor(() => screen.getByText("TC009"));
    await user.click(screen.getByRole("button", { name: /add & run/i }));
    await waitFor(() => screen.getByText(/TC009 added and executed/i));
    return { user, onTcAdded };
  }

  it("shows the TC id and status in done state", async () => {
    await renderDone();
    expect(screen.getByText(/TC009 added and executed/i)).toBeInTheDocument();
    expect(screen.getByText("PASSED")).toBeInTheDocument();
  });

  it("shows Generate another button in done state", async () => {
    await renderDone();
    expect(screen.getByRole("button", { name: /generate another/i })).toBeInTheDocument();
  });

  it("calls onTcAdded callback after confirm", async () => {
    const { onTcAdded } = await renderDone();
    expect(onTcAdded).toHaveBeenCalledTimes(1);
  });

  it("clicking Generate another resets to idle state", async () => {
    const { user } = await renderDone();
    await user.click(screen.getByRole("button", { name: /generate another/i }));
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /generate tc/i })).toBeInTheDocument();
  });
});

describe("AiTcGenerator — done state (FAILED)", () => {
  it("shows FAILED status in done state", async () => {
    mockedAiGenerateTc.mockResolvedValue(PREVIEW);
    mockedAiConfirmTc.mockResolvedValue(CONFIRM_RESPONSE_FAILED);

    const user = userEvent.setup();
    renderComponent();
    await user.type(screen.getByRole("textbox"), "Some prompt");
    await user.click(screen.getByRole("button", { name: /generate tc/i }));
    await waitFor(() => screen.getByText("TC009"));
    await user.click(screen.getByRole("button", { name: /add & run/i }));
    await waitFor(() => screen.getByText("FAILED"));
    expect(screen.getByText("FAILED")).toBeInTheDocument();
  });
});

describe("AiTcGenerator — error handling", () => {
  it("returns to idle state when aiGenerateTc rejects", async () => {
    mockedAiGenerateTc.mockRejectedValue(new Error("AI generation failed"));

    const user = userEvent.setup();
    renderComponent();
    await user.type(screen.getByRole("textbox"), "Some prompt");
    await user.click(screen.getByRole("button", { name: /generate tc/i }));

    // After rejection, should return to idle (textarea visible)
    await waitFor(() => screen.getByRole("textbox"));
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /generate tc/i })).toBeInTheDocument();
  });

  it("stays in preview state when aiConfirmTc rejects", async () => {
    mockedAiGenerateTc.mockResolvedValue(PREVIEW);
    mockedAiConfirmTc.mockRejectedValue(new Error("Failed to add test case"));

    const user = userEvent.setup();
    renderComponent();
    await user.type(screen.getByRole("textbox"), "Some prompt");
    await user.click(screen.getByRole("button", { name: /generate tc/i }));
    await waitFor(() => screen.getByText("TC009"));
    await user.click(screen.getByRole("button", { name: /add & run/i }));

    // On error, stays in preview (Add & Run button still visible)
    await waitFor(() => screen.getByRole("button", { name: /add & run/i }));
    expect(screen.getByRole("button", { name: /add & run/i })).toBeInTheDocument();
  });
});
