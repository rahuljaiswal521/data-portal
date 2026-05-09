import { API_BASE_URL } from "./constants";
import type {
  AccountSettingsResponse,
  AvailableModelsResponse,
  ChatResponse,
  DatabricksCredentialsUpdate,
  DatabricksTestConnectionResponse,
  CurrentUser,
  IndexStatus,
  LoginRequest,
  LoginResponse,
} from "@/types";
import type {
  GenerateSuiteResponse,
  RunSuiteResponse,
  TcConfirmResponse,
  TcGeneratePreview,
  TestCaseResult,
  TestRunListResponse,
  TestRunResult,
  TestSuite,
  TestSuiteListResponse,
} from "@/types/testing";
import type {
  BronzeTableInfo,
  EnterpriseModelResponse,
  SilverDashboardStats,
  SilverDiagramResponse,
  SilverEntityCreateResponse,
  SilverEntityDeleteResponse,
  SilverEntityDetail,
  SilverEntityListResponse,
  SilverRunHistoryResponse,
  SilverValidationResponse,
  SuggestModelResponse,
  TableProfileResponse,
} from "@/types/silver";
import type {
  GoldCommitResponse,
  GoldMartIR,
  GoldMartSummary,
  GoldPreviewResponse,
  ReadinessReport,
} from "@/types/gold";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

function getApiKey(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("bp_api_key") || "";
  }
  return "";
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const apiKey = getApiKey();
  const extraHeaders: Record<string, string> = {};
  if (apiKey) {
    extraHeaders["X-API-Key"] = apiKey;
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...extraHeaders, ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    // Don't auto-redirect when the failing call is the login request itself —
    // let the login form display its own error.
    const isLoginCall = path === "/auth/login";
    if (res.status === 401 && !isLoginCall && typeof window !== "undefined") {
      localStorage.removeItem("bp_api_key");
      window.location.href = "/login";
    }
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || res.statusText);
  }

  return res.json();
}

