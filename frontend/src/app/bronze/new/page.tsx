"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Toggle } from "@/components/ui/toggle";
import { useToast } from "@/components/ui/toast";
import { FormWizard } from "@/components/forms/form-wizard";
import { DynamicList } from "@/components/forms/dynamic-list";
import { KeyValueField } from "@/components/forms/key-value-field";
import { MetadataColumnsField } from "@/components/forms/metadata-columns-field";
import { YamlPreview } from "@/components/forms/yaml-preview";
import { api } from "@/lib/api";
import {
  AUTH_TYPES,
  CDC_MODES,
  FILE_FORMATS,
  LOAD_TYPES,
  PAGINATION_TYPES,
  SCHEMA_EVOLUTION_MODES,
  SOURCE_TYPES,
} from "@/lib/constants";
import type { SourceFormData } from "@/types";
import { useRouter } from "next/navigation";
import { useState } from "react";

const defaultForm: SourceFormData = {
  name: "",
  source_type: "jdbc",
  description: "",
  enabled: true,
  tags: {},
  connection: { properties: {} },
  extract: {
    load_type: "full",
    num_partitions: 1,
    fetch_size: 10000,
    format: "parquet",
    format_options: {},
    auto_loader: false,
    method: "GET",
    headers: {},
    params: {},
    timeout_seconds: 30,
    max_retries: 3,
    retry_backoff_factor: 2.0,
    response_root_path: "data",
    kafka_options: {},
    event_hub_consumer_group: "$Default",
    starting_offsets: "earliest",
  },
  target: {
    catalog: "${catalog}",
    schema: "bronze",
    table: "",
    partition_by: ["_ingest_date"],
    z_order_by: [],
    table_properties: {
      "delta.autoOptimize.optimizeWrite": "true",
    },
    metadata_columns: [
      { name: "_ingest_timestamp", expression: "current_timestamp()" },
      { name: "_ingest_date", expression: "current_date()" },
      { name: "_source_system", expression: "''" },
      { name: "_source_file", expression: "input_file_name()" },
    ],
    schema_evolution: { mode: "merge", rescued_data_column: "_rescued_data" },
    quality: { enabled: true, quarantine_threshold_pct: 10.0 },
    cdc: {
      enabled: false,
      mode: "append",
      primary_keys: [],
      exclude_columns_from_hash: [
        "_ingest_timestamp",
        "_ingest_date",
        "_source_file",
      ],
    },
    landing: { retention_days: 10, cleanup_enabled: true },
  },
};

