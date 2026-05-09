import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act, fireEvent } from "@testing-library/react";
import SettingsPage from "@/app/settings/page";
import type { AccountSettingsResponse, AvailableModel, AvailableModelsResponse } from "@/types";

// ── Mock the api module ────────────────────────────────────────────────────────

vi.mock("@/lib/api", () => ({
  api: {
    getAccountSettings: vi.fn(),
    setProviderKey: vi.fn(),
    deleteProviderKey: vi.fn(),
    updateAccountSettings: vi.fn(),
    deleteAnthropicKey: vi.fn(),
    listAvailableModels: vi.fn(),
    setSelectedModel: vi.fn(),
  },
}));

// ── Mock the toast hook ────────────────────────────────────────────────────────

const mockToast = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: mockToast }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import { api } from "@/lib/api";

const mockedGetSettings = vi.mocked(api.getAccountSettings);
const mockedSetProviderKey = vi.mocked(api.setProviderKey);
const mockedDeleteProviderKey = vi.mocked(api.deleteProviderKey);
const mockedListModels = vi.mocked(api.listAvailableModels);
const mockedSetSelectedModel = vi.mocked(api.setSelectedModel);

// ── Response builders ─────────────────────────────────────────────────────────

const AVAILABLE_MODELS: AvailableModel[] = [
  { id: "claude-sonnet-4-5-20250929", name: "Claude Sonnet 4.5", description: "Recommended", provider: "anthropic" },
  { id: "claude-haiku-4-5-20251001", name: "Claude Haiku 4.5", description: "Fastest", provider: "anthropic" },
  { id: "gpt-4.1", name: "GPT-4.1", description: "1M context", provider: "openai" },
  { id: "gpt-4.1-mini", name: "GPT-4.1 Mini", description: "Fast/affordable", provider: "openai" },
  { id: "gemini-2.5-pro", name: "Gemini 2.5 Pro", description: "Strong analysis", provider: "gemini" },
  { id: "gemini-2.5-flash", name: "Gemini 2.5 Flash", description: "Fastest", provider: "gemini" },
];

function makeModelsResponse(): AvailableModelsResponse {
  return { models: AVAILABLE_MODELS, default_model: "claude-sonnet-4-5-20250929" };
}

function makeSettings(overrides?: Partial<AccountSettingsResponse>): AccountSettingsResponse {
  return {
    anthropic: { configured: false, preview: null },
    openai: { configured: false, preview: null },
    gemini: { configured: false, preview: null },
    databricks: { configured: false, host_preview: null, warehouse_id: null },
    selected_model: "claude-sonnet-4-5-20250929",
    selected_provider: "anthropic",
    has_anthropic_key: false,
    anthropic_key_preview: null,
    ...overrides,
  };
}

function makeSettingsAllConfigured(): AccountSettingsResponse {
  return {
    anthropic: { configured: true, preview: "sk-ant-a...EFGH" },
    openai: { configured: true, preview: "sk-proj-...WXYZ" },
    gemini: { configured: true, preview: "AIzaSy...1234" },
    databricks: {
      configured: true,
      host_preview: "https://adb-***.azuredatabricks.net",
      warehouse_id: "abcd1234efgh5678",
    },
    selected_model: "claude-sonnet-4-5-20250929",
    selected_provider: "anthropic",
    has_anthropic_key: true,
    anthropic_key_preview: "sk-ant-a...EFGH",
  };
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function renderPage() {
  return render(<SettingsPage />);
}

// ── Setup / teardown ──────────────────────────────────────────────────────────

beforeEach(() => {
  mockToast.mockClear();
  mockedSetProviderKey.mockResolvedValue(makeSettings());
  mockedDeleteProviderKey.mockResolvedValue(makeSettings());
  mockedListModels.mockResolvedValue(makeModelsResponse());
  mockedSetSelectedModel.mockResolvedValue(makeSettings());
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Page structure ─────────────────────────────────────────────────────────────

describe("SettingsPage — page structure", () => {
  beforeEach(() => {
    mockedGetSettings.mockResolvedValue(makeSettings());
  });

  it("renders the Settings heading", async () => {
    await act(async () => renderPage());
    expect(screen.getByRole("heading", { name: /Settings/i })).toBeInTheDocument();
  });

  it("renders the AI Provider Keys section heading", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      expect(screen.getByText(/AI Provider Keys/i)).toBeInTheDocument();
    });
  });

  it("renders the Active Model section heading", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Active Model/i })).toBeInTheDocument();
    });
  });

  it("renders all three provider section labels", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      expect(screen.getByText("Anthropic")).toBeInTheDocument();
      expect(screen.getByText("OpenAI")).toBeInTheDocument();
      expect(screen.getByText("Google Gemini")).toBeInTheDocument();
    });
  });

  it("renders Anthropic placeholder text", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/sk-ant/i)).toBeInTheDocument();
    });
  });

  it("renders OpenAI placeholder text", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/sk-proj/i)).toBeInTheDocument();
    });
  });

  it("renders Gemini placeholder text", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/AIzaSy/i)).toBeInTheDocument();
    });
  });

  it("shows loading spinner initially", () => {
    mockedGetSettings.mockReturnValue(new Promise(() => {})); // never resolves
    renderPage();
    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });
});