export const api = {
  // Auth
  login: (body: LoginRequest) =>
    request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  logout: () => request<{ success: boolean }>("/auth/logout", { method: "POST" }),
  getCurrentUser: () => request<CurrentUser>("/auth/me"),

  // Sources
  listSources: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<any>(`/bronze/sources${qs}`);
  },
  getSource: (name: string) => request<any>(`/bronze/sources/${name}`),
  createSource: (data: any) =>
    request<any>("/bronze/sources", { method: "POST", body: JSON.stringify(data) }),
  updateSource: (name: string, data: any) =>
    request<any>(`/bronze/sources/${name}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteSource: (name: string) =>
    request<any>(`/bronze/sources/${name}`, { method: "DELETE" }),
  validateSource: (name: string, data: any) =>
    request<any>(`/bronze/sources/${name}/validate`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Deploy & trigger
  deploySource: (name: string) =>
    request<any>(`/bronze/sources/${name}/deploy`, { method: "POST" }),
  triggerRun: (name: string) =>
    request<any>(`/bronze/sources/${name}/trigger`, { method: "POST" }),

  // Monitoring
  getRunHistory: (name: string, limit = 50) =>
    request<any>(`/bronze/sources/${name}/runs?limit=${limit}`),
  getDeadLetters: (name: string, limit = 20) =>
    request<any>(`/bronze/sources/${name}/dead-letters?limit=${limit}`),
  getDashboardStats: () => request<any>("/bronze/stats"),

  // Other
  getEnvironments: () => request<any>("/environments"),
  getHealth: () => request<any>("/health"),

  // Account settings
  getAccountSettings: () =>
    request<AccountSettingsResponse>("/account/settings"),
  // Per-provider key management
  setProviderKey: (provider: "anthropic" | "openai" | "gemini", api_key: string) =>
    request<AccountSettingsResponse>(`/account/settings/${provider}-key`, {
      method: "PUT",
      body: JSON.stringify({ api_key }),
    }),
  deleteProviderKey: (provider: "anthropic" | "openai" | "gemini") =>
    request<AccountSettingsResponse>(`/account/settings/${provider}-key`, {
      method: "DELETE",
    }),
  // Legacy — kept for backward compat
  updateAccountSettings: (anthropic_api_key: string) =>
    request<AccountSettingsResponse>("/account/settings", {
      method: "PUT",
      body: JSON.stringify({ anthropic_api_key }),
    }),
  deleteAnthropicKey: () =>
    request<AccountSettingsResponse>("/account/settings/anthropic-key", { method: "DELETE" }),
  // Databricks credentials
  setDatabricksCredentials: (creds: DatabricksCredentialsUpdate) =>
    request<AccountSettingsResponse>("/account/settings/databricks", {
      method: "PUT",
      body: JSON.stringify(creds),
    }),
  deleteDatabricksCredentials: () =>
    request<AccountSettingsResponse>("/account/settings/databricks", { method: "DELETE" }),
  testDatabricksConnection: (creds: DatabricksCredentialsUpdate) =>
    request<DatabricksTestConnectionResponse>("/account/settings/databricks/test", {
      method: "POST",
      body: JSON.stringify(creds),
    }),

  // Model selection
  listAvailableModels: () =>
    request<AvailableModelsResponse>("/account/settings/models"),
  setSelectedModel: (model_id: string) =>
    request<AccountSettingsResponse>("/account/settings/selected-model", {
      method: "PUT",
      body: JSON.stringify({ model_id }),
    }),

  // RAG Assistant
  chat: (data: { question: string; session_id?: string }) =>
    request<ChatResponse>("/rag/chat", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getChatHistory: (sessionId: string) =>
    request<any>(`/rag/chat/history?session_id=${sessionId}`),
  rebuildIndex: () =>
    request<any>("/rag/index/rebuild", { method: "POST" }),
  getIndexStatus: () => request<IndexStatus>("/rag/index/status"),

  // Silver Entities
  listSilverEntities: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<SilverEntityListResponse>(`/silver/entities${qs}`);
  },
  getSilverEntity: (name: string) =>
    request<SilverEntityDetail>(`/silver/entities/${name}`),
  createSilverEntity: (data: any) =>
    request<SilverEntityCreateResponse>("/silver/entities", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateSilverEntity: (name: string, data: any) =>
    request<any>(`/silver/entities/${name}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  deleteSilverEntity: (name: string) =>
    request<SilverEntityDeleteResponse>(`/silver/entities/${name}`, {
      method: "DELETE",
    }),
  validateSilverEntity: (name: string, data: any) =>
    request<SilverValidationResponse>(`/silver/entities/${name}/validate`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deploySilverEntity: (name: string) =>
    request<any>(`/silver/entities/${name}/deploy`, { method: "POST" }),
  triggerSilverRun: (name: string) =>
    request<any>(`/silver/entities/${name}/trigger`, { method: "POST" }),

  getSilverStats: () => request<SilverDashboardStats>("/silver/stats"),
  getSilverDiagram: () => request<SilverDiagramResponse>("/silver/diagram"),
  getSilverRuns: (name: string, limit = 50) =>
    request<SilverRunHistoryResponse>(
      `/silver/entities/${name}/runs?limit=${limit}`
    ),

  // Silver AI Modeling
  profileBronzeTable: (data: { catalog: string; schema: string; table: string }) =>
    request<TableProfileResponse>("/silver/modeling/profile-table", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  suggestSilverModel: (data: {
    tables: { full_table_name: string; column_definitions?: string | null }[];
    domain_hint?: string | null;
    entity_name_hint?: string | null;
  }) =>
    request<SuggestModelResponse>("/silver/modeling/suggest-model", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  listBronzeTables: (catalog = "dev", schema = "bronze") =>
    request<BronzeTableInfo[]>(
      `/silver/modeling/bronze-tables?catalog=${catalog}&schema=${schema}`
    ),

  suggestEnterpriseModel: (tables: string[], catalog = "dev") =>
    request<EnterpriseModelResponse>("/silver/modeling/suggest-enterprise-model", {
      method: "POST",
      body: JSON.stringify({ tables, catalog }),
    }),

  // Testing
  listTestSuites: () =>
    request<TestSuiteListResponse>("/testing/suites"),
  getTestSuite: (sourceName: string) =>
    request<TestSuite>(`/testing/suites/${sourceName}`),
  generateTestSuite: (sourceName: string) =>
    request<GenerateSuiteResponse>(`/testing/suites/${sourceName}/generate`, {
      method: "POST",
    }),
  runTestSuite: (sourceName: string) =>
    request<RunSuiteResponse>(`/testing/suites/${sourceName}/run`, {
      method: "POST",
    }),
  cancelTestSuite: (sourceName: string) =>
    request<{ message: string }>(`/testing/suites/${sourceName}/cancel`, {
      method: "POST",
    }),
  getTestResults: (sourceName: string) =>
    request<TestRunListResponse>(`/testing/suites/${sourceName}/results`),
  getLatestTestResult: (sourceName: string) =>
    request<TestRunResult>(`/testing/suites/${sourceName}/results/latest`),
  runSingleTc: (sourceName: string, tcId: string) =>
    request<TestCaseResult>(`/testing/suites/${sourceName}/run-tc/${tcId}`, {
      method: "POST",
    }),
  getTestReportUrl: (sourceName: string) =>
    `${API_BASE_URL}/testing/suites/${sourceName}/results/latest/report`,

  // AI test case generator
  aiGenerateTc: (sourceName: string, prompt: string) =>
    request<TcGeneratePreview>(`/testing/suites/${sourceName}/ai-generate`, {
      method: "POST",
      body: JSON.stringify({ prompt }),
    }),
  aiConfirmTc: (sourceName: string, preview: TcGeneratePreview) =>
    request<TcConfirmResponse>(`/testing/suites/${sourceName}/ai-confirm`, {
      method: "POST",
      body: JSON.stringify(preview),
    }),

  suggestEnterpriseModelStream: async (
    tables: string[],
    catalog = "dev",
    onChunk: (text: string) => void
  ): Promise<EnterpriseModelResponse> => {
    const apiKey = getApiKey();
    const res = await fetch(
      `${API_BASE_URL}/silver/modeling/suggest-enterprise-model/stream`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(apiKey ? { "X-API-Key": apiKey } : {}),
        },
        body: JSON.stringify({ tables, catalog }),
      }
    );
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(res.status, body.detail || res.statusText);
    }

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let accumulated = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const raw = decoder.decode(value, { stream: true });
      for (const line of raw.split("\n")) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;
        const payload = trimmed.slice(5).trim();
        if (payload === "[DONE]") break;
        try {
          const parsed = JSON.parse(payload);
          if (parsed.error) throw new Error(parsed.error);
          if (parsed.chunk) {
            accumulated += parsed.chunk;
            onChunk(accumulated);
          }
        } catch {
          // skip malformed lines
        }
      }
    }

    // Parse the accumulated JSON into the typed response
    const cleaned = accumulated.trim().replace(/^```[^\n]*\n?/, "").replace(/```$/, "").trim();
    try {
      return JSON.parse(cleaned) as EnterpriseModelResponse;
    } catch {
      throw new Error(`AI returned invalid JSON: ${accumulated.slice(0, 200)}`);
    }
  },
};

