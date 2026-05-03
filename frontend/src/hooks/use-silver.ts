import useSWR from "swr";
import { api } from "@/lib/api";
import type {
  SilverDashboardStats,
  SilverDiagramResponse,
  SilverEntityDetail,
  SilverEntityListResponse,
  SilverRunHistoryResponse,
} from "@/types/silver";

export function useSilverEntities(params?: Record<string, string>) {
  const key = params
    ? `/silver/entities?${new URLSearchParams(params)}`
    : "/silver/entities";
  return useSWR<SilverEntityListResponse>(key, () =>
    api.listSilverEntities(params)
  );
}

export function useSilverEntity(name: string | null) {
  return useSWR<SilverEntityDetail>(
    name ? `/silver/entities/${name}` : null,
    () => api.getSilverEntity(name!)
  );
}

export function useSilverStats() {
  return useSWR<SilverDashboardStats>("/silver/stats", api.getSilverStats);
}

export function useSilverRuns(name: string | null, limit = 50) {
  return useSWR<SilverRunHistoryResponse>(
    name ? `/silver/entities/${name}/runs` : null,
    () => api.getSilverRuns(name!, limit)
  );
}

export function useSilverDiagram() {
  return useSWR<SilverDiagramResponse>(
    "/silver/diagram",
    api.getSilverDiagram
  );
}