// ── No keys configured state ──────────────────────────────────────────────────

describe("SettingsPage — no keys configured", () => {
  beforeEach(() => {
    mockedGetSettings.mockResolvedValue(makeSettings());
  });

  it("all three providers show 'Not set' badge", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      // 3 AI providers + 1 Databricks card all show "Not set" by default
      const badges = screen.getAllByText("Not set");
      expect(badges).toHaveLength(4);
    });
  });

  it("shows Anthropic-required warning banner when Anthropic key not set", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      expect(screen.getByText(/Anthropic key required/i)).toBeInTheDocument();
    });
  });

  it("warning banner uses error styling", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      const banner = screen.getByText(/Anthropic key required/i).closest("div");
      expect(banner?.className).toMatch(/bg-error/);
    });
  });

  it("all three Save buttons are present", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      const saveBtns = screen.getAllByRole("button", { name: /Save/i });
      expect(saveBtns.length).toBeGreaterThanOrEqual(3);
    });
  });

  it("does NOT show 'Configured' badge for any provider", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      expect(screen.queryByText("Configured")).not.toBeInTheDocument();
    });
  });
});

// ── All keys configured state ─────────────────────────────────────────────────

describe("SettingsPage — all keys configured", () => {
  beforeEach(() => {
    mockedGetSettings.mockResolvedValue(makeSettingsAllConfigured());
  });

  it("shows 'Configured' badge for all three providers", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      // 3 AI providers + 1 Databricks card all show "Configured"
      const badges = screen.getAllByText("Configured");
      expect(badges).toHaveLength(4);
    });
  });

  it("shows Anthropic masked key preview", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      expect(screen.getByText("sk-ant-a...EFGH")).toBeInTheDocument();
    });
  });

  it("shows OpenAI masked key preview", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      expect(screen.getByText("sk-proj-...WXYZ")).toBeInTheDocument();
    });
  });

  it("shows Gemini masked key preview", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      expect(screen.getByText("AIzaSy...1234")).toBeInTheDocument();
    });
  });

  it("does NOT show the Anthropic-required warning banner when Anthropic is set", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      expect(screen.queryByText(/Anthropic key required/i)).not.toBeInTheDocument();
    });
  });

  it("shows 'Replace' button text when key is set", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      const replaceButtons = screen.getAllByRole("button", { name: /Replace/i });
      expect(replaceButtons.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows Remove buttons for configured providers", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      // 3 AI provider Remove buttons + 1 Databricks "Remove credentials"
      const removeButtons = screen.getAllByRole("button", { name: /Remove/i });
      expect(removeButtons).toHaveLength(4);
    });
  });
});

// ── Partial configuration ─────────────────────────────────────────────────────

describe("SettingsPage — partial configuration", () => {
  it("shows Configured for Anthropic only, Not set for others", async () => {
    mockedGetSettings.mockResolvedValue(
      makeSettings({ anthropic: { configured: true, preview: "sk-ant-a...ABCD" }, has_anthropic_key: true, anthropic_key_preview: "sk-ant-a...ABCD" })
    );
    await act(async () => renderPage());
    await waitFor(() => {
      // Anthropic configured + (OpenAI, Gemini, Databricks) not set
      expect(screen.getByText("Configured")).toBeInTheDocument();
      const notSet = screen.getAllByText("Not set");
      expect(notSet).toHaveLength(3);
    });
  });

  it("does NOT show warning when Anthropic is configured even if others are not", async () => {
    mockedGetSettings.mockResolvedValue(
      makeSettings({ anthropic: { configured: true, preview: "sk-ant-a...ABCD" }, has_anthropic_key: true, anthropic_key_preview: "sk-ant-a...ABCD" })
    );
    await act(async () => renderPage());
    await waitFor(() => {
      expect(screen.queryByText(/Anthropic key required/i)).not.toBeInTheDocument();
    });
  });
});

