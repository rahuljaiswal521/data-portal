"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useTestSuites } from "@/hooks/use-testing";
import { cn } from "@/lib/utils";
import { CheckCircle2, Clock, FlaskConical, Play, XCircle } from "lucide-react";
import Link from "next/link";
import type { TestStatus } from "@/types/testing";

const layerTabs = [
  { label: "Bronze", href: "/testing/bronze", active: true },
  { label: "Silver", href: "/testing/silver", disabled: true },
];

function StatusBadge({ status }: { status: TestStatus | null }) {
  if (!status) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-bg-secondary text-text-tertiary">
        <Clock size={10} />
        Not Run
      </span>
    );
  }
  const map: Record<string, string> = {
    PASSED: "bg-green-100 text-green-700",
    FAILED: "bg-red-100 text-red-700",
    RUNNING: "bg-blue-100 text-blue-700",
    ERROR: "bg-orange-100 text-orange-700",
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${map[status] || "bg-bg-secondary text-text-tertiary"}`}
    >
      {status}
    </span>
  );
}

export default function BronzeTestingPage() {
  const { data: suitesData, isLoading } = useTestSuites();
  const suites = suitesData?.suites ?? [];

  const totalSuites = suites.length;
  const passing = suites.filter((s) => s.last_run_status === "PASSED").length;
  const failing = suites.filter((s) => s.last_run_status === "FAILED").length;
  const notRun = suites.filter((s) => !s.last_run_status).length;

  const stats = [
    { label: "Total Suites", value: totalSuites, icon: FlaskConical, color: "text-text-secondary" },
    { label: "Passing", value: passing, icon: CheckCircle2, color: "text-green-600" },
    { label: "Failing", value: failing, icon: XCircle, color: "text-error" },
    { label: "Not Run", value: notRun, icon: Clock, color: "text-text-tertiary" },
  ];

  return (
    <div className="space-y-8">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary">Test Suite</h1>
          <p className="text-sm text-text-secondary mt-1">
            Validate your data pipeline loads across layers
          </p>
        </div>
        <Button disabled className="opacity-50 cursor-not-allowed">
          <Play size={16} />
          Run All
        </Button>
      </div>

      {/* Layer tab strip */}
      <div className="flex gap-1 border-b border-border">
        {layerTabs.map((tab) =>
          tab.disabled ? (
            <span
              key={tab.label}
              className="px-4 py-2 text-sm font-medium text-text-tertiary cursor-not-allowed select-none"
            >
              {tab.label}
              <span className="ml-2 text-[10px] uppercase tracking-wide text-text-tertiary/60">
                coming soon
              </span>
            </span>
          ) : (
            <Link
              key={tab.label}
              href={tab.href}
              className={cn(
                "px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
                tab.active
                  ? "border-accent text-accent"
                  : "border-transparent text-text-secondary hover:text-text-primary"
              )}
            >
              {tab.label}
            </Link>
          )
        )}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4">
        {stats.map((stat) => (
          <Card key={stat.label} className="p-5">
            <div className="flex items-center gap-3">
              <stat.icon size={20} className={stat.color} />
              <div>
                {isLoading ? (
                  <Skeleton className="h-7 w-8 mb-1" />
                ) : (
                  <p className="text-2xl font-semibold text-text-primary">{stat.value}</p>
                )}
                <p className="text-xs text-text-secondary mt-0.5">{stat.label}</p>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Suite table or empty state */}
      {isLoading ? (
        <Card className="p-6 space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </Card>
      ) : suites.length === 0 ? (
        <Card className="flex flex-col items-center justify-center py-20 text-center">
          <div className="flex items-center justify-center w-14 h-14 rounded-full bg-bg-secondary mb-4">
            <FlaskConical size={28} className="text-text-tertiary" />
          </div>
          <h2 className="text-lg font-medium text-text-primary mb-2">
            No test suites configured yet
          </h2>
          <p className="text-sm text-text-secondary max-w-sm">
            Test suites are auto-generated when you create a Bronze source. Define
            expected row counts, schema checks, and data quality rules to get started.
          </p>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border text-text-tertiary text-xs">
                  <th className="px-4 py-3 text-left font-medium">Source</th>
                  <th className="px-4 py-3 text-left font-medium">Type</th>
                  <th className="px-4 py-3 text-left font-medium">Target Table</th>
                  <th className="px-4 py-3 text-left font-medium">Primary Keys</th>
                  <th className="px-4 py-3 text-left font-medium">Test Cases</th>
                  <th className="px-4 py-3 text-left font-medium">Last Run</th>
                  <th className="px-4 py-3 text-left font-medium">Status</th>
                  <th className="px-4 py-3 w-20" />
                </tr>
              </thead>
              <tbody>
                {suites.map((suite) => (
                  <tr
                    key={suite.source_name}
                    className="border-b border-border last:border-0 hover:bg-bg-secondary transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-sm text-text-primary">
                      {suite.source_name}
                    </td>
                    <td className="px-4 py-3 text-xs text-text-secondary capitalize">
                      {suite.source_type}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-text-secondary">
                      {suite.target_table}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-text-secondary">
                      {suite.primary_keys.join(", ")}
                    </td>
                    <td className="px-4 py-3 text-sm text-text-secondary">
                      {suite.test_count}
                    </td>
                    <td className="px-4 py-3 text-xs text-text-secondary">
                      {suite.last_run_at
                        ? new Date(suite.last_run_at).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={suite.last_run_status} />
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/testing/bronze/${suite.source_name}`}
                        className="text-xs text-accent hover:underline"
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
