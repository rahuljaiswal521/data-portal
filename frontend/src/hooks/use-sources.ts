import useSWR from "swr";
import { api } from "@/lib/api";
import type {
  DashboardStats,
  DeadLetterResponse,
  RunHistoryResponse,
  SourceDetail,
  SourceListResponse,
} from "@/types";

export function useSources(params?: Record<string, string>) {
  const key = params
    ? `/bronze/sources?${new URLSearchParams(params)}`
    : "/bronze/sources";
  return useSWR<SourceListResponse>(key, () => api.listSources(params));
}

export function useSource(name: string | null) {
  return useSWR<SourceDetail>(
    name ? `/bronze/sources/${name}` : null,
    () => api.getSource(name!)
  );
}

export function useDashboardStats() {
  return useSWR<DashboardStats>("/bronze/stats", api.getDashboardStats);
}

export function useRunHistory(name: string | null, limit = 50) {
  return useSWR<RunHistoryResponse>(
    name ? `/bronze/sources/${name}/runs` : null,
    () => api.getRunHistory(name!, limit)
  );
}

export function useDeadLetters(name: string | null, limit = 20) {
  return useSWR<DeadLetterResponse>(
    name ? `/bronze/sources/${name}/dead-letters` : null,
    () => api.getDeadLetters(name!, limit)
  );
}
