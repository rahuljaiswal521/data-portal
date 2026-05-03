"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { AiTcGenerator } from "@/components/testing/AiTcGenerator";
import { useLatestTestResult, useTestSuite } from "@/hooks/use-testing";
import { api } from "@/lib/api";
import type { AssertionResult, TestCase, TestCaseResult, TestStatus } from "@/types/testing";
import {
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Download,
  Loader2,
  Play,
  Square,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

// ─── helpers ────────────────────────────────────────────────────────────────

function statusCls(status: TestStatus | string): string {
  const map: Record<string, string> = {
    PASSED: "bg-green-100 text-green-700",
    FAILED: "bg-red-100 text-red-700",
    RUNNING: "bg-blue-100 text-blue-700",
    ERROR: "bg-orange-100 text-orange-700",
    SKIPPED: "bg-gray-100 text-gray-500",
    CANCELLED: "bg-yellow-100 text-yellow-700",
    NOT_RUN: "bg-gray-100 text-gray-400",
  };
  return map[status] ?? map.NOT_RUN;
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusCls(status)}`}
    >
      {status === "RUNNING" && (
        <Loader2 size={10} className="animate-spin mr-1" />
      )}
      {status}
    </span>
  );
}

// ─── assertion table (expanded row) ─────────────────────────────────────────

function AssertionTable({ assertions }: { assertions: AssertionResult[] }) {
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-text-tertiary border-b border-border">
          <th className="text-left pb-2 pr-6 font-medium">Assertion</th>
          <th className="text-left pb-2 pr-6 font-medium">Expected</th>
          <th className="text-left pb-2 pr-6 font-medium">Actual</th>
          <th className="text-left pb-2 font-medium w-8">Pass</th>
        </tr>
      </thead>
      <tbody>
        {assertions.map((a, i) => (
          <tr key={i} className={a.passed ? "" : "text-red-600"}>
            <td className="pr-6 py-1.5 text-text-secondary">{a.description}</td>
            <td className="pr-6 py-1.5 font-mono">{String(a.expected)}</td>
            <td className="pr-6 py-1.5 font-mono">
              {a.actual != null ? String(a.actual) : "—"}
            </td>
            <td className="py-1.5">
              {a.passed ? (
                <CheckCircle2 size={13} className="text-green-600" />
              ) : (
                <XCircle size={13} className="text-red-600" />
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ─── single test-case row ────────────────────────────────────────────────────

function TestCaseRow({
  tc,
  result,
  onRunSingle,
  isRunningThis,
  isSuiteRunning,
}: {
  tc: TestCase;
  result?: TestCaseResult;
  onRunSingle: (tcId: string) => void;
  isRunningThis: boolean;
  isSuiteRunning: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const effectiveResult = isRunningThis
    ? { ...result, status: "RUNNING" } as TestCaseResult
    : result;
  const status = effectiveResult?.status ?? "NOT_RUN";
  const canExpand = effectiveResult && (effectiveResult.assertions ?? []).length > 0;
  const runDisabled = isSuiteRunning || isRunningThis;

  return (
    <>
      <tr
        className={cn(
          "border-b border-border transition-colors",
          canExpand ? "cursor-pointer hover:bg-bg-secondary" : ""
        )}
        onClick={() => canExpand && setExpanded((v) => !v)}
      >
        <td className="px-4 py-3 font-mono text-xs text-text-secondary">
          {tc.id}
        </td>
        <td className="px-4 py-3 text-xs text-text-secondary capitalize">
          {tc.category.replace("_", " ")}
        </td>
        <td className="px-4 py-3 text-sm text-text-primary">{tc.name}</td>
        <td className="px-4 py-3">
          <span
            className={`text-xs font-medium ${tc.positive ? "text-green-600" : "text-orange-500"}`}
          >
            {tc.positive ? "Positive" : "Negative"}
          </span>
        </td>
        <td className="px-4 py-3">
          <StatusBadge status={status} />
        </td>
        <td className="px-4 py-3 text-xs text-text-secondary">
          {effectiveResult?.duration_seconds != null
            ? `${effectiveResult.duration_seconds}s`
            : "—"}
        </td>
        {/* Run single TC button */}
        <td
          className="px-3 py-3 w-10"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            title="Run this test case"
            disabled={runDisabled}
            onClick={() => onRunSingle(tc.id)}
            className={cn(
              "flex items-center justify-center w-7 h-7 rounded border transition-colors",
              runDisabled
                ? "opacity-40 cursor-not-allowed border-border text-text-tertiary"
                : "border-border text-text-secondary hover:border-accent hover:text-accent hover:bg-accent-light"
            )}
          >
            {isRunningThis ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <Play size={12} />
            )}
          </button>
        </td>
        <td className="px-2 py-3 w-6 text-text-tertiary">
          {canExpand &&
            (expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />)}
        </td>
      </tr>

      {expanded && effectiveResult && (effectiveResult.assertions ?? []).length > 0 && (
        <tr>
          <td colSpan={8} className="bg-bg-secondary px-6 py-4">
            <AssertionTable assertions={effectiveResult.assertions} />
            {effectiveResult.error && (
              <p className="mt-3 text-xs text-red-600 font-mono bg-red-50 px-3 py-2 rounded">
                {effectiveResult.error}
              </p>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

// tiny cn re-export to avoid importing utils in this file
function cn(...cls: (string | boolean | undefined)[]): string {
  return cls.filter(Boolean).join(" ");
}

// ─── page ────────────────────────────────────────────────────────────────────

export default function SourceTestSuitePage() {
  const params = useParams();
  const sourceName = params.source as string;
  const { toast } = useToast();
  const [starting, setStarting] = useState(false);

  const [cancelling, setCancelling] = useState(false);
  const { data: suite, isLoading: suiteLoading, mutate: mutateSuite } = useTestSuite(sourceName);
  const {
    data: latestResult,
    mutate: mutateResult,
  } = useLatestTestResult(sourceName);

  const [runningTcId, setRunningTcId] = useState<string | null>(null);

  const isRunning =
    latestResult?.overall_status === "RUNNING" || starting;

  // Build a map of tc.id → TestCaseResult for quick lookup
  const tcResults = new Map(
    (latestResult?.test_cases ?? []).map((r) => [r.id, r])
  );

  async function handleRun() {
    setStarting(true);
    try {
      await api.runTestSuite(sourceName);
      toast("Suite started — results will populate as each test case completes.", "success");
      mutateResult();
    } catch (err: any) {
      const msg = err.message || "Failed to start suite";
      toast(msg.includes("already in progress") ? "A run is already in progress — stop it first." : msg, "error");
    } finally {
      setStarting(false);
    }
  }

  async function handleCancel() {
    setCancelling(true);
    try {
      await api.cancelTestSuite(sourceName);
      toast("Suite cancellation requested — current test case will finish.", "success");
      mutateResult();
    } catch (err: any) {
      toast(err.message || "Failed to cancel suite", "error");
    } finally {
      setCancelling(false);
    }
  }

  async function handleRunSingle(tcId: string) {
    setRunningTcId(tcId);
    try {
      const tcResult = await api.runSingleTc(sourceName, tcId);
      // Optimistically update the cache, then revalidate so the persisted
      // result from the server overwrites any stale on-disk state (e.g. a
      // previous CANCELLED run that the server would return on focus).
      mutateResult((prev) => {
        if (!prev) return prev;
        const updatedTcs = prev.test_cases.some((t) => t.id === tcId)
          ? prev.test_cases.map((t) => (t.id === tcId ? tcResult : t))
          : [...prev.test_cases, tcResult];
        return { ...prev, test_cases: updatedTcs };
      });
      toast(
        tcResult.status === "PASSED"
          ? `${tcId} passed`
          : `${tcId} failed — expand row to see assertions`,
        tcResult.status === "PASSED" ? "success" : "error"
      );
    } catch (err: any) {
      toast(err.message || `Failed to run ${tcId}`, "error");
    } finally {
      setRunningTcId(null);
    }
  }

  function handleDownload() {
    if (!latestResult) return;
    const a = document.createElement("a");
    a.href = api.getTestReportUrl(sourceName);
    a.download = `${sourceName}_test_report.html`;
    a.click();
  }

  // ── Loading ────────────────────────────────────────────────────────────────
  if (suiteLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-5 w-96" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  // ── Not found ──────────────────────────────────────────────────────────────
  if (!suite) {
    return (
      <Card className="p-12 text-center">
        <p className="text-text-secondary mb-3">
          No test suite found for <code className="text-xs bg-bg-secondary px-1 rounded">{sourceName}</code>
        </p>
        <Link
          href="/testing/bronze"
          className="text-sm text-accent hover:underline"
        >
          ← Back to suites
        </Link>
      </Card>
    );
  }

  const summary = latestResult?.summary;

  return (
    <div className="space-y-6">
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <Link
            href="/testing/bronze"
            className="inline-flex items-center gap-1 text-xs text-text-secondary hover:text-text-primary mb-2"
          >
            <ArrowLeft size={12} />
            Back to suites
          </Link>
          <h1 className="text-2xl font-semibold text-text-primary">
            {sourceName}
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            {suite.test_cases.length} test cases ·{" "}
            <span className="font-mono">{suite.target_table}</span> ·{" "}
            <span className="font-mono text-xs bg-bg-secondary px-1 rounded">
              {suite.test_catalog}.{suite.test_schema}
            </span>
          </p>
        </div>

        <div className="flex items-center gap-2 mt-1">
          {latestResult && !isRunning && (
            <Button variant="secondary" size="sm" onClick={handleDownload}>
              <Download size={14} />
              Download Report
            </Button>
          )}
          {isRunning && (
            <Button
              variant="secondary"
              size="sm"
              onClick={handleCancel}
              disabled={cancelling}
            >
              {cancelling ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Square size={14} />
              )}
              {cancelling ? "Cancelling…" : "Stop"}
            </Button>
          )}
          <Button onClick={handleRun} disabled={isRunning}>
            {isRunning ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Play size={14} />
            )}
            {isRunning ? "Running…" : "Run Suite"}
          </Button>
        </div>
      </div>

      {/* ── Summary bar ───────────────────────────────────────────────────── */}
      {latestResult && (
        <Card className="p-4 flex items-center gap-6 flex-wrap">
          <StatusBadge status={latestResult.overall_status} />
          {summary && (
            <>
              <span className="flex items-center gap-1 text-sm text-green-600">
                <CheckCircle2 size={13} />
                {summary.passed} passed
              </span>
              <span className="flex items-center gap-1 text-sm text-red-600">
                <XCircle size={13} />
                {summary.failed} failed
              </span>
              <span className="flex items-center gap-1 text-sm text-text-secondary">
                <Clock size={13} />
                {summary.skipped} skipped
              </span>
              {latestResult.duration_seconds != null && (
                <span className="ml-auto text-sm text-text-secondary">
                  {latestResult.duration_seconds < 60
                    ? `${Math.round(latestResult.duration_seconds)}s`
                    : `${Math.round(latestResult.duration_seconds / 60)} min`}
                </span>
              )}
            </>
          )}
        </Card>
      )}

      {/* ── Test cases table ──────────────────────────────────────────────── */}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border text-text-tertiary text-xs">
                <th className="px-4 py-3 text-left font-medium">ID</th>
                <th className="px-4 py-3 text-left font-medium">Category</th>
                <th className="px-4 py-3 text-left font-medium">Name</th>
                <th className="px-4 py-3 text-left font-medium">Type</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Duration</th>
                <th className="px-3 py-3 w-10 text-left font-medium" title="Run individual test case">Run</th>
                <th className="px-2 py-3 w-6" />
              </tr>
            </thead>
            <tbody>
              {suite.test_cases.map((tc) => (
                <TestCaseRow
                  key={tc.id}
                  tc={tc}
                  result={tcResults.get(tc.id)}
                  onRunSingle={handleRunSingle}
                  isRunningThis={runningTcId === tc.id}
                  isSuiteRunning={isRunning}
                />
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ── AI Test Case Generator ─────────────────────────────────────────── */}
      <AiTcGenerator
        sourceName={sourceName}
        onTcAdded={() => { mutateSuite(); mutateResult(); }}
      />
    </div>
  );
}
