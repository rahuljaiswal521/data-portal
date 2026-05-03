import useSWR from "swr";
import { api } from "@/lib/api";
import type {
  TestRunListResponse,
  TestRunResult,
  TestSuite,
  TestSuiteListResponse,
} from "@/types/testing";

export function useTestSuites() {
  return useSWR<TestSuiteListResponse>("/testing/suites", () =>
    api.listTestSuites()
  );
}

export function useTestSuite(sourceName: string | null) {
  return useSWR<TestSuite>(
    sourceName ? `/testing/suites/${sourceName}` : null,
    () => api.getTestSuite(sourceName!)
  );
}

export function useLatestTestResult(sourceName: string | null) {
  return useSWR<TestRunResult>(
    sourceName ? `/testing/suites/${sourceName}/results/latest` : null,
    () => api.getLatestTestResult(sourceName!),
    {
      // Poll every 5 s while a run is active; stop when complete
      refreshInterval: (data) =>
        data?.overall_status === "RUNNING" ? 5000 : 0,
    }
  );
}

export function useTestResults(sourceName: string | null) {
  return useSWR<TestRunListResponse>(
    sourceName ? `/testing/suites/${sourceName}/results` : null,
    () => api.getTestResults(sourceName!)
  );
}
