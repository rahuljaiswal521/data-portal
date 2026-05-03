import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";

vi.mock("swr");
vi.mock("@/lib/api", () => ({
  api: {
    getCurrentUser: vi.fn(),
  },
}));

import useSWR from "swr";
import { api } from "@/lib/api";
import { useCurrentUser } from "@/hooks/use-current-user";

const mockedUseSWR = vi.mocked(useSWR);

beforeEach(() => {
  mockedUseSWR.mockReset();
  mockedUseSWR.mockReturnValue({
    data: undefined,
    isLoading: true,
    error: undefined,
    mutate: vi.fn(),
    isValidating: false,
  } as ReturnType<typeof useSWR>);
});

describe("useCurrentUser()", () => {
  it("calls useSWR with /auth/me key", () => {
    renderHook(() => useCurrentUser());
    expect(mockedUseSWR).toHaveBeenCalled();
    const call = mockedUseSWR.mock.calls[0];
    expect(call[0]).toBe("/auth/me");
  });

  it("passes api.getCurrentUser as the fetcher", () => {
    renderHook(() => useCurrentUser());
    const call = mockedUseSWR.mock.calls[0];
    expect(call[1]).toBe(api.getCurrentUser);
  });

  it("disables revalidateOnFocus", () => {
    renderHook(() => useCurrentUser());
    const call = mockedUseSWR.mock.calls[0] as unknown as [
      string,
      unknown,
      Record<string, unknown>
    ];
    expect(call[2].revalidateOnFocus).toBe(false);
  });

  it("disables shouldRetryOnError", () => {
    renderHook(() => useCurrentUser());
    const call = mockedUseSWR.mock.calls[0] as unknown as [
      string,
      unknown,
      Record<string, unknown>
    ];
    expect(call[2].shouldRetryOnError).toBe(false);
  });

  it("returns the data from useSWR", () => {
    mockedUseSWR.mockReturnValue({
      data: {
        tenant_id: "default",
        username: "alice",
        display_name: "Alice",
        role: "admin",
        last_login: "2026-04-24T10:00:00",
      } as never,
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
      isValidating: false,
    } as ReturnType<typeof useSWR>);

    const { result } = renderHook(() => useCurrentUser());
    expect(result.current.data).toEqual({
      tenant_id: "default",
      username: "alice",
      display_name: "Alice",
      role: "admin",
      last_login: "2026-04-24T10:00:00",
    });
  });

  it("returns isLoading from useSWR", () => {
    const { result } = renderHook(() => useCurrentUser());
    expect(result.current.isLoading).toBe(true);
  });
});