export default function NewSourcePage() {
  const router = useRouter();
  const { toast } = useToast();
  const [form, setForm] = useState<SourceFormData>(defaultForm);
  const [submitting, setSubmitting] = useState(false);
  const [yamlPreview, setYamlPreview] = useState<string>("");

  const update = <K extends keyof SourceFormData>(
    key: K,
    value: SourceFormData[K]
  ) => setForm((prev) => ({ ...prev, [key]: value }));

  const updateNested = (
    path: string,
    value: any
  ) => {
    setForm((prev) => {
      const next = JSON.parse(JSON.stringify(prev));
      const keys = path.split(".");
      let obj = next;
      for (let i = 0; i < keys.length - 1; i++) {
        obj = obj[keys[i]];
      }
      obj[keys[keys.length - 1]] = value;
      return next;
    });
  };

  const handlePreview = async () => {
    try {
      const res = await api.validateSource("preview", form);
      setYamlPreview(res.yaml_preview || "Validation failed");
    } catch {
      // Generate a simple preview client-side
      setYamlPreview(JSON.stringify(form, null, 2));
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await api.createSource(form);
      toast(`Source '${form.name}' created successfully`, "success");
      router.push("/bronze");
    } catch (err: any) {
      toast(err.message || "Failed to create source", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const steps = [
    {
      id: "general",
      title: "General",
      description: "Name, type, and basic settings",
      content: (
        <div className="space-y-5">
          <Input
            label="Source Name"
            value={form.name}
            onChange={(e) => update("name", e.target.value)}
            placeholder="e.g., erp_orders"
            hint="Lowercase, underscores. Used as YAML filename."
          />
          <div>
            <label className="block text-sm font-medium text-text-primary mb-2">
              Source Type
            </label>
            <div className="grid grid-cols-4 gap-3">
              {SOURCE_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => update("source_type", t.value)}
                  className={`p-3 rounded-[var(--radius-md)] border text-left transition-all ${
                    form.source_type === t.value
                      ? "border-accent bg-accent-light"
                      : "border-border hover:border-border-hover"
                  }`}
                >
                  <p className="text-sm font-medium text-text-primary">
                    {t.label}
                  </p>
                  <p className="text-xs text-text-tertiary mt-0.5">
                    {t.description}
                  </p>
                </button>
              ))}
            </div>
          </div>
          <Input
            label="Description"
            value={form.description}
            onChange={(e) => update("description", e.target.value)}
            placeholder="Brief description of this data source"
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
    {
      id: "connection",
      title: "Connection",
      description: "Source-specific connection details",
      content: (
        <div className="space-y-5">
          {/* JDBC */}
          {form.source_type === "jdbc" && (
            <>
              <Input
                label="Host"
                value={form.connection.host || ""}
                onChange={(e) => updateNested("connection.host", e.target.value)}
                placeholder="db-host.company.com"
              />
              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="Port"
                  type="number"
                  value={form.connection.port || ""}
                  onChange={(e) => updateNested("connection.port", parseInt(e.target.value) || undefined)}
                  placeholder="1433"
                />
                <Input
                  label="Database"
                  value={form.connection.database || ""}
                  onChange={(e) => updateNested("connection.database", e.target.value)}
                  placeholder="MyDatabase"
                />
              </div>
              <Input
                label="JDBC Driver"
                value={form.connection.driver || ""}
                onChange={(e) => updateNested("connection.driver", e.target.value)}
                placeholder="com.microsoft.sqlserver.jdbc.SQLServerDriver"
              />
              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="Secret Scope"
                  value={form.connection.secret_scope || ""}
                  onChange={(e) => updateNested("connection.secret_scope", e.target.value)}
                  placeholder="${secret_scope}"
                />
                <Input
                  label="Secret Key (User)"
                  value={form.connection.secret_key_user || ""}
                  onChange={(e) => updateNested("connection.secret_key_user", e.target.value)}
                />
              </div>
              <Input
                label="Secret Key (Password)"
                value={form.connection.secret_key_password || ""}
                onChange={(e) => updateNested("connection.secret_key_password", e.target.value)}
              />
              <KeyValueField
                label="Connection Properties"
                value={form.connection.properties}
                onChange={(v) => updateNested("connection.properties", v)}
              />
            </>
          )}

          {/* FILE */}
          {form.source_type === "file" && (
            <>
              <Input
                label="Path"
                value={form.extract.path || ""}
                onChange={(e) => updateNested("extract.path", e.target.value)}
                placeholder="${storage_base}/landing/my_data/"
              />
              <Select
                label="Format"
                value={form.extract.format}
                onChange={(e) => updateNested("extract.format", e.target.value)}
                options={FILE_FORMATS.map((f) => ({ value: f, label: f.toUpperCase() }))}
              />
              <Toggle
                label="Auto Loader (Structured Streaming)"
                checked={form.extract.auto_loader}
                onChange={(v) => updateNested("extract.auto_loader", v)}
              />
              {form.extract.auto_loader && (
                <Input
                  label="Checkpoint Path"
                  value={form.extract.checkpoint_path || ""}
                  onChange={(e) => updateNested("extract.checkpoint_path", e.target.value)}
                  placeholder="${checkpoint_base}/my_data/"
                />
              )}
              <KeyValueField
                label="Format Options"
                value={form.extract.format_options}
                onChange={(v) => updateNested("extract.format_options", v)}
              />
            </>
          )}

          {/* API */}
          {form.source_type === "api" && (
            <>
              <Input
                label="Base URL"
                value={form.extract.base_url || ""}
                onChange={(e) => updateNested("extract.base_url", e.target.value)}
                placeholder="https://api.example.com"
              />
              <Input
                label="Endpoint"
                value={form.extract.endpoint || ""}
                onChange={(e) => updateNested("extract.endpoint", e.target.value)}
                placeholder="/v2/transactions"
              />
              <div className="grid grid-cols-3 gap-4">
                <Input
                  label="Timeout (s)"
                  type="number"
                  value={form.extract.timeout_seconds}
                  onChange={(e) => updateNested("extract.timeout_seconds", parseInt(e.target.value) || 30)}
                />
                <Input
                  label="Max Retries"
                  type="number"
                  value={form.extract.max_retries}
                  onChange={(e) => updateNested("extract.max_retries", parseInt(e.target.value) || 3)}
                />
                <Input
                  label="Response Root"
                  value={form.extract.response_root_path}
                  onChange={(e) => updateNested("extract.response_root_path", e.target.value)}
                />
              </div>
              <Select
                label="Auth Type"
                value={form.extract.auth?.type || "none"}
                onChange={(e) => {
                  if (e.target.value === "none") {
                    updateNested("extract.auth", undefined);
                  } else {
                    updateNested("extract.auth", {
                      type: e.target.value,
                      header_name: "Authorization",
                      header_prefix: "Bearer",
                    });
                  }
                }}
                options={AUTH_TYPES.map((a) => ({
                  value: a.value,
                  label: a.label,
                }))}
              />
              {form.extract.auth && form.extract.auth.type === "oauth2" && (
                <div className="space-y-4 p-4 rounded-[var(--radius-md)] border border-border bg-bg-secondary/30">
                  <Input
                    label="Token URL"
                    value={form.extract.auth.token_url || ""}
                    onChange={(e) => updateNested("extract.auth.token_url", e.target.value)}
                  />
                  <Input
                    label="Client ID Secret Key"
                    value={form.extract.auth.secret_key_client_id || ""}
                    onChange={(e) => updateNested("extract.auth.secret_key_client_id", e.target.value)}
                  />
                  <Input
                    label="Client Secret Secret Key"
                    value={form.extract.auth.secret_key_client_secret || ""}
                    onChange={(e) => updateNested("extract.auth.secret_key_client_secret", e.target.value)}
                  />
                </div>
              )}
              {form.extract.auth && form.extract.auth.type === "bearer" && (
                <Input
                  label="Token Secret Key"
                  value={form.extract.auth.secret_key_token || ""}
                  onChange={(e) => updateNested("extract.auth.secret_key_token", e.target.value)}
                />
              )}
              <KeyValueField
                label="Request Headers"
                value={form.extract.headers}
                onChange={(v) => updateNested("extract.headers", v)}
              />
              <KeyValueField
                label="Query Parameters"
                value={form.extract.params}
                onChange={(v) => updateNested("extract.params", v)}
              />
            </>
          )}

          {/* STREAM */}
          {form.source_type === "stream" && (
            <>
              <Input
                label="Kafka Bootstrap Servers"
                value={form.extract.kafka_bootstrap_servers || ""}
                onChange={(e) => updateNested("extract.kafka_bootstrap_servers", e.target.value)}
                placeholder="broker1:9092,broker2:9092"
              />
              <Input
                label="Kafka Topic"
                value={form.extract.kafka_topic || ""}
                onChange={(e) => updateNested("extract.kafka_topic", e.target.value)}
              />
              <Input
                label="Consumer Group"
                value={form.extract.kafka_consumer_group || ""}
                onChange={(e) => updateNested("extract.kafka_consumer_group", e.target.value)}
                placeholder="bronze-ingestion"
              />
              <Input
                label="Checkpoint Path"
                value={form.extract.checkpoint_path || ""}
                onChange={(e) => updateNested("extract.checkpoint_path", e.target.value)}
                placeholder="${checkpoint_base}/my_stream/"
              />
              <Select
                label="Starting Offsets"
                value={form.extract.starting_offsets}
                onChange={(e) => updateNested("extract.starting_offsets", e.target.value)}
                options={[
                  { value: "earliest", label: "Earliest" },
                  { value: "latest", label: "Latest" },
                ]}
              />
              <KeyValueField
                label="Kafka Options"
                value={form.extract.kafka_options}
                onChange={(v) => updateNested("extract.kafka_options", v)}
              />
            </>
          )}
        </div>
      ),
    },
    {
      id: "extract",
      title: "Extract",
      description: "Load type, watermark, and pagination",
      content: (
        <div className="space-y-5">
          <Select
            label="Load Type"
            value={form.extract.load_type}
            onChange={(e) => updateNested("extract.load_type", e.target.value)}
            options={LOAD_TYPES.map((l) => ({
              value: l.value,
              label: l.label,
            }))}
          />
          {form.source_type === "jdbc" && (
            <>
              <Input
                label="Source Table"
                value={form.extract.table || ""}
                onChange={(e) => updateNested("extract.table", e.target.value)}
                placeholder="dbo.MyTable"
              />
              <div className="grid grid-cols-3 gap-4">
                <Input
                  label="Partition Column"
                  value={form.extract.partition_column || ""}
                  onChange={(e) => updateNested("extract.partition_column", e.target.value)}
                />
                <Input
                  label="Num Partitions"
                  type="number"
                  value={form.extract.num_partitions}
                  onChange={(e) => updateNested("extract.num_partitions", parseInt(e.target.value) || 1)}
                />
                <Input
                  label="Fetch Size"
                  type="number"
                  value={form.extract.fetch_size}
                  onChange={(e) => updateNested("extract.fetch_size", parseInt(e.target.value) || 10000)}
                />
              </div>
            </>
          )}
          {form.extract.load_type === "incremental" && (
            <div className="p-4 rounded-[var(--radius-md)] border border-border bg-bg-secondary/30 space-y-4">
              <p className="text-sm font-medium text-text-primary">
                Watermark Configuration
              </p>
              <Input
                label="Watermark Column"
                value={form.extract.watermark?.column || ""}
                onChange={(e) =>
                  updateNested("extract.watermark", {
                    ...form.extract.watermark,
                    column: e.target.value,
                    type: form.extract.watermark?.type || "timestamp",
                  })
                }
                placeholder="updated_at"
              />
              <div className="grid grid-cols-2 gap-4">
                <Select
                  label="Watermark Type"
                  value={form.extract.watermark?.type || "timestamp"}
                  onChange={(e) =>
                    updateNested("extract.watermark", {
                      ...form.extract.watermark,
                      type: e.target.value,
                    })
                  }
                  options={[
                    { value: "timestamp", label: "Timestamp" },
                    { value: "integer", label: "Integer" },
                    { value: "date", label: "Date" },
                  ]}
                />
                <Input
                  label="Default Value"
                  value={form.extract.watermark?.default_value || ""}
                  onChange={(e) =>
                    updateNested("extract.watermark", {
                      ...form.extract.watermark,
                      default_value: e.target.value,
                    })
                  }
                  placeholder="2020-01-01T00:00:00"
                />
              </div>
            </div>
          )}
          {form.source_type === "api" && (
            <div className="p-4 rounded-[var(--radius-md)] border border-border bg-bg-secondary/30 space-y-4">
              <p className="text-sm font-medium text-text-primary">
                Pagination
              </p>
              <Toggle
                label="Enable Pagination"
                checked={!!form.extract.pagination}
                onChange={(v) =>
                  updateNested(
                    "extract.pagination",
                    v
                      ? {
                          type: "offset",
                          page_size: 100,
                          offset_param: "offset",
                          limit_param: "limit",
                          cursor_param: "cursor",
                          data_response_path: "data",
                        }
                      : undefined
                  )
                }
              />
              {form.extract.pagination && (
                <>
                  <Select
                    label="Pagination Type"
                    value={form.extract.pagination.type}
                    onChange={(e) =>
                      updateNested("extract.pagination.type", e.target.value)
                    }
                    options={PAGINATION_TYPES.map((p) => ({
                      value: p.value,
                      label: p.label,
                    }))}
                  />
                  <div className="grid grid-cols-2 gap-4">
                    <Input
                      label="Page Size"
                      type="number"
                      value={form.extract.pagination.page_size}
                      onChange={(e) =>
                        updateNested(
                          "extract.pagination.page_size",
                          parseInt(e.target.value) || 100
                        )
                      }
                    />
                    <Input
                      label="Max Pages"
                      type="number"
                      value={form.extract.pagination.max_pages || ""}
                      onChange={(e) =>
                        updateNested(
                          "extract.pagination.max_pages",
                          e.target.value ? parseInt(e.target.value) : undefined
                        )
                      }
                      placeholder="Unlimited"
                    />
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      ),
    },
    {
      id: "target",
      title: "Target",
      description: "Delta Lake table settings",
      content: (
        <div className="space-y-5">
          <div className="grid grid-cols-3 gap-4">
            <Input
              label="Catalog"
              value={form.target.catalog}
              onChange={(e) => updateNested("target.catalog", e.target.value)}
              placeholder="${catalog}"
            />
            <Input
              label="Schema"
              value={form.target.schema}
              onChange={(e) => updateNested("target.schema", e.target.value)}
              placeholder="bronze"
            />
            <Input
              label="Table"
              value={form.target.table}
              onChange={(e) => updateNested("target.table", e.target.value)}
              placeholder="my_table"
            />
          </div>
          <DynamicList
            label="Partition By"
            value={form.target.partition_by}
            onChange={(v) => updateNested("target.partition_by", v)}
            placeholder="Column name"
          />
          <DynamicList
            label="Z-Order By"
            value={form.target.z_order_by}
            onChange={(v) => updateNested("target.z_order_by", v)}
            placeholder="Column name"
          />
          <KeyValueField
            label="Table Properties"
            value={form.target.table_properties}
            onChange={(v) => updateNested("target.table_properties", v)}
          />
        </div>
      ),
    },
    {
      id: "cdc",
      title: "CDC & Quality",
      description: "Change data capture and quality rules",
      content: (
        <div className="space-y-6">
          {/* CDC */}
          <div className="space-y-4">
            <Toggle
              label="Enable CDC"
              checked={form.target.cdc.enabled}
              onChange={(v) => updateNested("target.cdc.enabled", v)}
            />
            {form.target.cdc.enabled && (
              <div className="p-4 rounded-[var(--radius-md)] border border-border bg-bg-secondary/30 space-y-4">
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
                          form.target.cdc.mode === m.value
                            ? "border-accent bg-accent-light"
                            : "border-border hover:border-border-hover"
                        }`}
                      >
                        <p className="text-sm font-medium">{m.label}</p>
                        <p className="text-xs text-text-tertiary mt-0.5">
                          {m.description}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
                <DynamicList
                  label="Primary Keys"
                  value={form.target.cdc.primary_keys}
                  onChange={(v) => updateNested("target.cdc.primary_keys", v)}
                  placeholder="Column name"
                />
                <Input
                  label="Sequence Column"
                  value={form.target.cdc.sequence_column || ""}
                  onChange={(e) => updateNested("target.cdc.sequence_column", e.target.value || undefined)}
                  placeholder="updated_at"
                  hint="Column used to order records within the same key"
                />
                <DynamicList
                  label="Exclude Columns from Hash"
                  value={form.target.cdc.exclude_columns_from_hash}
                  onChange={(v) => updateNested("target.cdc.exclude_columns_from_hash", v)}
                />
              </div>
            )}
          </div>

          {/* Schema Evolution */}
          <div>
            <label className="block text-sm font-medium text-text-primary mb-2">
              Schema Evolution Mode
            </label>
            <div className="grid grid-cols-3 gap-3">
              {SCHEMA_EVOLUTION_MODES.map((m) => (
                <button
                  key={m.value}
                  type="button"
                  onClick={() => updateNested("target.schema_evolution.mode", m.value)}
                  className={`p-3 rounded-[var(--radius-md)] border text-left transition-all ${
                    form.target.schema_evolution.mode === m.value
                      ? "border-accent bg-accent-light"
                      : "border-border hover:border-border-hover"
                  }`}
                >
                  <p className="text-sm font-medium">{m.label}</p>
                  <p className="text-xs text-text-tertiary mt-0.5">
                    {m.description}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* Quality */}
          <div className="space-y-4">
            <Toggle
              label="Enable Data Quality Checks"
              checked={form.target.quality.enabled}
              onChange={(v) => updateNested("target.quality.enabled", v)}
            />
            {form.target.quality.enabled && (
              <Input
                label="Quarantine Threshold (%)"
                type="number"
                value={form.target.quality.quarantine_threshold_pct}
                onChange={(e) =>
                  updateNested(
                    "target.quality.quarantine_threshold_pct",
                    parseFloat(e.target.value) || 10.0
                  )
                }
                hint="Fail the job if bad records exceed this percentage"
              />
            )}
          </div>
        </div>
      ),
    },
    {
      id: "metadata",
      title: "Metadata",
      description: "Injected columns and file settings",
      content: (
        <div className="space-y-6">
          <MetadataColumnsField
            value={form.target.metadata_columns}
            onChange={(v) => updateNested("target.metadata_columns", v)}
          />
          {form.source_type === "file" && (
            <div className="p-4 rounded-[var(--radius-md)] border border-border bg-bg-secondary/30 space-y-4">
              <p className="text-sm font-medium text-text-primary">
                Landing Zone
              </p>
              <Input
                label="Landing Path"
                value={form.target.landing.path || ""}
                onChange={(e) => updateNested("target.landing.path", e.target.value || undefined)}
              />
              <Input
                label="Archive Path"
                value={form.target.landing.archive_path || ""}
                onChange={(e) => updateNested("target.landing.archive_path", e.target.value || undefined)}
              />
              <Input
                label="Retention Days"
                type="number"
                value={form.target.landing.retention_days}
                onChange={(e) => updateNested("target.landing.retention_days", parseInt(e.target.value) || 10)}
              />
              <Toggle
                label="Cleanup Enabled"
                checked={form.target.landing.cleanup_enabled}
                onChange={(v) => updateNested("target.landing.cleanup_enabled", v)}
              />
            </div>
          )}
        </div>
      ),
    },
    {
      id: "review",
      title: "Review",
      description: "Schedule and final review",
      content: (
        <div className="space-y-6">
          <div className="space-y-4">
            <Input
              label="Cron Schedule (Quartz)"
              value={form.schedule?.cron_expression || ""}
              onChange={(e) =>
                updateNested("schedule", {
                  cron_expression: e.target.value || undefined,
                  timezone: form.schedule?.timezone || "UTC",
                  pause_status: "UNPAUSED",
                })
              }
              placeholder="0 0 6 * * ? (6 AM daily)"
              hint="Leave empty for manual-only execution"
            />
          </div>
          <Button variant="secondary" onClick={handlePreview}>
            Generate YAML Preview
          </Button>
          {yamlPreview && <YamlPreview yaml={yamlPreview} />}
        </div>
      ),
    },
  ];

  return (
    <FormWizard steps={steps} onSubmit={handleSubmit} submitting={submitting} />
  );
}
