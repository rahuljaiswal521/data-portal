import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api, ApiError } from "@/lib/api";

const BASE = "http://localhost:8000/api/v1";

function mockFetch(body: unknown, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    json: () => Promise.resolve(body),
  });
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("api.listSources()", () => {
  it("calls GET /bronze/sources", async () => {
    global.fetch = mockFetch({ sources: [] });
    await api.listSources();
    expect(global.fetch).toHaveBeenCalledWith(
      `${BASE}/bronze/sources`,
      expect.objectContaining({ headers: expect.any(Object) })
    );
  });

  it("appends query string when params provided", async () => {
    global.fetch = mockFetch({ sources: [] });
    await api.listSources({ source_type: "jdbc" });
    expect(global.fetch).toHaveBeenCalledWith(
      `${BASE}/bronze/sources?source_type=jdbc`,
      expect.anything()
    );
  });
});

describe("api.getSource()", () => {
  it("calls GET /bronze/sources/{name}", async () => {
    global.fetch = mockFetch({ name: "my_source" });
    await api.getSource("my_source");
    expect(global.fetch).toHaveBeenCalledWith(
      `${BASE}/bronze/sources/my_source`,
      expect.anything()
    );
  });
});

describe("api.createSource()", () => {
  it("calls POST /bronze/sources with JSON body", async () => {
    global.fetch = mockFetch({ name: "new_source" });
    const data = { name: "new_source", source_type: "jdbc" };
    await api.createSource(data);
    expect(global.fetch).toHaveBeenCalledWith(
      `${BASE}/bronze/sources`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(data),
      })
    );
  });
});

describe("api.deleteSource()", () => {
  it("calls DELETE /bronze/sources/{name}", async () => {
    global.fetch = mockFetch({ deleted: true });
    await api.deleteSource("old_source");
    expect(global.fetch).toHaveBeenCalledWith(
      `${BASE}/bronze/sources/old_source`,
      expect.objectContaining({ method: "DELETE" })
    );
  });
});

describe("api.getDashboardStats()", () => {
  it("calls GET /bronze/stats", async () => {
    global.fetch = mockFetch({ total_sources: 3 });
    await api.getDashboardStats();
    expect(global.fetch).toHaveBeenCalledWith(
      `${BASE}/bronze/stats`,
      expect.anything()
    );
  });
});

describe("error handling", () => {
  it("throws ApiError with status and detail on non-200", async () => {
    global.fetch = mockFetch({ detail: "Not found" }, 404);
    await expect(api.getSource("nonexistent")).rejects.toThrow("Not found");
    await expect(api.getSource("nonexistent")).rejects.toBeInstanceOf(ApiError);
  });

  it("ApiError has correct status", async () => {
    global.fetch = mockFetch({ detail: "Server error" }, 500);
    try {
      await api.getSource("x");
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      expect((e as ApiError).status).toBe(500);
    }
  });

  it("falls back to statusText when body has no detail", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
      json: () => Promise.reject(new Error("no json")),
    });
    await expect(api.getSource("x")).rejects.toThrow("Service Unavailable");
  });
});

describe("API key header injection", () => {
  it("sends X-API-Key header when key is set in localStorage", async () => {
    localStorage.setItem("bp_api_key", "test-key-123");
    global.fetch = mockFetch({ sources: [] });
    await api.listSources();
    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({ "X-API-Key": "test-key-123" }),
      })
    );
  });

  it("does not send X-API-Key when no key stored", async () => {
    global.fetch = mockFetch({ sources: [] });
    await api.listSources();
    const [, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(options.headers).not.toHaveProperty("X-API-Key");
  });
});

describe("api.suggestEnterpriseModelStream()", () => {
  it("parses SSE chunks and returns final JSON", async () => {
    const finalObj = { domains: [], ungrouped_tables: [], overall_reasoning: "done" };
    const finalJson = JSON.stringify(finalObj);
    const encoder = new TextEncoder();

    const chunk1 = finalJson.slice(0, 10);
    const chunk2 = finalJson.slice(10);

    const sseLines = [
      `data: ${JSON.stringify({ chunk: chunk1 })}`,
      `data: ${JSON.stringify({ chunk: chunk2 })}`,
      "data: [DONE]",
    ].join("\n");

    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(sseLines));
        controller.close();
      },
    });

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: stream,
    });

    const onChunk = vi.fn();
    const result = await api.suggestEnterpriseModelStream(["dev.bronze.orders"], "dev", onChunk);

    expect(onChunk).toHaveBeenCalled();
    expect(result).toEqual(finalObj);
  });
});
