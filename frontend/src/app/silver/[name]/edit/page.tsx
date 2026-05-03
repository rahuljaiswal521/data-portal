"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Toggle } from "@/components/ui/toggle";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { DynamicList } from "@/components/forms/dynamic-list";
import { KeyValueField } from "@/components/forms/key-value-field";
import { useSilverEntity } from "@/hooks/use-silver";
import { api } from "@/lib/api";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

// ── Types ───────────────────────────────────────────────────────────────

interface ColumnMapping {
  source: string;
  target: string;
  transform: string;
  default_value: string;
}

interface SourceForm {
  bronze_table: string;
  priority: number;
  filter_condition: string;
  watermark: { column: string; type: string; default_value: string };
  columns: ColumnMapping[];
  temporal: { start_column: string; end_column: string; end_inclusive: boolean } | null;
}

interface EditForm {
  description: string;
  enabled: boolean;
  tags: Record<string, string>;
  sources: SourceForm[];
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

// ── Constants ───────────────────────────────────────────────────────────

const SCD_TYPES = [
  { value: "scd2", label: "SCD Type 2" },
  { value: "append", label: "Append Only" },
];

const WATERMARK_TYPES = [
  { value: "timestamp", label: "Timestamp" },
  { value: "integer", label: "Integer" },
  { value: "date", label: "Date" },
];

// ── Helpers ─────────────────────────────────────────────────────────────

function entityToForm(entity: any): EditForm {
  return {
    description: entity.description ?? "",
    enabled: entity.enabled ?? true,
    tags: entity.tags ?? {},
    sources: (entity.sources ?? []).map((s: any) => ({
      bronze_table: s.bronze_table ?? "",
      priority: s.priority ?? 1,
      filter_condition: s.filter_condition ?? "",
      watermark: {
        column: s.watermark?.column ?? "",
        type: s.watermark?.type ?? "timestamp",
        default_value: s.watermark?.default_value ?? "",
      },
      columns: (s.columns ?? []).map((c: any) => ({
        source: c.source ?? "",
        target: c.target ?? "",
        transform: c.transform ?? "",
        default_value: c.default_value ?? "",
      })),
      temporal: s.temporal
        ? {
            start_column: s.temporal.start_column ?? "",
            end_column: s.temporal.end_column ?? "",
            end_inclusive: s.temporal.end_inclusive ?? false,
          }
        : null,
    })),
    target: {
      catalog: entity.target?.catalog ?? "${catalog}",
      schema_name: entity.target?.schema ?? entity.target?.schema_name ?? "",
      table: entity.target?.table ?? "",
      scd_type: entity.target?.scd_type ?? "scd2",
      business_keys: entity.target?.business_keys ?? [],
      partition_by: entity.target?.partition_by ?? [],
      exclude_columns_from_hash: entity.target?.exclude_columns_from_hash ?? [],
    },
    schedule: entity.schedule
      ? {
          cron_expression: entity.schedule.cron_expression ?? "",
          timezone: entity.schedule.timezone ?? "UTC",
        }
      : null,
  };
}

const defaultColumn: ColumnMapping = { source: "", target: "", transform: "", default_value: "" };

// ── Page ────────────────────────────────────────────────────────────────

export default function EditSilverEntityPage() {
  const params = useParams();
  const name = params.name as string;
  const router = useRouter();
  const { toast } = useToast();
  const { data: entity, isLoading } = useSilverEntity(name);
  const [form, setForm] = useState<EditForm | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (entity) setForm(entityToForm(entity));
  }, [entity]);

  // ── Generic update helpers ──────────────────────────────────────────

  const update = <K extends keyof EditForm>(key: K, value: EditForm[K]) =>
    setForm((prev) => prev ? { ...prev, [key]: value } : prev);

  const updateTarget = (field: string, value: any) =>
    setForm((prev) =>
      prev ? { ...prev, target: { ...prev.target, [field]: value } } : prev
    );

  // ── Source helpers ──────────────────────────────────────────────────

  const updateSource = (idx: number, field: string, value: any) =>
    setForm((prev) =>
      prev
        ? {
            ...prev,
            sources: prev.sources.map((s, i) =>
              i === idx ? { ...s, [field]: value } : s
            ),
          }
        : prev
    );

  const updateSourceWatermark = (idx: number, field: string, value: any) =>
    setForm((prev) =>
      prev
        ? {
            ...prev,
            sources: prev.sources.map((s, i) =>
              i === idx ? { ...s, watermark: { ...s.watermark, [field]: value } } : s
            ),
          }
        : prev
    );

  const addSource = () =>
    setForm((prev) =>
      prev
        ? {
            ...prev,
            sources: [
              ...prev.sources,
              {
                bronze_table: "",
                priority: prev.sources.length + 1,
                filter_condition: "",
                watermark: { column: "", type: "timestamp", default_value: "" },
                columns: [{ ...defaultColumn }],
                temporal: null,
              },
            ],
          }
        : prev
    );

  const removeSource = (idx: number) =>
    setForm((prev) =>
      prev ? { ...prev, sources: prev.sources.filter((_, i) => i !== idx) } : prev
    );

  // ── Column helpers ──────────────────────────────────────────────────

  const addColumn = (srcIdx: number) =>
    setForm((prev) =>
      prev
        ? {
            ...prev,
            sources: prev.sources.map((s, i) =>
              i === srcIdx
                ? { ...s, columns: [...s.columns, { ...defaultColumn }] }
                : s
            ),
          }
        : prev
    );

  const removeColumn = (srcIdx: number, colIdx: number) =>
    setForm((prev) =>
      prev
        ? {
            ...prev,
            sources: prev.sources.map((s, i) =>
              i === srcIdx
                ? { ...s, columns: s.columns.filter((_, ci) => ci !== colIdx) }
                : s
            ),
          }
        : prev
    );

  const updateColumn = (srcIdx: number, colIdx: number, field: string, value: string) =>
    setForm((prev) =>
      prev
        ? {
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
          }
        : prev
    );

  // ── Submit ──────────────────────────────────────────────────────────

  const handleSubmit = async () => {
    if (!form) return;
    setSubmitting(true);
    try {
      await api.updateSilverEntity(name, form);
      toast("Entity updated successfully", "success");
      router.push(`/silver/${name}`);
    } catch (err: any) {
      toast(err.message || "Update failed", "error");
    } finally {
      setSubmitting(false);
    }
  };

  // ── Loading / not found ─────────────────────────────────────────────

  if (isLoading || !form) {
    return (
      <div className="max-w-3xl mx-auto space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (!entity) {
    return (
      <div className="text-center py-20">
        <p className="text-text-secondary">Entity &apos;{name}&apos; not found</p>
        <Link href="/silver">
          <Button variant="secondary" className="mt-4">
            <ArrowLeft size={16} /> Back
          </Button>
        </Link>
      </div>
    );
  }

  // ── Render ──────────────────────────────────────────────────────────

  return (
    <div className="max-w-3xl mx-auto space-y-8 pb-16">
      {/* Header */}
      <div>
        <Link
          href={`/silver/${name}`}
          className="inline-flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors mb-4"
        >
          <ArrowLeft size={14} /> Back to {name}
        </Link>
        <h1 className="text-xl font-semibold text-text-primary">
          Edit <span className="font-mono">{name}</span>
        </h1>
        <p className="text-sm text-text-tertiary mt-1">
          Domain: <span className="font-mono">slv_{entity.domain}</span>
          &nbsp;&middot;&nbsp;Name and domain cannot be changed after creation.
        </p>
      </div>

      {/* ── General ────────────────────────────────────────────────── */}
      <section className="space-y-5">
        <h2 className="text-sm font-semibold text-text-primary uppercase tracking-wider border-b border-border pb-2">
          General
        </h2>
        <Input
          label="Description"
          value={form.description}
          onChange={(e) => update("description", e.target.value)}
          placeholder="Brief description of this Silver entity"
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
      </section>

      {/* ── Sources ────────────────────────────────────────────────── */}
      <section className="space-y-5">
        <h2 className="text-sm font-semibold text-text-primary uppercase tracking-wider border-b border-border pb-2">
          Sources
        </h2>

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
                onChange={(e) => updateSource(srcIdx, "bronze_table", e.target.value)}
                placeholder="${catalog}.bronze.table_name"
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
              onChange={(e) => updateSource(srcIdx, "filter_condition", e.target.value)}
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
                  onChange={(e) => updateSourceWatermark(srcIdx, "column", e.target.value)}
                  placeholder="updated_at"
                />
                <Select
                  label="Type"
                  value={source.watermark.type}
                  onChange={(e) => updateSourceWatermark(srcIdx, "type", e.target.value)}
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
                        {(["source", "target", "transform", "default_value"] as const).map(
                          (field) => (
                            <td key={field} className="pr-2 pb-2">
                              <input
                                type="text"
                                value={col[field]}
                                onChange={(e) =>
                                  updateColumn(srcIdx, colIdx, field, e.target.value)
                                }
                                placeholder={
                                  field === "source"
                                    ? "src_col"
                                    : field === "target"
                                    ? "tgt_col"
                                    : "optional"
                                }
                                className="w-full rounded-[var(--radius-md)] border border-border bg-bg-card px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                              />
                            </td>
                          )
                        )}
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

            {/* Temporal config */}
            {source.temporal && (
              <div className="p-3 rounded-[var(--radius-md)] border border-border bg-bg-card space-y-3">
                <p className="text-xs font-medium text-text-secondary uppercase tracking-wider">
                  Temporal Configuration
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    label="Start Column"
                    value={source.temporal.start_column}
                    onChange={(e) =>
                      updateSource(srcIdx, "temporal", {
                        ...source.temporal!,
                        start_column: e.target.value,
                      })
                    }
                  />
                  <Input
                    label="End Column"
                    value={source.temporal.end_column}
                    onChange={(e) =>
                      updateSource(srcIdx, "temporal", {
                        ...source.temporal!,
                        end_column: e.target.value,
                      })
                    }
                  />
                </div>
                <Toggle
                  label="End Inclusive"
                  checked={source.temporal.end_inclusive}
                  onChange={(v) =>
                    updateSource(srcIdx, "temporal", {
                      ...source.temporal!,
                      end_inclusive: v,
                    })
                  }
                />
              </div>
            )}
          </div>
        ))}

        <Button type="button" variant="secondary" onClick={addSource}>
          <Plus size={14} /> Add Source
        </Button>
      </section>

      {/* ── Target ─────────────────────────────────────────────────── */}
      <section className="space-y-5">
        <h2 className="text-sm font-semibold text-text-primary uppercase tracking-wider border-b border-border pb-2">
          Target
        </h2>
        <div className="grid grid-cols-3 gap-4">
          <Input
            label="Catalog"
            value={form.target.catalog}
            onChange={(e) => updateTarget("catalog", e.target.value)}
          />
          <Input
            label="Schema"
            value={form.target.schema_name}
            onChange={(e) => updateTarget("schema_name", e.target.value)}
          />
          <Input
            label="Table"
            value={form.target.table}
            onChange={(e) => updateTarget("table", e.target.value)}
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
      </section>

      {/* ── Schedule ───────────────────────────────────────────────── */}
      <section className="space-y-5">
        <h2 className="text-sm font-semibold text-text-primary uppercase tracking-wider border-b border-border pb-2">
          Schedule (optional)
        </h2>
        <div className="grid grid-cols-2 gap-4">
          <Input
            label="Cron Expression"
            value={form.schedule?.cron_expression ?? ""}
            onChange={(e) =>
              update(
                "schedule",
                e.target.value
                  ? { cron_expression: e.target.value, timezone: form.schedule?.timezone ?? "UTC" }
                  : null
              )
            }
            placeholder="0 0 6 * * ? (6 AM daily)"
            hint="Leave empty to clear the schedule"
          />
          <Input
            label="Timezone"
            value={form.schedule?.timezone ?? ""}
            onChange={(e) =>
              form.schedule &&
              update("schedule", { ...form.schedule, timezone: e.target.value })
            }
            placeholder="UTC"
            disabled={!form.schedule}
          />
        </div>
      </section>

      {/* ── Actions ────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 pt-2 border-t border-border">
        <Button onClick={handleSubmit} disabled={submitting}>
          {submitting ? "Saving..." : "Save Changes"}
        </Button>
        <Link href={`/silver/${name}`}>
          <Button variant="secondary">Cancel</Button>
        </Link>
      </div>
    </div>
  );
}