// ── Save key interaction ──────────────────────────────────────────────────────

describe("SettingsPage — save key interactions", () => {
  beforeEach(() => {
    mockedGetSettings.mockResolvedValue(makeSettings());
    mockedSetProviderKey.mockResolvedValue(
      makeSettings({ anthropic: { configured: true, preview: "sk-ant-a...TEST" }, has_anthropic_key: true })
    );
  });

  it("calls setProviderKey with 'anthropic' when Anthropic form is submitted", async () => {
    await act(async () => renderPage());
    await waitFor(() => screen.getByPlaceholderText(/sk-ant/i));

    const input = screen.getByPlaceholderText(/sk-ant/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "sk-ant-api03-testkey12345" } });

    // Submit the Anthropic-specific form (input's enclosing form). Multiple Save
    // buttons now exist (Databricks card + 3 AI providers) — submit by form.
    const form = input.closest("form")!;
    await act(async () => fireEvent.submit(form));

    await waitFor(() => {
      expect(mockedSetProviderKey).toHaveBeenCalledWith("anthropic", "sk-ant-api03-testkey12345");
    });
  });

  it("shows success toast after saving", async () => {
    await act(async () => renderPage());
    await waitFor(() => screen.getByPlaceholderText(/sk-ant/i));

    const input = screen.getByPlaceholderText(/sk-ant/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "sk-ant-api03-testkey12345" } });

    const form = input.closest("form")!;
    await act(async () => fireEvent.submit(form));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.stringContaining("saved"), "success");
    });
  });
});

// ── Error state ───────────────────────────────────────────────────────────────

describe("SettingsPage — error handling", () => {
  it("shows error toast when getAccountSettings fails", async () => {
    mockedGetSettings.mockRejectedValue(new Error("Network error"));
    mockedListModels.mockResolvedValue(makeModelsResponse());
    await act(async () => renderPage());
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith("Failed to load settings", "error");
    });
  });

  it("shows error toast when listAvailableModels fails", async () => {
    mockedGetSettings.mockResolvedValue(makeSettings());
    mockedListModels.mockRejectedValue(new Error("Network error"));
    await act(async () => renderPage());
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith("Failed to load settings", "error");
    });
  });
});

// ── Model selector ────────────────────────────────────────────────────────────

