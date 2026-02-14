import { API_BASE_URL } from "./constants";
import type { ChatResponse, IndexStatus } from "@/types";

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
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || res.statusText);
  }

  return res.json();
}

export const api = {
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
};

export { ApiError };
