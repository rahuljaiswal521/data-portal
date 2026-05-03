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

// jsdom/happy-dom provides a real localStorage; window.location is read-only
// but we can stub the href setter via Object.defineProperty in the auto-redirect tests.

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── api.login ───────────────────────────────────────────────────────────

describe("api.login()", () => {
  it("POSTs to /auth/login", async () => {
    global.fetch = mockFetch({
      api_key: "bp_x",
      tenant_id: "default",
      username: "admin",
      display_name: "Admin",
      role: "admin",
    });
    await api.login({ username: "admin", password: "pw" });
    expect(global.fetch).toHaveBeenCalledWith(
      `${BASE}/auth/login`,
      expect.objectContaining({ method: "POST" })
    );
  });

  it("sends Content-Type: application/json", async () => {
    global.fetch = mockFetch({
      api_key: "bp_x",
      tenant_id: "default",
      username: "admin",
      display_name: null,
      role: "user",
    });
    await api.login({ username: "admin", password: "pw" });
    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const init = call[1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("serialises username+password into the request body", async () => {
    global.fetch = mockFetch({
      api_key: "bp_x",
      tenant_id: "default",
      username: "admin",
      display_name: null,
      role: "user",
    });
    await api.login({ username: "admin", password: "secret" });
    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const init = call[1] as RequestInit;
    expect(init.body).toBe(JSON.stringify({ username: "admin", password: "secret" }));
  });

  it("returns the parsed JSON body on success", async () => {
    global.fetch = mockFetch({
      api_key: "bp_token",
      tenant_id: "default",
      username: "admin",
      display_name: "Administrator",
      role: "admin",
    });
    const res = await api.login({ username: "admin", password: "pw" });
    expect(res.api_key).toBe("bp_token");
    expect(res.role).toBe("admin");
  });
});

// ── api.logout ──────────────────────────────────────────────────────────

describe("api.logout()", () => {
  it("POSTs to /auth/logout", async () => {
    global.fetch = mockFetch({ success: true });
    await api.logout();
    expect(global.fetch).toHaveBeenCalledWith(
      `${BASE}/auth/logout`,
      expect.objectContaining({ method: "POST" })
    );
  });

  it("returns the parsed body", async () => {
    global.fetch = mockFetch({ success: true });
    const res = await api.logout();
    expect(res).toEqual({ success: true });
  });
});

// ── api.getCurrentUser ──────────────────────────────────────────────────

describe("api.getCurrentUser()", () => {
  it("GETs /auth/me (no explicit method = GET)", async () => {
    global.fetch = mockFetch({
      tenant_id: "default",
      username: "admin",
      display_name: "Admin",
      role: "admin",
      last_login: null,
    });
    await api.getCurrentUser();
    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(call[0]).toBe(`${BASE}/auth/me`);
    // request() doesn't set method explicitly for GETs.
    const init = call[1] as RequestInit;
    expect(init.method).toBeUndefined();
  });

  it("includes X-API-Key header when key is in localStorage", async () => {
    localStorage.setItem("bp_api_key", "bp_stored");
    global.fetch = mockFetch({
      tenant_id: "default",
      username: "admin",
      display_name: null,
      role: "user",
      last_login: null,
    });
    await api.getCurrentUser();
    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const init = call[1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers["X-API-Key"]).toBe("bp_stored");
  });

  it("returns the profile from the JSON body", async () => {
    global.fetch = mockFetch({
      tenant_id: "default",
      username: "alice",
      display_name: "Alice",
      role: "admin",
      last_login: "2026-04-24T08:00:00",
    });
    const me = await api.getCurrentUser();
    expect(me.username).toBe("alice");
    expect(me.role).toBe("admin");
  });
});

// ── 401 auto-redirect logic — login excluded, others included ───────────

describe("request() — 401 auto-redirect behaviour", () => {
  let originalLocation: Location;

  beforeEach(() => {
    originalLocation = window.location;
    // Replace window.location with a settable stub to capture href writes.
    // happy-dom allows redefining window.location.
    Object.defineProperty(window, "location", {
      configurable: true,
      writable: true,
      value: { ...originalLocation, href: "" },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      writable: true,
      value: originalLocation,
    });
  });

  it("401 on /auth/login does NOT clear bp_api_key", async () => {
    localStorage.setItem("bp_api_key", "preserved");
    global.fetch = mockFetch({ detail: "Invalid username or password" }, 401);

    await expect(
      api.login({ username: "admin", password: "wrong" })
    ).rejects.toBeInstanceOf(ApiError);

    expect(localStorage.getItem("bp_api_key")).toBe("preserved");
  });

  it("401 on /auth/login does NOT redirect to /login", async () => {
    global.fetch = mockFetch({ detail: "Invalid username or password" }, 401);

    await expect(
      api.login({ username: "admin", password: "wrong" })
    ).rejects.toBeInstanceOf(ApiError);

    expect(window.location.href).toBe("");
  });

  it("401 on /auth/me DOES clear bp_api_key", async () => {
    localStorage.setItem("bp_api_key", "stale");
    global.fetch = mockFetch({ detail: "Missing X-API-Key header" }, 401);

    await expect(api.getCurrentUser()).rejects.toBeInstanceOf(ApiError);

    expect(localStorage.getItem("bp_api_key")).toBeNull();
  });

  it("401 on /auth/me DOES redirect to /login", async () => {
    localStorage.setItem("bp_api_key", "stale");
    global.fetch = mockFetch({ detail: "Missing X-API-Key header" }, 401);

    await expect(api.getCurrentUser()).rejects.toBeInstanceOf(ApiError);

    expect(window.location.href).toBe("/login");
  });

  it("401 on a non-auth endpoint also triggers the redirect", async () => {
    localStorage.setItem("bp_api_key", "stale");
    global.fetch = mockFetch({ detail: "Invalid or missing API key" }, 401);

    await expect(api.listSources()).rejects.toBeInstanceOf(ApiError);

    expect(localStorage.getItem("bp_api_key")).toBeNull();
    expect(window.location.href).toBe("/login");
  });
});
