/**
 * Type definitions for the Gold layer ingest + mart APIs.
 * Mirrors the FastAPI backend under /api/v1/gold.
 */

export interface GoldMartSummary {
  name: string;
  description: string;
  schema: string;
  owner: string;
  n_dimensions: number;
  n_facts: number;
  n_metrics: number;
}

export interface GoldDimensionAttribute {
  name: string;
  source_column?: string;
  description?: string;
}

export interface GoldDimension {
  name: string;
  description?: string;
  source_entity: string;
  business_key: string[];
  scd_type: string;
  is_conformed: boolean;
  attributes: GoldDimensionAttribute[];
  quality?: { name: string; assertion: string; severity: string }[];
}

export interface GoldForeignKey {
  dim: string;
  source_column: string;
  sk_column?: string;
}

export interface GoldMeasure {
  name: string;
  expr?: string;
  description?: string;
}

export interface GoldFact {
  name: string;
  description?: string;
  source_entity: string;
  grain: string[];
  load_type: string;
  watermark_column?: string | null;
  foreign_keys: GoldForeignKey[];
  measures: GoldMeasure[];
  degenerate_dimensions?: string[];
  quality?: { name: string; assertion: string; severity: string }[];
}

export interface GoldMetric {
  name: string;
  description?: string;
  fact: string;
  formula: string;
  grain: string[];
  materialization: "view" | "table";
}

export interface GoldMartIR {
  mart: {
    name: string;
    description?: string;
    schema?: string;
    common_schema?: string;
    owner?: string;
    schedule?: { cron_expression?: string; timezone?: string };
  };
  dimensions: GoldDimension[];
  facts: GoldFact[];
  metrics: GoldMetric[];
  warnings?: string[];
}

export interface GoldDiff {
  exists: boolean;
  added: { dimensions: string[]; facts: string[]; metrics: string[] };
  removed: { dimensions: string[]; facts: string[]; metrics: string[] };
  changed: { dimensions: string[]; facts: string[]; metrics: string[] };
}

export interface GoldPreviewResponse {
  ir: GoldMartIR;
  diff: GoldDiff;
  warnings: string[];
  summary: { n_dimensions: number; n_facts: number; n_metrics: number };
}

export interface GoldCommitResponse {
  mart_name: string;
  mart_dir: string;
  n_dimensions: number;
  n_facts: number;
  n_metrics: number;
}

// ── Readiness ──────────────────────────────────────────────────────────────

export interface SourceCheck {
  full_name: string;
  classified_layer: "bronze" | "silver" | "unknown";
  yaml_present: boolean;
  table_reachable: boolean | null;
  referenced_by: string[];
  error: string | null;
  warning: string | null;
}

export interface ColumnIssue {
  source_full_name: string;
  referenced_by: string;
  missing_column: string;
  available_columns: string[];
  suggestions: string[];
}

export interface ReadinessReport {
  ready: boolean;
  summary: {
    sources_total: number;
    sources_ok: number;
    sources_missing_bronze: number;
    sources_missing_silver: number;
    column_issues: number;
  };
  sources: SourceCheck[];
  column_issues: ColumnIssue[];
  errors: string[];
  warnings: string[];
  databricks_available: boolean;
}