describe("SettingsPage — model selector", () => {
  beforeEach(() => {
    mockedGetSettings.mockResolvedValue(makeSettings());
  });

  it("calls api.listAvailableModels on mount", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      expect(mockedListModels).toHaveBeenCalledTimes(1);
    });
  });

  it("renders the model dropdown with provider-grouped options", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      const select = screen.getByLabelText(/Active AI model/i) as HTMLSelectElement;
      expect(select).toBeInTheDocument();
      // optgroups: Anthropic / OpenAI / Google Gemini
      const optgroups = select.querySelectorAll("optgroup");
      const labels = Array.from(optgroups).map((g) => g.getAttribute("label"));
      expect(labels).toEqual(expect.arrayContaining(["Anthropic", "OpenAI", "Google Gemini"]));
    });
  });

  it("renders all models from the catalogue as <option> elements", async () => {
    await act(async () => renderPage());
    await waitFor(() => {
      const select = screen.getByLabelText(/Active AI model/i) as HTMLSelectElement;
      const opts = Array.from(select.querySelectorAll("option")).map((o) => o.value);
      for (const m of AVAILABLE_MODELS) {
        expect(opts).toContain(m.id);
      }
    });
  });

  it("shows the selected model as the dropdown value", async () => {
    mockedGetSettings.mockResolvedValue(makeSettings({ selected_model: "gpt-4.1", selected_provider: "openai" }));
    await act(async () => renderPage());
    await waitFor(() => {
      const select = screen.getByLabelText(/Active AI model/i) as HTMLSelectElement;
      expect(select.value).toBe("gpt-4.1");
    });
  });

  it("calls api.setSelectedModel when the dropdown changes", async () => {
    mockedSetSelectedModel.mockResolvedValue(makeSettings({ selected_model: "gpt-4.1", selected_provider: "openai" }));
    await act(async () => renderPage());
    await waitFor(() => screen.getByLabelText(/Active AI model/i));

    const select = screen.getByLabelText(/Active AI model/i) as HTMLSelectElement;
    await act(async () => {
      fireEvent.change(select, { target: { value: "gpt-4.1" } });
    });

    await waitFor(() => {
      expect(mockedSetSelectedModel).toHaveBeenCalledWith("gpt-4.1");
    });
  });

  it("does not call setSelectedModel when selecting the current value", async () => {
    await act(async () => renderPage());
    await waitFor(() => screen.getByLabelText(/Active AI model/i));

    const select = screen.getByLabelText(/Active AI model/i) as HTMLSelectElement;
    await act(async () => {
      fireEvent.change(select, { target: { value: "claude-sonnet-4-5-20250929" } });
    });

    expect(mockedSetSelectedModel).not.toHaveBeenCalled();
  });

  it("shows a success toast after the model is changed", async () => {
    mockedSetSelectedModel.mockResolvedValue(makeSettings({ selected_model: "gemini-2.5-pro", selected_provider: "gemini" }));
    await act(async () => renderPage());
    await waitFor(() => screen.getByLabelText(/Active AI model/i));

    const select = screen.getByLabelText(/Active AI model/i) as HTMLSelectElement;
    await act(async () => {
      fireEvent.change(select, { target: { value: "gemini-2.5-pro" } });
    });

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.stringContaining("gemini-2.5-pro"),
        "success",
      );
    });
  });

  it("shows an error toast when setSelectedModel rejects", async () => {
    mockedSetSelectedModel.mockRejectedValue(new Error("Unknown model id"));
    await act(async () => renderPage());
    await waitFor(() => screen.getByLabelText(/Active AI model/i));

    const select = screen.getByLabelText(/Active AI model/i) as HTMLSelectElement;
    await act(async () => {
      fireEvent.change(select, { target: { value: "gpt-4.1" } });
    });

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith("Unknown model id", "error");
    });
  });

  it("displays the currently active model id below the dropdown", async () => {
    mockedGetSettings.mockResolvedValue(
      makeSettings({ selected_model: "gpt-4.1-mini", selected_provider: "openai" }),
    );
    await act(async () => renderPage());
    await waitFor(() => {
      expect(screen.getByText("gpt-4.1-mini")).toBeInTheDocument();
    });
  });
});

// ── Warning banner per selected provider ──────────────────────────────────────

describe("SettingsPage — warning banner follows selected_provider", () => {
  it("shows 'OpenAI key required' warning when selected=openai and OpenAI key missing", async () => {
    mockedGetSettings.mockResolvedValue(
      makeSettings({
        selected_model: "gpt-4.1",
        selected_provider: "openai",
        anthropic: { configured: true, preview: "sk-ant-a...ABCD" },
        has_anthropic_key: true,
        anthropic_key_preview: "sk-ant-a...ABCD",
      }),
    );
    await act(async () => renderPage());
    await waitFor(() => {
      expect(screen.getByText(/OpenAI key required/i)).toBeInTheDocument();
    });
  });

  it("shows 'Google Gemini key required' warning when selected=gemini and Gemini key missing", async () => {
    mockedGetSettings.mockResolvedValue(
      makeSettings({
        selected_model: "gemini-2.5-pro",
        selected_provider: "gemini",
      }),
    );
    await act(async () => renderPage());
    await waitFor(() => {
      expect(screen.getByText(/Google Gemini key required/i)).toBeInTheDocument();
    });
  });

  it("hides the warning when the selected provider's key IS configured", async () => {
    mockedGetSettings.mockResolvedValue(
      makeSettings({
        selected_model: "gpt-4.1",
        selected_provider: "openai",
        openai: { configured: true, preview: "sk-proj-...ABCD" },
      }),
    );
    await act(async () => renderPage());
    await waitFor(() => {
      expect(screen.getByLabelText(/Active AI model/i)).toBeInTheDocument();
    });
    // No "key required" banner anywhere
    expect(screen.queryByText(/key required/i)).not.toBeInTheDocument();
  });

  it("warning text mentions the active model id", async () => {
    mockedGetSettings.mockResolvedValue(
      makeSettings({
        selected_model: "gpt-4.1",
        selected_provider: "openai",
      }),
    );
    await act(async () => renderPage());
    await waitFor(() => {
      // The warning banner contains the model id embedded in its prose
      const banner = screen.getByText(/OpenAI key required/i).closest("div");
      expect(banner?.textContent).toMatch(/gpt-4\.1/);
    });
  });
});
