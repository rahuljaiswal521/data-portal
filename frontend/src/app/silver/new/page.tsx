"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Toggle } from "@/components/ui/toggle";
import { useToast } from "@/components/ui/toast";
import { FormWizard } from "@/components/forms/form-wizard";
import { DynamicList } from "@/components/forms/dynamic-list";
import { KeyValueField } from "@/components/forms/key-value-field";
import { YamlPreview } from "@/components/forms/yaml-preview";
import { api } from "@/lib/api";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useEffect, Suspense } from "react";
import { Plus, Trash2, Sparkles, Search, Check, AlertTriangle, Info } from "lucide-react";
import type { TableProfileResponse, SuggestModelResponse } from "@/types/silver";

// ── Types ──────────────────────────────────────────────────────────────

interface SilverColumnMapping {
  source: string;
  target: string;
  transform: string;
  default_value: string;
}

interface SilverSourceForm {
  bronze_table: string;
  priority: number;
  filter_condition: string;
  watermark: { column: string; type: string; default_value: string };
  columns: SilverColumnMapping[];
  temporal: { start_column: string; end_column: string; end_inclusive: boolean } | null;
}

interface SilverFormData {
  name: string;
  domain: string;
  description: string;
  enabled: boolean;
  entity_type: "standard" | "temporal_join";
  tags: Record<string, string>;
  sources: SilverSourceForm[];
  target: {
    catalog: string;
    schema_name: string;
    table: string;
    scd_type: string;
    business_keys: string[];
    partition_by: string[];
    exclude_columns_from_hash: string[];
  };
  schedule: { cron_expression: string; timezone: string } | null;
}

interface ModelingTable {
  full_table_name: string;
  column_definitions: string;
  hasDefinitions: boolean;
}

// ── Defaults ───────────────────────────────────────────────────────────

const defaultSource: SilverSourceForm = {
  bronze_table: "",
  priority: 1,
  filter_condition: "",
  watermark: { column: "", type: "timestamp", default_value: "" },
  columns: [{ source: "", target: "", transform: "", default_value: "" }],
  temporal: null,
};

const defaultForm: SilverFormData = {
  name: "",
  domain: "customer",
  description: "",
  enabled: true,
  entity_type: "standard",
  tags: {},
  sources: [{ ...defaultSource, columns: [{ source: "", target: "", transform: "", default_value: "" }] }],
  target: {
    catalog: "${catalog}",
    schema_name: "slv_customer",
    table: "",
    scd_type: "scd2",
    business_keys: [""],
    partition_by: [],
    exclude_columns_from_hash: [],
  },
  schedule: null,
};

const DOMAINS = [
  { value: "customer", label: "Customer" },
  { value: "policy", label: "Policy" },
  { value: "payment", label: "Payment" },
  { value: "interaction", label: "Interaction" },
];

const ENTITY_TYPES = [
  { value: "standard", label: "Standard" },
  { value: "temporal_join", label: "Temporal Join" },
];

const SCD_TYPES = [
  { value: "scd2", label: "SCD Type 2" },
  { value: "append", label: "Append Only" },
];

const WATERMARK_TYPES = [
  { value: "timestamp", label: "Timestamp" },
  { value: "integer", label: "Integer" },
  { value: "date", label: "Date" },
];

// ── Component ──────────────────────────────────────────────────────────

function NewSilverEntityPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const [form, setForm] = useState<SilverFormData>(defaultForm);
  const [submitting, setSubmitting] = useState(false);
  const [yamlPreview, setYamlPreview] = useState<string>("");
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [customDomain, setCustomDomain] = useState(false);

  // ── AI Modeling state ─────────────────────────────────────────────
  const [modelingTables, setModelingTables] = useState<ModelingTable[]>([
    { full_table_name: "", column_definitions: "", hasDefinitions: false },
  ]);
  const [tableProfiles, setTableProfiles] = useState<Record<string, TableProfileResponse>>({});
  const [suggestedModel, setSuggestedModel] = useState<SuggestModelResponse | null>(null);
  const [suggesting, setSuggesting] = useState(false);
  const [profilingTable, setProfilingTable] = useState<string | null>(null);
  const [modelApplied, setModelApplied] = useState(false);

  // ── Pre-fill from URL params (e.g. from Model Advisor) ────────────
  useEffect(() => {
    const tablesParam      = searchParams.get("tables");
    const nameParam        = searchParams.get("name");
    const domainParam      = searchParams.get("domain");
    const descriptionParam = searchParams.get("description");

    if (tablesParam) {
      const tableList = tablesParam
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean)
        .map((t) => ({ full_table_name: t, column_definitions: "", hasDefinitions: false }));
      if (tableList.length > 0) setModelingTables(tableList);
    }

    setForm((prev) => {
      let updated = { ...prev };
      if (nameParam) {
        updated = { ...updated, name: nameParam, target: { ...updated.target, table: nameParam } };
      }
      if (domainParam) {
        updated = {
          ...updated,
          domain: domainParam,
          target: { ...updated.target, schema_name: `slv_${domainParam}` },
        };
      }
      if (descriptionParam) {
        updated = { ...updated, description: descriptionParam };
      }
      return updated;
    });
  }, [searchParams]);

  // ── Update helpers ─────────────────────────────────────────────────

  const update = <K extends keyof SilverFormData>(
    key: K,
    value: SilverFormData[K]
  ) => setForm((prev) => ({ ...prev, [key]: value }));

  const updateTarget = (field: string, value: any) =>
    setForm((prev) => ({
      ...prev,
      target: { ...prev.target, [field]: value },
    }));

  const updateDomain = (domain: string) => {
    setForm((prev) => ({
      ...prev,
      domain,
      target: { ...prev.target, schema_name: `slv_${domain}` },
    }));
  };

  const updateName = (name: string) => {
    setForm((prev) => ({
      ...prev,
      name,
      target: { ...prev.target, table: name },
    }));
  };

  // ── Source helpers ─────────────────────────────────────────────────

  const updateSource = (idx: number, field: string, value: any) =>
    setForm((prev) => ({
      ...prev,
      sources: prev.sources.map((s, i) =>
        i === idx ? { ...s, [field]: value } : s
      ),
    }));

  const addSource = () =>
    setForm((prev) => ({
      ...prev,
      sources: [
        ...prev.sources,
        {
          ...defaultSource,
          priority: prev.sources.length + 1,
          columns: [{ source: "", target: "", transform: "", default_value: "" }],
          temporal: prev.entity_type === "temporal_join"
            ? { start_column: "", end_column: "", end_inclusive: false }
            : null,
        },
      ],
    }));

  const removeSource = (idx: number) =>
    setForm((prev) => ({
      ...prev,
      sources: prev.sources.filter((_, i) => i !== idx),
    }));

  // ── Column mapping helpers ────────────────────────────────────────

  const addColumn = (srcIdx: number) =>
    setForm((prev) => ({
      ...prev,
      sources: prev.sources.map((s, i) =>
        i === srcIdx
          ? { ...s, columns: [...s.columns, { source: "", target: "", transform: "", default_value: "" }] }
          : s
      ),
    }));

  const removeColumn = (srcIdx: number, colIdx: number) =>
    setForm((prev) => ({
      ...prev,
      sources: prev.sources.map((s, i) =>
        i === srcIdx
          ? { ...s, columns: s.columns.filter((_, ci) => ci !== colIdx) }
          : s
      ),
    }));

  const updateColumn = (srcIdx: number, colIdx: number, field: string, value: string) =>
    setForm((prev) => ({
      ...prev,
      sources: prev.sources.map((s, i) =>
        i === srcIdx
          ? {
              ...s,
              columns: s.columns.map((c, ci) =>
                ci === colIdx ? { ...c, [field]: value } : c
              ),
            }
          : s
      ),
    }));

  const updateSourceTemporal = (srcIdx: number, field: string, value: any) =>
    setForm((prev) => ({
      ...prev,
      sources: prev.sources.map((s, i) =>
        i === srcIdx && s.temporal
          ? { ...s, temporal: { ...s.temporal, [field]: value } }
          : s
      ),
    }));

  const updateSourceWatermark = (srcIdx: number, field: string, value: any) =>
    setForm((prev) => ({
      ...prev,
      sources: prev.sources.map((s, i) =>
        i === srcIdx
          ? { ...s, watermark: { ...s.watermark, [field]: value } }
          : s
      ),
    }));

  // ── Entity type change — toggle temporal on all sources ───────────

  const handleEntityTypeChange = (entityType: "standard" | "temporal_join") => {
    setForm((prev) => ({
      ...prev,
      entity_type: entityType,
      sources: prev.sources.map((s) => ({
        ...s,
        temporal:
          entityType === "temporal_join"
            ? s.temporal || { start_column: "", end_column: "", end_inclusive: false }
            : null,
      })),
    }));
  };

  // ── AI Modeling helpers ────────────────────────────────────────────

  const updateModelingTable = (idx: number, field: keyof ModelingTable, value: any) =>
    setModelingTables((prev) =>
      prev.map((t, i) => (i === idx ? { ...t, [field]: value } : t))
    );

  const addModelingTable = () =>
    setModelingTables((prev) => [
      ...prev,
      { full_table_name: "", column_definitions: "", hasDefinitions: false },
    ]);

  const removeModelingTable = (idx: number) => {
    setModelingTables((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleProfileTable = async (tableName: string) => {
    const parts = tableName.split(".");
    if (parts.length !== 3) {
      toast("Enter a 3-part name: catalog.schema.table", "error");
      return;
    }
    setProfilingTable(tableName);
    try {
      const res = await api.profileBronzeTable({
        catalog: parts[0],
        schema: parts[1],
        table: parts[2],
      });
      setTableProfiles((prev) => ({ ...prev, [tableName]: res }));
      if (res.error) {
        toast(res.error, "error");
      }
    } catch (err: any) {
      toast(err.message || "Failed to profile table", "error");
    } finally {
      setProfilingTable(null);
    }
  };

  const handleSuggestModel = async () => {
    const validTables = modelingTables.filter((t) => t.full_table_name.trim());
    if (validTables.length === 0) {
      toast("Add at least one Bronze table to analyze", "error");
      return;
    }
    setSuggesting(true);
    setSuggestedModel(null);
    try {
      const res = await api.suggestSilverModel({
        tables: validTables.map((t) => ({
          full_table_name: t.full_table_name.trim(),
          column_definitions: t.hasDefinitions && t.column_definitions.trim()
            ? t.column_definitions.trim()
            : null,
        })),
        domain_hint: form.domain || null,
        entity_name_hint: form.name || null,
      });
      setSuggestedModel(res);
      if (res.error) {
        toast(res.error, "error");
      } else {
        // Auto-apply immediately so Sources step is pre-filled when user clicks Continue
        applyModelToForm(res, true);
        toast("AI model generated and applied to Sources. Click Continue to review.", "success");
      }
    } catch (err: any) {
      toast(err.message || "AI modeling failed", "error");
    } finally {
      setSuggesting(false);
    }
  };

  // Accept model directly so it can be called immediately after setSuggestedModel
  // (React state updates are async — reading suggestedModel right after setting it won't work)
  const applyModelToForm = (model: SuggestModelResponse, silent = false) => {
    if (!model || model.error) return;

    setForm((prev) => {
      const updated = { ...prev };

      if (model.name) {
        updated.name = model.name;
        updated.target = { ...updated.target, table: model.name };
      }
      if (model.domain) {
        updated.domain = model.domain;
        updated.target = { ...updated.target, schema_name: `slv_${model.domain}` };
      }
      if (model.description) updated.description = model.description;
      if (model.entity_type) {
        updated.entity_type = model.entity_type as "standard" | "temporal_join";
      }

      if (model.sources.length > 0) {
        updated.sources = model.sources.map((s) => ({
          bronze_table: s.bronze_table,
          priority: s.priority,
          filter_condition: s.filter_condition || "",
          watermark: s.watermark
            ? {
                column: s.watermark.column || "",
                type: s.watermark.type || "timestamp",
                default_value: s.watermark.default_value || "",
              }
            : { column: "", type: "timestamp", default_value: "" },
          columns: s.columns.map((c) => ({
            source: c.source,
            target: c.target,
            transform: c.transform || "",
            default_value: c.default_value || "",
          })),
          temporal: s.temporal
            ? {
                start_column: s.temporal.start_column || "",
                end_column: s.temporal.end_column || "",
                end_inclusive: s.temporal.end_inclusive ?? false,
              }
            : null,
        }));
      }

      if (model.target) {
        const t = model.target;
        updated.target = {
          ...updated.target,
          catalog: t.catalog || updated.target.catalog,
          schema_name: t.schema_name || updated.target.schema_name,
          table: t.table || updated.target.table,
          scd_type: t.scd_type || updated.target.scd_type,
          business_keys: t.business_keys.length > 0 ? t.business_keys : updated.target.business_keys,
          partition_by: t.partition_by || [],
          exclude_columns_from_hash: t.exclude_columns_from_hash || [],
        };
      }

      return updated;
    });

    setModelApplied(true);
    if (!silent) {
      toast("AI model re-applied to form.", "success");
    }
  };

  // ── Preview & Submit ──────────────────────────────────────────────

  const handlePreview = async () => {
    setValidationErrors([]);
    try {
      const res = await api.validateSilverEntity(form.name || "preview", form);
      if (res.valid && res.yaml_preview) {
        setYamlPreview(res.yaml_preview);
      } else {
        setValidationErrors(res.errors || ["Validation failed"]);
        setYamlPreview("");
      }
    } catch {
      setYamlPreview(JSON.stringify(form, null, 2));
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await api.createSilverEntity(form);
      toast(`Entity '${form.name}' created successfully`, "success");
      router.push("/silver");
    } catch (err: any) {
      toast(err.message || "Failed to create entity", "error");
    } finally {
      setSubmitting(false);
    }
  };

  // ── Steps ─────────────────────────────────────────────────────────

  const steps = [
    // ─── Step 1: General ──────────────────────────────────────────
    {
      id: "general",
      title: "General",
      description: "Name, domain, and basic settings",
      content: (
        <div className="space-y-5">
          <Input
            label="Entity Name"
            value={form.name}
            onChange={(e) => updateName(e.target.value)}
            placeholder="e.g., customer_profile"
            hint="Lowercase with underscores. Used as table name and YAML filename."
          />
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">
              Domain
            </label>
            {customDomain ? (
              <div className="flex gap-2">
                <input
                  type="text"
                  value={form.domain}
                  onChange={(e) => updateDomain(e.target.value)}
                  placeholder="custom_domain"
                  className="flex-1 rounded-[var(--radius-md)] border border-border bg-bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setCustomDomain(false);
                    updateDomain("customer");
                  }}
                >
                  Use preset
                </Button>
              </div>
            ) : (
              <div className="flex gap-2 items-end">
                <div className="flex-1">
                  <Select
                    value={form.domain}
                    onChange={(e) => updateDomain(e.target.value)}
                    options={DOMAINS}
                  />
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setCustomDomain(true)}
                >
                  Custom
                </Button>
              </div>
            )}
            <p className="text-xs text-text-tertiary mt-1">
              Target schema: <span className="font-mono">slv_{form.domain}</span>
            </p>
          </div>
          <Input
            label="Description"
            value={form.description}
            onChange={(e) => update("description", e.target.value)}
            placeholder="Brief description of this Silver entity"
          />
          <Select
            label="Entity Type"
            value={form.entity_type}
            onChange={(e) =>
              handleEntityTypeChange(e.target.value as "standard" | "temporal_join")
            }
            options={ENTITY_TYPES}
          />
          <Toggle
            label="Enabled"
            checked={form.enabled}
            onChange={(v) => update("enabled", v)}
          />
          <KeyValueField
            label="Tags"
            value={form.tags}
            onChange={(v) => update("tags", v)}
          />
        </div>
      ),
    },

    // ─── Step 2: AI Model ─────────────────────────────────────────
    {
      id: "model",
      title: "Model",
      description: "AI-assisted entity modeling (optional)",
      content: (
        <div className="space-y-6">
          {/* Info banner */}
          <div className="flex gap-3 p-4 rounded-[var(--radius-md)] border border-accent/30 bg-accent/5">
            <Info size={18} className="text-accent mt-0.5 shrink-0" />
            <div className="text-sm text-text-secondary">
              <p className="font-medium text-text-primary mb-1">Optional: AI-Assisted Modeling</p>
              <p>
                Add Bronze tables below, optionally provide column definitions, then let AI
                suggest a Silver entity model with column mappings, transforms, and business keys.
                You can skip this step and configure everything manually.
              </p>
            </div>
          </div>

          {/* Bronze table cards */}
          {modelingTables.map((mt, idx) => (
            <div
              key={idx}
              className="p-4 rounded-[var(--radius-md)] border border-border bg-bg-secondary/30 space-y-4"
            >
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-text-primary">
                  Bronze Table {idx + 1}
                </p>
                {modelingTables.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeModelingTable(idx)}
                    className="p-1.5 text-text-tertiary hover:text-error transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>

              <div className="flex gap-3">
                <div className="flex-1">
                  <Input
                    label="Table Name"
                    value={mt.full_table_name}
                    onChange={(e) =>
                      updateModelingTable(idx, "full_table_name", e.target.value)
                    }
                    placeholder="dev.bronze.crm_customers"
                    hint="Three-part name: catalog.schema.table"
                  />
                </div>
                <div className="flex items-end">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleProfileTable(mt.full_table_name)}
                    disabled={!mt.full_table_name.trim() || profilingTable === mt.full_table_name}
                  >
                    <Search size={14} />
                    {profilingTable === mt.full_table_name ? "Profiling..." : "Profile"}
                  </Button>
                </div>
              </div>

              {/* Profile results inline */}
              {tableProfiles[mt.full_table_name] && !tableProfiles[mt.full_table_name].error && (
                <div className="p-3 rounded-[var(--radius-md)] border border-border bg-bg-card space-y-3">
                  <div className="flex items-center gap-2">
                    <Check size={14} className="text-green-600" />
                    <span className="text-xs font-medium text-text-secondary uppercase tracking-wider">
                      Profile: {tableProfiles[mt.full_table_name].row_count.toLocaleString()} rows
                      {tableProfiles[mt.full_table_name].has_scd2_columns && " (SCD2)"}
                    </span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-text-tertiary uppercase">
                          <th className="text-left pb-1.5 pr-3">Column</th>
                          <th className="text-left pb-1.5 pr-3">Type</th>
                          <th className="text-right pb-1.5 pr-3">Distinct</th>
                          <th className="text-right pb-1.5">Nulls</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tableProfiles[mt.full_table_name].columns
                          .filter((c) => !c.name.startsWith("_"))
                          .map((col) => {
                            const stats = tableProfiles[mt.full_table_name].profiling.find(
                              (p) => p.column === col.name
                            );
                            return (
                              <tr key={col.name} className="border-t border-border/50">
                                <td className="py-1.5 pr-3 font-mono">{col.name}</td>
                                <td className="py-1.5 pr-3 text-text-tertiary">{col.type}</td>
                                <td className="py-1.5 pr-3 text-right">
                                  {stats?.distinct_count?.toLocaleString() ?? "-"}
                                </td>
                                <td className="py-1.5 text-right">
                                  {stats?.null_count?.toLocaleString() ?? "-"}
                                </td>
                              </tr>
                            );
                          })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Column definitions toggle */}
              <div className="space-y-2">
                <Toggle
                  label="I have column definitions"
                  checked={mt.hasDefinitions}
                  onChange={(v) => updateModelingTable(idx, "hasDefinitions", v)}
                />
                {mt.hasDefinitions && (
                  <textarea
                    value={mt.column_definitions}
                    onChange={(e) =>
                      updateModelingTable(idx, "column_definitions", e.target.value)
                    }
                    placeholder="Paste column definitions, data dictionary entries, or descriptions here..."
                    rows={4}
                    className="w-full rounded-[var(--radius-md)] border border-border bg-bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent resize-y"
                  />
                )}
              </div>
            </div>
          ))}

          <div className="flex gap-3">
            <Button type="button" variant="secondary" onClick={addModelingTable}>
              <Plus size={14} /> Add Table
            </Button>
          </div>

          {/* Generate button */}
          <div className="pt-2">
            <Button
              onClick={handleSuggestModel}
              disabled={suggesting || modelingTables.every((t) => !t.full_table_name.trim())}
            >
              <Sparkles size={14} />
              {suggesting ? "Generating Model..." : "Generate Model with AI"}
            </Button>
          </div>

          {/* Suggested model display */}
          {suggestedModel && !suggestedModel.error && (
            <div className="space-y-4 p-4 rounded-[var(--radius-md)] border border-accent/40 bg-accent/5">
              <div className="flex items-center gap-2">
                <Sparkles size={16} className="text-accent" />
                <p className="text-sm font-semibold text-text-primary">AI-Suggested Model</p>
              </div>

              {/* Reasoning */}
              {suggestedModel.reasoning && (
                <div className="text-sm text-text-secondary leading-relaxed">
                  {suggestedModel.reasoning}
                </div>
              )}

              {/* Warnings */}
              {suggestedModel.warnings.length > 0 && (
                <div className="p-3 rounded-[var(--radius-md)] border border-yellow-500/30 bg-yellow-50/50 space-y-1">
                  {suggestedModel.warnings.map((w, i) => (
                    <div key={i} className="flex gap-2 text-sm text-yellow-800">
                      <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Summary grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-2 rounded bg-bg-card border border-border">
                  <p className="text-[10px] text-text-tertiary uppercase tracking-wider">Domain</p>
                  <p className="text-sm font-medium">{suggestedModel.domain || "-"}</p>
                </div>
                <div className="p-2 rounded bg-bg-card border border-border">
                  <p className="text-[10px] text-text-tertiary uppercase tracking-wider">SCD Type</p>
                  <p className="text-sm font-medium">{suggestedModel.target?.scd_type || "-"}</p>
                </div>
                <div className="p-2 rounded bg-bg-card border border-border">
                  <p className="text-[10px] text-text-tertiary uppercase tracking-wider">Entity Type</p>
                  <p className="text-sm font-medium">{suggestedModel.entity_type}</p>
                </div>
                <div className="p-2 rounded bg-bg-card border border-border">
                  <p className="text-[10px] text-text-tertiary uppercase tracking-wider">Business Keys</p>
                  <p className="text-sm font-medium font-mono">
                    {suggestedModel.target?.business_keys?.join(", ") || "-"}
                  </p>
                </div>
              </div>

              {/* Per-source column mapping tables */}
              {suggestedModel.sources.map((src, srcIdx) => (
                <div key={srcIdx} className="space-y-2">
                  <p className="text-xs font-medium text-text-secondary uppercase tracking-wider">
                    Source: <span className="font-mono">{src.bronze_table}</span>
                    {src.priority > 1 && ` (priority ${src.priority})`}
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-text-tertiary uppercase">
                          <th className="text-left pb-1.5 pr-2">Source</th>
                          <th className="text-left pb-1.5 pr-2">Target</th>
                          <th className="text-left pb-1.5 pr-2">Transform</th>
                          <th className="text-left pb-1.5">Reasoning</th>
                        </tr>
                      </thead>
                      <tbody>
                        {src.columns.map((col, colIdx) => (
                          <tr key={colIdx} className="border-t border-border/50">
                            <td className="py-1.5 pr-2 font-mono">{col.source}</td>
                            <td className="py-1.5 pr-2 font-mono">{col.target}</td>
                            <td className="py-1.5 pr-2 font-mono text-text-tertiary">
                              {col.transform || "-"}
                            </td>
                            <td className="py-1.5 text-text-tertiary italic">
                              {col.reasoning || "-"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}

              {/* Apply button */}
              <div className="pt-2 flex items-center gap-3">
                {modelApplied && (
                  <div className="flex items-center gap-1.5 text-xs text-green-700">
                    <Check size={12} />
                    Auto-applied to Sources &amp; Target — click Continue to review
                  </div>
                )}
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => applyModelToForm(suggestedModel!)}
                >
                  <Check size={14} />
                  Re-apply to Form
                </Button>
              </div>
            </div>
          )}

          {/* Error display */}
          {suggestedModel?.error && (
            <div className="p-4 rounded-[var(--radius-md)] border border-error bg-error/5">
              <p className="text-sm text-error">{suggestedModel.error}</p>
            </div>
          )}
        </div>
      ),
    },

    // ─── Step 3: Sources ──────────────────────────────────────────
    {
      id: "sources",
      title: "Sources",
      description: "Bronze source tables and column mappings",
      content: (
        <div className="space-y-6">
          {form.sources.map((source, srcIdx) => (
            <div
              key={srcIdx}
              className="p-4 rounded-[var(--radius-md)] border border-border bg-bg-secondary/30 space-y-4"
            >
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-text-primary">
                  Source {srcIdx + 1}
                </p>
                {form.sources.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeSource(srcIdx)}
                    className="p-1.5 text-text-tertiary hover:text-error transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="Bronze Table"
                  value={source.bronze_table}
                  onChange={(e) =>
                    updateSource(srcIdx, "bronze_table", e.target.value)
                  }
                  placeholder="${catalog}.bronze.policy_packages"
                />
                <Input
                  label="Priority"
                  type="number"
                  value={source.priority}
                  onChange={(e) =>
                    updateSource(srcIdx, "priority", parseInt(e.target.value) || 1)
                  }
                />
              </div>

              <Input
                label="Filter Condition (optional)"
                value={source.filter_condition}
                onChange={(e) =>
                  updateSource(srcIdx, "filter_condition", e.target.value)
                }
                placeholder="e.g., status != 'DELETED'"
              />

              {/* Watermark */}
              <div className="p-3 rounded-[var(--radius-md)] border border-border bg-bg-card space-y-3">
                <p className="text-xs font-medium text-text-secondary uppercase tracking-wider">
                  Watermark (optional)
                </p>
                <div className="grid grid-cols-3 gap-3">
                  <Input
                    label="Column"
                    value={source.watermark.column}
                    onChange={(e) =>
                      updateSourceWatermark(srcIdx, "column", e.target.value)
                    }
                    placeholder="updated_at"
                  />
                  <Select
                    label="Type"
                    value={source.watermark.type}
                    onChange={(e) =>
                      updateSourceWatermark(srcIdx, "type", e.target.value)
                    }
                    options={WATERMARK_TYPES}
                  />
                  <Input
                    label="Default Value"
                    value={source.watermark.default_value}
                    onChange={(e) =>
                      updateSourceWatermark(srcIdx, "default_value", e.target.value)
                    }
                    placeholder="2020-01-01T00:00:00"
                  />
                </div>
              </div>

              {/* Column Mappings */}
              <div className="space-y-2">
                <label className="block text-sm font-medium text-text-primary">
                  Column Mappings
                </label>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-xs text-text-tertiary uppercase">
                        <th className="text-left pb-2 pr-2">Source</th>
                        <th className="text-left pb-2 pr-2">Target</th>
                        <th className="text-left pb-2 pr-2">Transform</th>
                        <th className="text-left pb-2 pr-2">Default</th>
                        <th className="pb-2 w-8" />
                      </tr>
                    </thead>
                    <tbody>
                      {source.columns.map((col, colIdx) => (
                        <tr key={colIdx}>
                          <td className="pr-2 pb-2">
                            <input
                              type="text"
                              value={col.source}
                              onChange={(e) =>
                                updateColumn(srcIdx, colIdx, "source", e.target.value)
                              }
                              placeholder="src_col"
                              className="w-full rounded-[var(--radius-md)] border border-border bg-bg-card px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                            />
                          </td>
                          <td className="pr-2 pb-2">
                            <input
                              type="text"
                              value={col.target}
                              onChange={(e) =>
                                updateColumn(srcIdx, colIdx, "target", e.target.value)
                              }
                              placeholder="tgt_col"
                              className="w-full rounded-[var(--radius-md)] border border-border bg-bg-card px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                            />
                          </td>
                          <td className="pr-2 pb-2">
                            <input
                              type="text"
                              value={col.transform}
                              onChange={(e) =>
                                updateColumn(srcIdx, colIdx, "transform", e.target.value)
                              }
                              placeholder="optional"
                              className="w-full rounded-[var(--radius-md)] border border-border bg-bg-card px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                            />
                          </td>
                          <td className="pr-2 pb-2">
                            <input
                              type="text"
                              value={col.default_value}
                              onChange={(e) =>
                                updateColumn(srcIdx, colIdx, "default_value", e.target.value)
                              }
                              placeholder="optional"
                              className="w-full rounded-[var(--radius-md)] border border-border bg-bg-card px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                            />
                          </td>
                          <td className="pb-2">
                            {source.columns.length > 1 && (
                              <button
                                type="button"
                                onClick={() => removeColumn(srcIdx, colIdx)}
                                className="p-1 text-text-tertiary hover:text-error transition-colors"
                              >
                                <Trash2 size={12} />
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => addColumn(srcIdx)}
                >
                  <Plus size={14} /> Add Column
                </Button>
              </div>

              {/* Temporal config — only for temporal_join entities */}
              {form.entity_type === "temporal_join" && source.temporal && (
                <div className="p-3 rounded-[var(--radius-md)] border border-border bg-bg-card space-y-3">
                  <p className="text-xs font-medium text-text-secondary uppercase tracking-wider">
                    Temporal Configuration
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    <Input
                      label="Start Column"
                      value={source.temporal.start_column}
                      onChange={(e) =>
                        updateSourceTemporal(srcIdx, "start_column", e.target.value)
                      }
                      placeholder="effective_from"
                    />
                    <Input
                      label="End Column"
                      value={source.temporal.end_column}
                      onChange={(e) =>
                        updateSourceTemporal(srcIdx, "end_column", e.target.value)
                      }
                      placeholder="effective_to"
                    />
                  </div>
                  <Toggle
                    label="End Inclusive"
                    checked={source.temporal.end_inclusive}
                    onChange={(v) =>
                      updateSourceTemporal(srcIdx, "end_inclusive", v)
                    }
                  />
                </div>
              )}
            </div>
          ))}

          <Button type="button" variant="secondary" onClick={addSource}>
            <Plus size={14} /> Add Source
          </Button>
        </div>
      ),
    },

    // ─── Step 4: Target ───────────────────────────────────────────
    {
      id: "target",
      title: "Target",
      description: "Silver Delta table settings",
      content: (
        <div className="space-y-5">
          <div className="grid grid-cols-3 gap-4">
            <Input
              label="Catalog"
              value={form.target.catalog}
              onChange={(e) => updateTarget("catalog", e.target.value)}
              placeholder="${catalog}"
            />
            <Input
              label="Schema"
              value={form.target.schema_name}
              onChange={(e) => updateTarget("schema_name", e.target.value)}
              hint="Auto-filled from domain"
            />
            <Input
              label="Table"
              value={form.target.table}
              onChange={(e) => updateTarget("table", e.target.value)}
              hint="Auto-filled from entity name"
            />
          </div>
          <Select
            label="SCD Type"
            value={form.target.scd_type}
            onChange={(e) => updateTarget("scd_type", e.target.value)}
            options={SCD_TYPES}
          />
          <DynamicList
            label="Business Keys"
            value={form.target.business_keys}
            onChange={(v) => updateTarget("business_keys", v)}
            placeholder="e.g., customer_id"
          />
          <DynamicList
            label="Partition By"
            value={form.target.partition_by}
            onChange={(v) => updateTarget("partition_by", v)}
            placeholder="Column name"
          />
          <DynamicList
            label="Exclude Columns from Hash"
            value={form.target.exclude_columns_from_hash}
            onChange={(v) => updateTarget("exclude_columns_from_hash", v)}
            placeholder="Column name"
          />
        </div>
      ),
    },

    // ─── Step 5: Review & Schedule ────────────────────────────────
    {
      id: "review",
      title: "Review",
      description: "Schedule and YAML preview",
      content: (
        <div className="space-y-6">
          <div className="p-4 rounded-[var(--radius-md)] border border-border bg-bg-secondary/30 space-y-4">
            <p className="text-sm font-medium text-text-primary">
              Schedule (optional)
            </p>
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Cron Expression"
                value={form.schedule?.cron_expression || ""}
                onChange={(e) =>
                  update(
                    "schedule",
                    e.target.value
                      ? {
                          cron_expression: e.target.value,
                          timezone: form.schedule?.timezone || "UTC",
                        }
                      : null
                  )
                }
                placeholder="0 0 6 * * ? (6 AM daily)"
                hint="Leave empty for manual-only execution"
              />
              <Input
                label="Timezone"
                value={form.schedule?.timezone || ""}
                onChange={(e) =>
                  form.schedule &&
                  update("schedule", {
                    ...form.schedule,
                    timezone: e.target.value,
                  })
                }
                placeholder="UTC"
                disabled={!form.schedule}
              />
            </div>
          </div>

          <Button variant="secondary" onClick={handlePreview}>
            Preview YAML
          </Button>

          {validationErrors.length > 0 && (
            <div className="p-4 rounded-[var(--radius-md)] border border-error bg-error/5 space-y-1">
              <p className="text-sm font-medium text-error">Validation Errors</p>
              {validationErrors.map((err, i) => (
                <p key={i} className="text-sm text-error">
                  {err}
                </p>
              ))}
            </div>
          )}

          {yamlPreview && <YamlPreview yaml={yamlPreview} />}
        </div>
      ),
    },
  ];

  return (
    <FormWizard
      steps={steps}
      onSubmit={handleSubmit}
      submitting={submitting}
      submitLabel="Create Entity"
    />
  );
}

export default function NewSilverEntityPage() {
  return (
    <Suspense fallback={null}>
      <NewSilverEntityPageInner />
    </Suspense>
  );
}
