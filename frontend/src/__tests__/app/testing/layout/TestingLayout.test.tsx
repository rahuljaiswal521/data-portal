import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import TestingLayout from "@/app/testing/layout";

// DatabricksGuard calls api.getAccountSettings() — mock it to return configured.
vi.mock("@/lib/api", () => ({
  api: {
    getAccountSettings: vi.fn().mockResolvedValue({
      anthropic: { configured: false, preview: null },
      openai: { configured: false, preview: null },
      gemini: { configured: false, preview: null },
      databricks: {
        configured: true,
        host_preview: "https://adb-***.azuredatabricks.net",
        warehouse_id: "abc",
      },
      selected_model: "claude-sonnet-4-5-20250929",
      selected_provider: "anthropic",
      has_anthropic_key: false,
      anthropic_key_preview: null,
    }),
  },
}));

// AuthGuard checks localStorage for bp_api_key; set it so children render.
beforeEach(() => {
  localStorage.setItem("bp_api_key", "test-key");
});

async function renderAndWait(ui: React.ReactElement) {
  let result: ReturnType<typeof render>;
  await act(async () => {
    result = render(ui);
  });
  // Wait for DatabricksGuard's async settings check to resolve.
  await waitFor(() => {
    expect(document.querySelector("main")?.textContent).not.toContain("Checking Databricks");
  });
  return result!;
}

describe("TestingLayout", () => {
  it("renders its children", async () => {
    await renderAndWait(<TestingLayout><p>test content</p></TestingLayout>);
    expect(screen.getByText("test content")).toBeInTheDocument();
  });

  it("renders the Sidebar (aside landmark)", async () => {
    await renderAndWait(<TestingLayout><p>child</p></TestingLayout>);
    expect(document.querySelector("aside")).toBeInTheDocument();
  });

  it("renders the Header (sticky header element)", async () => {
    await renderAndWait(<TestingLayout><p>child</p></TestingLayout>);
    expect(document.querySelector("header")).toBeInTheDocument();
  });

  it("renders children inside a main element", async () => {
    await renderAndWait(<TestingLayout><p>main content</p></TestingLayout>);
    const main = document.querySelector("main");
    expect(main).toBeInTheDocument();
    expect(main!.textContent).toContain("main content");
  });

  it("wraps output in a full-height container (smoke test — no crash)", async () => {
    const { container } = await renderAndWait(<TestingLayout><span>ok</span></TestingLayout>);
    expect(container.firstChild).toBeInTheDocument();
  });
});