// ── Gold layer API ─────────────────────────────────────────────────────────

export const goldApi = {
  listMarts: () => request<GoldMartSummary[]>("/gold/marts"),

  getMart: (name: string) => request<GoldMartIR>(`/gold/marts/${name}`),

  deleteMart: (name: string) =>
    request<void>(`/gold/marts/${name}`, { method: "DELETE" }),

  previewIngest: async (
    file: File,
    defaultMartName: string,
  ): Promise<GoldPreviewResponse> => {
    const apiKey =
      typeof window !== "undefined"
        ? localStorage.getItem("bp_api_key") || ""
        : "";
    const fd = new FormData();
    fd.append("file", file);
    fd.append("default_mart_name", defaultMartName);

    const res = await fetch(`${API_BASE_URL}/gold/ingest/preview`, {
      method: "POST",
      headers: apiKey ? { "X-API-Key": apiKey } : undefined,
      body: fd,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(res.status, body.detail || res.statusText);
    }
    return res.json();
  },

  commitIngest: (ir: GoldMartIR, overwrite: boolean) =>
    request<GoldCommitResponse>("/gold/ingest/commit", {
      method: "POST",
      body: JSON.stringify({ ir, overwrite }),
    }),

  checkReadiness: (ir: GoldMartIR, includeAiSuggestions: boolean = false) =>
    request<ReadinessReport>("/gold/ingest/readiness", {
      method: "POST",
      body: JSON.stringify({
        ir,
        include_ai_suggestions: includeAiSuggestions,
      }),
    }),
};

export { ApiError };
