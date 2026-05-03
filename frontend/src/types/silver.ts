export type SilverScdType = "scd2" | "append";

export interface SilverEntitySummary {
  name: string;
  domain: string;
  description: string;
  enabled: boolean;
  tags: Record<string, string>;
  target_table: string;
  scd_type: SilverScdType;
  business_keys: string[];
  source_count: number;
  bronze_tables: string[];
  schedule: string | null;
}

export interface SilverEntityDetail {
  name: string;
  domain: string;
  description: string;
  enabled: boolean;
  tags: Record<string, string>;
  sources: Record<string, any>[];
  target: Record<string, any>;
  schedule: Record<string, any> | null;
  raw_yaml: string;
}

export interface SilverEntityListResponse {
  entities: SilverEntitySummary[];
  total: number;
}

export interface SilverDashboardStats {
  total_entities: number;
  enabled_entities: number;
  domains: string[];
  entities_by_domain: Record<string, number>;
  entities_by_scd_type: Record<string, number>;
  recent_runs: number;
  recent_failures: number;
}

export interface SilverRunRecord {
  entity_name: string;
  domain: string;
  target_table: string;
  status: string;
  start_time: string | null;
  end_time: string | null;
  records_read: number;
  records_written: number;
  records_skipped: number;
  error_message: string | null;
  scd_type: string;
  bronze_sources: string;
}

export interface SilverRunHistoryResponse {
  entity_name: string;
  runs: SilverRunRecord[];
  total: number;
}

export interface SilverValidationResponse {
  valid: boolean;
  errors: string[];
  yaml_preview: string | null;
}

export interface SilverEntityCreateResponse {
  name: string;
  yaml_path: string;
  git_commit: string | null;
  job_id: string | null;
  message: string;
}

export interface SilverEntityDeleteResponse {
  name: string;
  message: string;
}

export interface SilverDiagramResponse {
  mermaid: string;
  entity_count: number;
  domains: string[];
}

// ── Enterprise Model Advisor Types ────────────────────────────────────

export interface BronzeTableInfo {
  table: string;
  full_name: string;
}

export interface EntitySuggestion {
  name: string;
  description: string;
  entity_type: string;
  scd_type: string;
  business_keys: string[];
  source_tables: string[];
  reasoning: string;
  domain?: string;
}

export interface DomainSuggestion {
  domain: string;
  schema: string;
  reasoning: string;
  entities: EntitySuggestion[];
}

export interface EnterpriseModelResponse {
  domains: DomainSuggestion[];
  ungrouped_tables: string[];
  overall_reasoning: string;
  error?: string | null;
}

// ── AI Modeling Types ─────────────────────────────────────────────────

export interface ColumnInfo {
  name: string;
  type: string;
  comment?: string | null;
}

export interface ColumnProfile {
  column: string;
  distinct_count: number;
  null_count: number;
}

export interface TableProfileResponse {
  table: string;
  row_count: number;
  columns: ColumnInfo[];
  profiling: ColumnProfile[];
  sample_data: Record<string, any>[];
  has_scd2_columns: boolean;
  error?: string | null;
}

export interface SuggestedColumnMapping {
  source: string;
  target: string;
  transform?: string | null;
  default_value?: string | null;
  reasoning?: string | null;
}

export interface SuggestedSource {
  bronze_table: string;
  priority: number;
  filter_condition?: string | null;
  watermark?: Record<string, string> | null;
  columns: SuggestedColumnMapping[];
  temporal?: Record<string, any> | null;
}

export interface SuggestedTarget {
  catalog: string;
  schema_name: string;
  table: string;
  scd_type: string;
  business_keys: string[];
  partition_by: string[];
  exclude_columns_from_hash: string[];
}

export interface SuggestModelResponse {
  name?: string | null;
  domain?: string | null;
  description?: string | null;
  entity_type: string;
  sources: SuggestedSource[];
  target?: SuggestedTarget | null;
  reasoning?: string | null;
  warnings: string[];
  error?: string | null;
}
