"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Toggle } from "@/components/ui/toggle";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { DynamicList } from "@/components/forms/dynamic-list";
import { KeyValueField } from "@/components/forms/key-value-field";
import { MetadataColumnsField } from "@/components/forms/metadata-columns-field";
import { TypeBadge } from "@/components/sources/status-badge";
import { useSource } from "@/hooks/use-sources";
import { api } from "@/lib/api";
import { CDC_MODES, SCHEMA_EVOLUTION_MODES } from "@/lib/constants";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function EditSourcePage() {
  const params = useParams();
  const name = params.name as string;
  const router = useRouter();
  const { toast } = useToast();
  const { data: source, isLoading } = useSource(name);
  const [form, setForm] = useState<any>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (source) {
      setForm({
        description: source.description,
        enabled: source.enabled,
        tags: source.tags,
        connection: source.connection,
        extract: source.extract,
        target: source.target,
        schedule: source.schedule,
      });
    }
  }, [source]);

  const updateNested = (path: string, value: any) => {
    setForm((prev: any) => {
      if (!prev) return prev;
      const next = JSON.parse(JSON.stringify(prev));
      const keys = path.split(".");
      let obj = next;
      for (let i = 0; i < keys.length - 1; i++) {
        if (!obj[keys[i]]) obj[keys[i]] = {};
        obj = obj[keys[i]];
      }
      obj[keys[keys.length - 1]] = value;
      return next;
    });
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await api.updateSource(name, form);
      toast(`Source '${name}' updated successfully`, "success");
      router.push(`/bronze/${name}`);
    } catch (err: any) {
      toast(err.message || "Failed to update source", "error");
    } finally {
      setSubmitting(false);
    }
  };

  if (isLoading || !form) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-6">
      <Link
        href={`/bronze/${name}`}
        className="inline-flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
      >
        <ArrowLeft size={14} /> Back to {name}
      </Link>

      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold text-text-primary">
          Edit: {name}
        </h1>
        <TypeBadge type={source!.source_type} />
      </div>

      <div className="rounded-[var(--radius-lg)] border border-border bg-bg-card p-6 space-y-6">
        {/* General */}
        <section className="space-y-4">
          <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">General</h3>
          <Input
            label="Description"
            value={form.description}
            onChange={(e) => updateNested("description", e.target.value)}
          />
          <Toggle
            label="Enabled"
            checked={form.enabled}
            onChange={(v) => updateNested("enabled", v)}
          />
          <KeyValueField
            label="Tags"
            value={form.tags}
            onChange={(v) => updateNested("tags", v)}
          />
        </section>

        {/* Target */}
        <section className="space-y-4 pt-6 border-t border-border">
          <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">Target</h3>
          <div className="grid grid-cols-3 gap-4">
            <Input
              label="Catalog"
              value={form.target?.catalog || ""}
              onChange={(e) => updateNested("target.catalog", e.target.value)}
            />
            <Input
              label="Schema"
              value={form.target?.schema || "bronze"}
              onChange={(e) => updateNested("target.schema", e.target.value)}
            />
            <Input
              label="Table"
              value={form.target?.table || ""}
              onChange={(e) => updateNested("target.table", e.target.value)}
            />
          </div>
          <DynamicList
            label="Partition By"
            value={form.target?.partition_by || []}
            onChange={(v) => updateNested("target.partition_by", v)}
          />
          <KeyValueField
            label="Table Properties"
            value={form.target?.table_properties || {}}
            onChange={(v) => updateNested("target.table_properties", v)}
          />
        </section>

        {/* CDC */}
        <section className="space-y-4 pt-6 border-t border-border">
          <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">CDC</h3>
          <Toggle
            label="Enable CDC"
            checked={form.target?.cdc?.enabled || false}
            onChange={(v) => updateNested("target.cdc.enabled", v)}
          />
          {form.target?.cdc?.enabled && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-text-primary mb-2">
                  CDC Mode
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {CDC_MODES.map((m) => (
                    <button
                      key={m.value}
                      type="button"
                      onClick={() => updateNested("target.cdc.mode", m.value)}
                      className={`p-3 rounded-[var(--radius-md)] border text-left transition-all ${
                        form.target?.cdc?.mode === m.value
                          ? "border-accent bg-accent-light"
                          : "border-border hover:border-border-hover"
                      }`}
                    >
                      <p className="text-sm font-medium">{m.label}</p>
                      <p className="text-xs text-text-tertiary mt-0.5">{m.description}</p>
                    </button>
                  ))}
                </div>
              </div>
              <DynamicList
                label="Primary Keys"
                value={form.target?.cdc?.primary_keys || []}
                onChange={(v) => updateNested("target.cdc.primary_keys", v)}
              />
              <Input
                label="Sequence Column"
                value={form.target?.cdc?.sequence_column || ""}
                onChange={(e) => updateNested("target.cdc.sequence_column", e.target.value || undefined)}
              />
            </div>
          )}
        </section>

        {/* Schema Evolution */}
        <section className="space-y-4 pt-6 border-t border-border">
          <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">Schema Evolution</h3>
          <div className="grid grid-cols-3 gap-3">
            {SCHEMA_EVOLUTION_MODES.map((m) => (
              <button
                key={m.value}
                type="button"
                onClick={() => updateNested("target.schema_evolution.mode", m.value)}
                className={`p-3 rounded-[var(--radius-md)] border text-left transition-all ${
                  form.target?.schema_evolution?.mode === m.value
                    ? "border-accent bg-accent-light"
                    : "border-border hover:border-border-hover"
                }`}
              >
                <p className="text-sm font-medium">{m.label}</p>
                <p className="text-xs text-text-tertiary mt-0.5">{m.description}</p>
              </button>
            ))}
          </div>
        </section>

        {/* Quality */}
        <section className="space-y-4 pt-6 border-t border-border">
          <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">Quality</h3>
          <Toggle
            label="Enable Quality Checks"
            checked={form.target?.quality?.enabled ?? true}
            onChange={(v) => updateNested("target.quality.enabled", v)}
          />
          {form.target?.quality?.enabled && (
            <Input
              label="Quarantine Threshold (%)"
              type="number"
              value={form.target?.quality?.quarantine_threshold_pct ?? 10}
              onChange={(e) => updateNested("target.quality.quarantine_threshold_pct", parseFloat(e.target.value) || 10)}
            />
          )}
        </section>

        {/* Metadata Columns */}
        <section className="space-y-4 pt-6 border-t border-border">
          <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">Metadata Columns</h3>
          <MetadataColumnsField
            value={form.target?.metadata_columns || []}
            onChange={(v) => updateNested("target.metadata_columns", v)}
          />
        </section>

        {/* Schedule */}
        <section className="space-y-4 pt-6 border-t border-border">
          <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">Schedule</h3>
          <Input
            label="Cron Expression (Quartz)"
            value={form.schedule?.cron_expression || ""}
            onChange={(e) =>
              updateNested("schedule", {
                cron_expression: e.target.value || undefined,
                timezone: form.schedule?.timezone || "UTC",
                pause_status: "UNPAUSED",
              })
            }
            placeholder="0 0 6 * * ?"
          />
        </section>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-6 border-t border-border">
          <Link href={`/bronze/${name}`}>
            <Button variant="secondary">Cancel</Button>
          </Link>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </div>
    </div>
  );
}
