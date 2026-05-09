import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import { DatabricksGuard } from "@/components/layout/DatabricksGuard";

const mockGetSettings = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getAccountSettings: () => mockGetSettings(),
  },
}));

function makeSettings(databricksConfigured: boolean) {
  return {
    anthropic: { configured: false, preview: null },
    openai: { configured: false, preview: null },
    gemini: { configured: false, preview: null },
    databricks: {
      configured: databricksConfigured,
      host_preview: databricksConfigured ? "https://adb-***.azuredatabricks.net" : null,
      warehouse_id: databricksConfigured ? "abc1234" : null,
    },
    selected_model: "claude-sonnet-4-5-20250929",
    selected_provider: "anthropic" as const,
    has_anthropic_key: false,
    anthropic_key_preview: null,
  };
}

beforeEach(() => {
  mockGetSettings.mockReset();
});

describe("DatabricksGuard — configured", () => {
  it("renders children when databricks.configured is true", async () => {
    mockGetSettings.mockResolvedValue(makeSettings(true));
    await act(async () => {
      render(<DatabricksGuard><span>protected child</span></DatabricksGuard>);
    });
    await waitFor(() => {
      expect(screen.getByText("protected child")).toBeInTheDocument();
    });
  });

  it("does not show the prompt when configured", async () => {
    mockGetSettings.mockResolvedValue(makeSettings(true));
    await act(async () => {
      render(<DatabricksGuard><span>ok</span></DatabricksGuard>);
    });
    await waitFor(() => {
      expect(screen.queryByText(/Databricks workspace not configured/i)).not.toBeInTheDocument();
    });
  });
});

describe("DatabricksGuard — not configured", () => {
  it("shows the prompt when databricks.configured is false", async () => {
    mockGetSettings.mockResolvedValue(makeSettings(false));
    await act(async () => {
      render(<DatabricksGuard><span>protected child</span></DatabricksGuard>);
    });
    await waitFor(() => {
      expect(screen.getByText(/Databricks workspace not configured/i)).toBeInTheDocument();
    });
  });

  it("does NOT render children when not configured", async () => {
    mockGetSettings.mockResolvedValue(makeSettings(false));
    await act(async () => {
      render(<DatabricksGuard><span data-testid="child">protected child</span></DatabricksGuard>);
    });
    await waitFor(() => {
      expect(screen.queryByTestId("child")).not.toBeInTheDocument();
    });
  });

  it("shows a link to /settings", async () => {
    mockGetSettings.mockResolvedValue(makeSettings(false));
    await act(async () => {
      render(<DatabricksGuard><span>x</span></DatabricksGuard>);
    });
    await waitFor(() => {
      const link = screen.getByRole("link", { name: /Open Settings/i });
      expect(link).toBeInTheDocument();
      expect(link.getAttribute("href")).toBe("/settings");
    });
  });
});

describe("DatabricksGuard — loading state", () => {
  it("shows 'Checking Databricks configuration…' before resolution", async () => {
    let resolve!: (v: unknown) => void;
    mockGetSettings.mockReturnValue(new Promise((r) => { resolve = r; }));
    render(<DatabricksGuard><span>x</span></DatabricksGuard>);
    expect(screen.getByText(/Checking Databricks configuration/i)).toBeInTheDocument();
    // resolve to clean up
    await act(async () => { resolve(makeSettings(true)); });
  });
});

describe("DatabricksGuard — error state", () => {
  it("shows the prompt with an error message when getAccountSettings fails", async () => {
    mockGetSettings.mockRejectedValue(new Error("network down"));
    await act(async () => {
      render(<DatabricksGuard><span>x</span></DatabricksGuard>);
    });
    await waitFor(() => {
      expect(screen.getByText(/Databricks workspace not configured/i)).toBeInTheDocument();
      expect(screen.getByText(/Could not load account settings/i)).toBeInTheDocument();
    });
  });
});
