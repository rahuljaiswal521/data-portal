"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  Plus,
  Trash2,
  RefreshCw,
  ChevronRight,
  Database,
  AlertTriangle,
  Check,
  Layers,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type {
  BronzeTableInfo,
  DomainSuggestion,
  EnterpriseModelResponse,
  EntitySuggestion,
} from "@/types/silver";

// ── Domain colour palette ──────────────────────────────────────────────

const DOMAIN_COLOURS: Record<string, string> = {
  customer: "border-blue-400/40 bg-blue-50/30",
  policy: "border-purple-400/40 bg-purple-50/30",
  finance: "border-green-400/40 bg-green-50/30",
  payment: "border-green-400/40 bg-green-50/30",
  interaction: "border-orange-400/40 bg-orange-50/30",
  claim: "border-red-400/40 bg-red-50/30",
  product: "border-yellow-400/40 bg-yellow-50/30",
};

function domainClass(domain: string): string {
  return DOMAIN_COLOURS[domain.toLowerCase()] ?? "border-border bg-bg-secondary/20";
}

// ── SCD badge ─────────────────────────────────────────────────────────

function ScdBadge({ scd }: { scd: string }) {
  const isAppend = scd === "append";
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide ${
        isAppend
          ? "bg-blue-100 text-blue-700"
          : "bg-amber-100 text-amber-700"
      }`}
    >
      {isAppend ? "Append" : "SCD2"}
    </span>
  );
}

// ── Entity card ───────────────────────────────────────────────────────

function EntityCard({
  entity,
  onConfigure,
}: {
  entity: EntitySuggestion;
  onConfigure: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="p-3 rounded-[var(--radius-md)] border border-border bg-bg-card space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-text-primary font-mono">
            {entity.name}
          </span>
          <ScdBadge scd={entity.scd_type} />
          {entity.entity_type === "temporal_join" && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide bg-indigo-100 text-indigo-700">
              temporal
            </span>
          )}
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={onConfigure}
          className="shrink-0 text-xs gap-1"
        >
          Configure &amp; Create
          <ChevronRight size={12} />
        </Button>
      </div>

      {entity.description && (
        <p className="text-xs text-text-secondary leading-relaxed">
          {entity.description}
        </p>
      )}

      <div className="flex flex-wrap gap-1.5">
        {entity.source_tables.map((t) => (
          <span
            key={t}
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-bg-secondary border border-border text-[10px] font-mono text-text-tertiary"
          >
            <Database size={9} />
            {t.split(".").pop()}
          </span>
        ))}
      </div>

      {entity.business_keys.length > 0 && (
        <p className="text-[11px] text-text-tertiary">
          <span className="font-medium text-text-secondary">Keys:</span>{" "}
          <span className="font-mono">{entity.business_keys.join(", ")}</span>
        </p>
      )}

      {entity.reasoning && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-[11px] text-accent hover:underline"
        >
          {expanded ? "Hide reasoning" : "Show reasoning"}
        </button>
      )}
      {expanded && entity.reasoning && (
        <p className="text-xs text-text-secondary leading-relaxed border-t border-border/50 pt-2">
          {entity.reasoning}
        </p>
      )}
    </div>
  );
}

// ── Domain card ───────────────────────────────────────────────────────

function DomainCard({
  domain,
  onConfigureEntity,
}: {
  domain: DomainSuggestion;
  onConfigureEntity: (entity: EntitySuggestion) => void;
}) {
  return (
    <div
      className={`rounded-[var(--radius-lg)] border p-5 space-y-4 ${domainClass(domain.domain)}`}
    >
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Layers size={15} className="text-text-secondary" />
          <span className="text-sm font-semibold text-text-primary font-mono">
            {domain.schema}
          </span>
          <span className="text-xs text-text-tertiary">
            ({domain.entities.length}{" "}
            {domain.entities.length === 1 ? "entity" : "entities"})
          </span>
        </div>
        {domain.reasoning && (
          <p className="text-xs text-text-secondary leading-relaxed">
            {domain.reasoning}
          </p>
        )}
      </div>

      <div className="space-y-3">
        {domain.entities.map((entity) => (
          <EntityCard
            key={entity.name}
            entity={entity}
            onConfigure={() => onConfigureEntity(entity)}
          />
        ))}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────

export default function ModelAdvisorPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [tables, setTables] = useState<string[]>([""]);
  const [selectedTables, setSelectedTables] = useState<Set<string>>(new Set());
  const [discovered, setDiscovered] = useState<BronzeTableInfo[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [result, setResult] = useState<EnterpriseModelResponse | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [streamingText, setStreamingText] = useState("");

  // ── Discover bronze tables ────────────────────────────────────────

  const handleDiscover = async () => {
    setDiscovering(true);
    try {
      const rows = await api.listBronzeTables("dev", "bronze");
      setDiscovered(rows);
      const allFull = new Set(rows.map((r) => r.full_name));
      setSelectedTables(allFull);
      // Sync manual input list with discovered
      setTables(rows.map((r) => r.full_name));
    } catch (err: any) {
      toast(err.message || "Failed to discover bronze tables", "error");
    } finally {
      setDiscovering(false);
    }
  };

  // ── Manual table list helpers ─────────────────────────────────────

  const updateTable = (idx: number, value: string) =>
    setTables((prev) => prev.map((t, i) => (i === idx ? value : t)));

  const addTable = () => setTables((prev) => [...prev, ""]);

  const removeTable = (idx: number) =>
    setTables((prev) => prev.filter((_, i) => i !== idx));

  // ── Checkbox toggle ───────────────────────────────────────────────

  const toggleTable = (fullName: string) => {
    setSelectedTables((prev) => {
      const next = new Set(prev);
      if (next.has(fullName)) next.delete(fullName);
      else next.add(fullName);
      return next;
    });
  };

  const toggleAll = () => {
    const allNames = discovered.length
      ? discovered.map((r) => r.full_name)
      : tables.filter((t) => t.trim());
    const allSelected = allNames.every((n) => selectedTables.has(n));
    if (allSelected) {
      setSelectedTables(new Set());
    } else {
      setSelectedTables(new Set(allNames));
    }
  };

  // ── Analyze ───────────────────────────────────────────────────────

  const handleAnalyze = async () => {
    const toAnalyze =
      discovered.length > 0
        ? [...selectedTables]
        : tables.filter((t) => t.trim());

    if (toAnalyze.length === 0) {
      toast("Select at least one table to analyze", "error");
      return;
    }

    setAnalyzing(true);
    setResult(null);
    setStreamingText("");
    try {
      const res = await api.suggestEnterpriseModelStream(
        toAnalyze,
        "dev",
        (text) => setStreamingText(text)
      );
      setResult(res);
      setStreamingText("");
      if (res.error) {
        toast(res.error, "error");
      }
    } catch (err: any) {
      toast(err.message || "Enterprise model analysis failed", "error");
    } finally {
      setAnalyzing(false);
    }
  };

  // ── Configure & Create navigation ─────────────────────────────────

  const handleConfigure = (entity: EntitySuggestion) => {
    const params = new URLSearchParams();
    if (entity.source_tables.length > 0)
      params.set("tables", entity.source_tables.join(","));
    if (entity.name)        params.set("name", entity.name);
    if (entity.description) params.set("description", entity.description);
    if (entity.domain)      params.set("domain", entity.domain);
    router.push(`/silver/new?${params.toString()}`);
  };

  // ── Computed state ────────────────────────────────────────────────

  const displayList = discovered.length > 0 ? discovered : null;
  const selectedCount =
    displayList
      ? [...selectedTables].filter((t) => discovered.some((d) => d.full_name === t)).length
      : tables.filter((t) => t.trim()).length;

  return (
    <div className="max-w-3xl mx-auto space-y-8 pb-16">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Sparkles size={20} className="text-accent" />
          <h1 className="text-xl font-semibold text-text-primary">
            Enterprise Model Advisor
          </h1>
        </div>
        <p className="text-sm text-text-secondary">
          Select your Bronze tables and let AI suggest how to organise them into
          Silver domains and entities.
        </p>
      </div>

      {/* Table selection */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-text-primary">Bronze Tables</p>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleDiscover}
              disabled={discovering}
            >
              <RefreshCw size={14} className={discovering ? "animate-spin" : ""} />
              {discovering ? "Discovering..." : "Discover Bronze Tables"}
            </Button>
            <Button variant="ghost" size="sm" onClick={addTable}>
              <Plus size={14} />
              Add Manually
            </Button>
          </div>
        </div>

        {/* Discovered list with checkboxes */}
        {displayList ? (
          <div className="rounded-[var(--radius-md)] border border-border divide-y divide-border overflow-hidden">
            <div className="flex items-center gap-3 px-4 py-2.5 bg-bg-secondary/50">
              <input
                type="checkbox"
                checked={
                  displayList.length > 0 &&
                  displayList.every((d) => selectedTables.has(d.full_name))
                }
                onChange={toggleAll}
                className="h-4 w-4 rounded border-border text-accent focus:ring-accent"
              />
              <span className="text-xs font-medium text-text-secondary uppercase tracking-wide">
                {selectedCount} / {displayList.length} selected
              </span>
            </div>
            {displayList.map((tbl) => (
              <label
                key={tbl.full_name}
                className="flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-bg-secondary/30 transition-colors"
              >
                <input
                  type="checkbox"
                  checked={selectedTables.has(tbl.full_name)}
                  onChange={() => toggleTable(tbl.full_name)}
                  className="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                />
                <Database size={13} className="text-text-tertiary shrink-0" />
                <span className="text-sm font-mono text-text-primary">
                  {tbl.full_name}
                </span>
              </label>
            ))}
          </div>
        ) : (
          /* Manual entry list */
          <div className="space-y-2">
            {tables.map((tbl, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <input
                  type="text"
                  value={tbl}
                  onChange={(e) => updateTable(idx, e.target.value)}
                  placeholder="dev.bronze.crm_customers"
                  className="flex-1 rounded-[var(--radius-md)] border border-border bg-bg-card px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-accent"
                />
                {tables.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeTable(idx)}
                    className="p-1.5 text-text-tertiary hover:text-error transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            ))}
            <p className="text-xs text-text-tertiary">
              Or click <strong>Discover Bronze Tables</strong> to auto-load from Databricks.
            </p>
          </div>
        )}
      </div>

      {/* Analyze button */}
      <div>
        <Button
          onClick={handleAnalyze}
          disabled={analyzing || selectedCount === 0}
          className="gap-2"
        >
          <Sparkles size={15} />
          {analyzing ? "Analyzing..." : `Suggest Enterprise Model (${selectedCount} tables)`}
        </Button>
      </div>

      {/* Streaming preview */}
      {analyzing && streamingText && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <RefreshCw size={13} className="animate-spin text-accent" />
            <p className="text-xs font-medium text-text-secondary uppercase tracking-wide">
              Analyzing...
            </p>
          </div>
          <pre className="text-[11px] text-text-tertiary font-mono leading-relaxed p-3 rounded-[var(--radius-md)] border border-border bg-bg-secondary/30 whitespace-pre-wrap max-h-48 overflow-y-auto">
            {streamingText}
          </pre>
        </div>
      )}

      {/* Results */}
      {result && !result.error && (
        <div className="space-y-6">
          <div className="flex items-center gap-2 border-b border-border pb-3">
            <Check size={16} className="text-green-600" />
            <p className="text-sm font-semibold text-text-primary">
              {result.domains.length}{" "}
              {result.domains.length === 1 ? "domain" : "domains"} suggested
            </p>
          </div>

          {result.overall_reasoning && (
            <div className="p-4 rounded-[var(--radius-md)] border border-accent/30 bg-accent/5 text-sm text-text-secondary leading-relaxed">
              {result.overall_reasoning}
            </div>
          )}

          {result.domains.map((domain) => (
            <DomainCard
              key={domain.domain}
              domain={domain}
              onConfigureEntity={handleConfigure}
            />
          ))}

          {result.ungrouped_tables.length > 0 && (
            <div className="p-4 rounded-[var(--radius-md)] border border-yellow-400/40 bg-yellow-50/30 space-y-2">
              <div className="flex items-center gap-2">
                <AlertTriangle size={14} className="text-yellow-600" />
                <p className="text-xs font-semibold text-yellow-800 uppercase tracking-wide">
                  Ungrouped Tables
                </p>
              </div>
              <p className="text-xs text-yellow-700">
                The following tables did not fit into a domain:
              </p>
              <ul className="space-y-0.5">
                {result.ungrouped_tables.map((t) => (
                  <li key={t} className="text-xs font-mono text-yellow-800">
                    {t}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {result?.error && (
        <div className="p-4 rounded-[var(--radius-md)] border border-error bg-error/5">
          <p className="text-sm text-error">{result.error}</p>
        </div>
      )}
    </div>
  );
}
