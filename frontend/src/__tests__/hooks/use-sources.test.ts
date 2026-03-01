import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";

vi.mock("swr");
vi.mock("@/lib/api", () => ({
  api: {
    listSources: vi.fn(),
    getSource: vi.fn(),
    getDashboardStats: vi.fn(),
    getRunHistory: vi.fn(),
    getDeadLetters: vi.fn(),
  },
}));

import useSWR from "swr";
import {
  useSources,
  useSource,
  useDashboardStats,
  useRunHistory,
  useDeadLetters,
} from "@/hooks/use-sources";

const mockedUseSWR = vi.mocked(useSWR);

beforeEach(() => {
  mockedUseSWR.mockReturnValue({
    data: undefined,
    isLoading: true,
    error: undefined,
    mutate: vi.fn(),
    isValidating: false,
  } as ReturnType<typeof useSWR>);
});

describe("useSources()", () => {
  it("calls useSWR with /bronze/sources key (no params)", () => {
    renderHook(() => useSources());
    expect(mockedUseSWR).toHaveBeenCalledWith(
      "/bronze/sources",
      expect.any(Function)
    );
  });

  it("calls useSWR with query-string key when params provided", () => {
    renderHook(() => useSources({ source_type: "jdbc" }));
    expect(mockedUseSWR).toHaveBeenCalledWith(
      "/bronze/sources?source_type=jdbc",
      expect.any(Function)
    );
  });

  it("returns the value from useSWR", () => {
    mockedUseSWR.mockReturnValue({
      data: { sources: [] } as any,
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
      isValidating: false,
    } as ReturnType<typeof useSWR>);

    const { result } = renderHook(() => useSources());
    expect(result.current.isLoading).toBe(false);
  });
});

describe("useSource()", () => {
  it("calls useSWR with null key when name is null", () => {
    renderHook(() => useSource(null));
    expect(mockedUseSWR).toHaveBeenCalledWith(null, expect.any(Function));
  });

  it("calls useSWR with /bronze/sources/{name} key", () => {
    renderHook(() => useSource("my-source"));
    expect(mockedUseSWR).toHaveBeenCalledWith(
      "/bronze/sources/my-source",
      expect.any(Function)
    );
  });
});

describe("useDashboardStats()", () => {
  it("calls useSWR with /bronze/stats key", () => {
    renderHook(() => useDashboardStats());
    expect(mockedUseSWR).toHaveBeenCalledWith(
      "/bronze/stats",
      expect.any(Function)
    );
  });
});

describe("useRunHistory()", () => {
  it("calls useSWR with null key when name is null", () => {
    renderHook(() => useRunHistory(null));
    expect(mockedUseSWR).toHaveBeenCalledWith(null, expect.any(Function));
  });

  it("calls useSWR with run history key when name provided", () => {
    renderHook(() => useRunHistory("my-source"));
    expect(mockedUseSWR).toHaveBeenCalledWith(
      "/bronze/sources/my-source/runs",
      expect.any(Function)
    );
  });
});

describe("useDeadLetters()", () => {
  it("calls useSWR with null key when name is null", () => {
    renderHook(() => useDeadLetters(null));
    expect(mockedUseSWR).toHaveBeenCalledWith(null, expect.any(Function));
  });

  it("calls useSWR with dead-letters key when name provided", () => {
    renderHook(() => useDeadLetters("my-source"));
    expect(mockedUseSWR).toHaveBeenCalledWith(
      "/bronze/sources/my-source/dead-letters",
      expect.any(Function)
    );
  });
});
