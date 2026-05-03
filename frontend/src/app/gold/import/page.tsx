"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Toggle } from "@/components/ui/toggle";
import { goldApi } from "@/lib/api";
import type {
  ColumnIssue,
  GoldPreviewResponse,
  ReadinessReport,
  SourceCheck,
} from "@/types/gold";

type Step = "upload" | "preview" | "readiness" | "committed";

export default function GoldImportPage() {
  const router = useRouter();

  const [step, setStep] = useState<Step>("upload");

  // Upload state
  const [file, setFile] = useState<File | null>(null);
  const [defaultName, setDefaultName] = useState("new_mart");

  // Preview state
  const [preview, setPreview] = useState<GoldPreviewResponse | null>(null);

  // Readiness state
  const [readiness, setReadiness] = useState<ReadinessReport | null>(null);
  const [aiSuggestions, setAiSuggestions] = useState(true);

  // Commit state
  const [overwrite, setOverwrite] = useState(false);
  const [committed, setCommitted] = useState<string | null>(null);

  // Shared
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onPreview = async () => {
    if (!file) return;
    setError(null);
    setPreview(null);
    setLoading(true);
    try {
      const result = await goldApi.previewIngest(file, defaultName);
      setPreview(result);
      setStep("preview");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const onCheckReadiness = async () => {
    if (!preview) return;
    setError(null);
    setReadiness(null);
    setLoading(true);
    try {
      const result = await goldApi.checkReadiness(preview.ir, aiSuggestions);
      setReadiness(result);
      setStep("readiness");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const onCommit = async () => {
    if (!preview) return;
    setError(null);
    setLoading(true);
    try {
      const result = await goldApi.commitIngest(preview.ir, overwrite);
      setCommitted(result.mart_name);
      setStep("committed");
      setTimeout(() => router.push("/gold"), 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const onReset = () => {
    setFile(null);
    setPreview(null);
    setReadiness(null);
    setError(null);
    setCommitted(null);
    setStep("upload");
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-semibold">Import Business Rules</h1>
        <p className="text-text-secondary mt-1">
          Upload an <code>.xlsx</code> workbook (sheets: <code>mart</code>,{" "}
          <code>dimensions</code>, <code>facts</code>, <code>metrics</code>) or
          a <code>.json</code> file matching the gold IR shape. The portal will
          parse it, then verify every source it references is in your bronze +
          silver layers before letting you commit.
        </p>
      </div>

      <StepIndicator current={step} />

      {error && (
        <Card className="p-4 border-red-300 bg-red-50 text-red-900">
          <strong>Error:</strong> {error}
        </Card>
      )}

      {/* Step 1: Upload */}
      {step === "upload" && (
        <Card className="p-6 space-y-4">
          <h2 className="text-lg font-semibold">1. Upload workbook or JSON</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm mb-1">
                File (.xlsx or .json)
              </label>
              <Input
                type="file"
                accept=".xlsx,.xlsm,.json"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>
            <div>
              <label className="block text-sm mb-1">
                Default mart name (used if absent in the file)
              </label>
              <Input
                value={defaultName}
                onChange={(e) => setDefaultName(e.target.value)}
                placeholder="sales"
              />
            </div>
          </div>
          <div>
            <Button onClick={onPreview} disabled={!file || loading}>
              {loading ? "Parsing…" : "Parse & preview"}
            </Button>
          </div>
        </Card>
      )}

      {/* Step 2: Preview */}
      {step === "preview" && preview && (
        <Card className="p-6 space-y-4">
          <h2 className="text-lg font-semibold">2. Review parsed mart</h2>

          <div className="grid grid-cols-3 gap-3 text-sm">
            <SummaryStat label="Dimensions" value={preview.summary.n_dimensions} />
            <SummaryStat label="Facts" value={preview.summary.n_facts} />
            <SummaryStat label="Metrics" value={preview.summary.n_metrics} />
          </div>

          <div className="border rounded p-4 bg-bg-secondary">
            <h3 className="font-medium mb-2">Mart</h3>
            <p className="text-sm">
              <code>{preview.ir.mart.name}</code>
              {preview.ir.mart.description ? ` — ${preview.ir.mart.description}` : ""}
            </p>
            <p className="text-xs text-text-secondary">
              Schema: {preview.ir.mart.schema} · Common: {preview.ir.mart.common_schema} · Owner: {preview.ir.mart.owner || "—"}
            </p>
          </div>

          {preview.warnings.length > 0 && (
            <div className="border rounded p-4 border-amber-300 bg-amber-50">
              <h3 className="font-medium mb-2">Parser warnings</h3>
              <ul className="list-disc pl-5 text-sm space-y-1">
                {preview.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          <DimList items={preview.ir.dimensions} />
          <FactList items={preview.ir.facts} />
          <MetricList items={preview.ir.metrics} />

          <div className="border-t pt-4 flex items-center gap-3">
            <Toggle
              checked={aiSuggestions}
              onChange={(v) => setAiSuggestions(v)}
              label="Use AI to suggest fixes for missing columns"
            />
          </div>

          <div className="flex gap-2">
            <Button onClick={onCheckReadiness} disabled={loading}>
              {loading ? "Checking…" : "Check bronze + silver readiness"}
            </Button>
            <Button variant="secondary" onClick={onReset}>
              Start over
            </Button>
          </div>
        </Card>
      )}

      {/* Step 3: Readiness */}
      {step === "readiness" && readiness && (
        <Card className="p-6 space-y-4">
          <h2 className="text-lg font-semibold">3. Readiness check</h2>

          <ReadinessVerdict report={readiness} />
          <ReadinessSummary report={readiness} />

          <SourceList sources={readiness.sources} />

          {readiness.column_issues.length > 0 && (
            <ColumnIssueList issues={readiness.column_issues} />
          )}

          <div className="border-t pt-4 space-y-3">
            <Toggle
              checked={overwrite}
              onChange={(v) => setOverwrite(v)}
              label="Overwrite if mart already exists"
            />
            <div className="flex gap-2">
              <Button
                onClick={onCommit}
                disabled={loading || !readiness.ready}
                title={
                  readiness.ready
                    ? "Commit gold mart YAMLs"
                    : "Resolve readiness errors before committing"
                }
              >
                {loading
                  ? "Committing…"
                  : readiness.ready
                  ? "Commit to disk"
                  : "Cannot commit (errors above)"}
              </Button>
              <Button variant="secondary" onClick={() => setStep("preview")}>
                Back
              </Button>
              <Button variant="secondary" onClick={onReset}>
                Start over
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Step 4: Committed */}
      {step === "committed" && committed && (
        <Card className="p-4 border-green-300 bg-green-50 text-green-900">
          ✅ Mart <strong>{committed}</strong> committed. Redirecting…
        </Card>
      )}
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────

function StepIndicator({ current }: { current: Step }) {
  const steps: { key: Step; label: string }[] = [
    { key: "upload", label: "Upload" },
    { key: "preview", label: "Preview" },
    { key: "readiness", label: "Readiness" },
    { key: "committed", label: "Done" },
  ];
  const idx = steps.findIndex((s) => s.key === current);
  return (
    <div className="flex gap-2 text-sm">
      {steps.map((s, i) => {
        const active = i === idx;
        const done = i < idx;
        return (
          <div
            key={s.key}
            className={[
              "px-3 py-1 rounded-full border",
              active
                ? "bg-accent-light text-accent border-accent"
                : done
                ? "bg-green-50 text-green-800 border-green-300"
                : "bg-bg-secondary text-text-tertiary border-border",
            ].join(" ")}
          >
            {i + 1}. {s.label}
          </div>
        );
      })}
    </div>
  );
}

function SummaryStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="border rounded p-3">
      <p className="text-xs text-text-secondary">{label}</p>
      <p className="text-2xl font-semibold">{value}</p>
    </div>
  );
}

function ReadinessVerdict({ report }: { report: ReadinessReport }) {
  if (report.ready) {
    return (
      <div className="border rounded p-4 border-green-300 bg-green-50">
        <p className="font-medium text-green-900">
          ✅ Ready to build — all referenced bronze + silver sources are in place.
        </p>
        {!report.databricks_available && (
          <p className="text-xs text-green-800 mt-1">
            (YAML-only check — Databricks not configured, so column-level
            verification was skipped.)
          </p>
        )}
      </div>
    );
  }
  return (
    <div className="border rounded p-4 border-red-300 bg-red-50">
      <p className="font-medium text-red-900">
        ⛔ Not ready — {report.errors.length} blocking{" "}
        {report.errors.length === 1 ? "issue" : "issues"} below.
      </p>
    </div>
  );
}

function ReadinessSummary({ report }: { report: ReadinessReport }) {
  const s = report.summary;
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
      <SummaryStat label="Sources total" value={s.sources_total} />
      <SummaryStat label="Sources OK" value={s.sources_ok} />
      <SummaryStat
        label="Missing in bronze"
        value={s.sources_missing_bronze}
      />
      <SummaryStat
        label="Missing in silver"
        value={s.sources_missing_silver}
      />
      <SummaryStat label="Column issues" value={s.column_issues} />
    </div>
  );
}

function SourceList({ sources }: { sources: SourceCheck[] }) {
  return (
    <div className="border rounded p-4">
      <h3 className="font-medium mb-2">Sources ({sources.length})</h3>
      <div className="space-y-2">
        {sources.map((s) => (
          <div key={s.full_name} className="text-sm border-b last:border-b-0 pb-2 last:pb-0">
            <div className="flex items-center gap-2">
              <code className="font-mono">{s.full_name}</code>
              <LayerBadge layer={s.classified_layer} />
              {s.error ? (
                <span className="text-xs text-red-700">⛔ blocked</span>
              ) : s.warning ? (
                <span className="text-xs text-amber-700">⚠ warning</span>
              ) : (
                <span className="text-xs text-green-700">✓ ok</span>
              )}
            </div>
            <p className="text-xs text-text-secondary">
              YAML: {s.yaml_present ? "found" : "missing"} · Reachable:{" "}
              {s.table_reachable === null
                ? "n/a"
                : s.table_reachable
                ? "yes"
                : "no"}{" "}
              · Used by: {s.referenced_by.join(", ")}
            </p>
            {s.error && <p className="text-xs text-red-700 mt-1">{s.error}</p>}
            {s.warning && (
              <p className="text-xs text-amber-700 mt-1">{s.warning}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function LayerBadge({ layer }: { layer: SourceCheck["classified_layer"] }) {
  const cls =
    layer === "bronze"
      ? "bg-amber-100 text-amber-800"
      : layer === "silver"
      ? "bg-zinc-200 text-zinc-700"
      : "bg-bg-secondary text-text-tertiary";
  return (
    <span className={`text-[10px] uppercase px-1.5 rounded ${cls}`}>
      {layer}
    </span>
  );
}

function ColumnIssueList({ issues }: { issues: ColumnIssue[] }) {
  return (
    <div className="border rounded p-4 border-red-200 bg-red-50/40">
      <h3 className="font-medium mb-2">
        Column issues ({issues.length})
      </h3>
      <div className="space-y-3">
        {issues.map((c, i) => (
          <div key={i} className="text-sm">
            <p>
              <code className="font-mono">{c.referenced_by}</code> wants column{" "}
              <code className="bg-white px-1 rounded">{c.missing_column}</code>{" "}
              from <code>{c.source_full_name}</code>
            </p>
            {c.suggestions && c.suggestions.length > 0 && (
              <p className="text-xs mt-1">
                <strong>AI suggestions:</strong>{" "}
                {c.suggestions.map((s) => (
                  <code key={s} className="bg-white px-1 rounded mr-1">
                    {s}
                  </code>
                ))}
              </p>
            )}
            <details className="text-xs mt-1">
              <summary className="cursor-pointer text-text-secondary">
                Show available columns ({c.available_columns.length})
              </summary>
              <p className="font-mono break-all mt-1">
                {c.available_columns.join(", ")}
              </p>
            </details>
          </div>
        ))}
      </div>
    </div>
  );
}

function DimList({
  items,
}: {
  items: GoldPreviewResponse["ir"]["dimensions"];
}) {
  if (items.length === 0) return null;
  return (
    <div className="border rounded p-4">
      <h3 className="font-medium mb-2">Dimensions ({items.length})</h3>
      <div className="space-y-3">
        {items.map((d) => (
          <div key={d.name} className="text-sm">
            <p className="font-mono">{d.name}</p>
            <p className="text-xs text-text-secondary">
              {d.is_conformed ? "conformed" : "local"} · {d.scd_type} ·
              source: {d.source_entity} · BK: [{d.business_key.join(", ")}] ·
              {d.attributes.length} attrs
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function FactList({
  items,
}: {
  items: GoldPreviewResponse["ir"]["facts"];
}) {
  if (items.length === 0) return null;
  return (
    <div className="border rounded p-4">
      <h3 className="font-medium mb-2">Facts ({items.length})</h3>
      <div className="space-y-3">
        {items.map((f) => (
          <div key={f.name} className="text-sm">
            <p className="font-mono">{f.name}</p>
            <p className="text-xs text-text-secondary">
              {f.load_type} · grain: [{f.grain.join(", ")}] · {f.measures.length}{" "}
              measures · {f.foreign_keys.length} FKs
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function MetricList({
  items,
}: {
  items: GoldPreviewResponse["ir"]["metrics"];
}) {
  if (items.length === 0) return null;
  return (
    <div className="border rounded p-4">
      <h3 className="font-medium mb-2">Metrics ({items.length})</h3>
      <ul className="space-y-2 text-sm">
        {items.map((m) => (
          <li key={m.name}>
            <code>{m.name}</code> · {m.materialization} · <code>{m.formula}</code>
          </li>
        ))}
      </ul>
    </div>
  );
}
