export type SourceType = "jdbc" | "file" | "api" | "stream";
export type CdcMode = "scd2" | "upsert" | "append";
export type LoadType = "full" | "incremental";
export type SchemaEvolutionMode = "merge" | "strict" | "rescue";
export type AuthType = "oauth2" | "api_key" | "bearer" | "none";
export type PaginationType = "offset" | "cursor" | "link_header";

export interface SourceSummary {
  name: string;
  source_type: SourceType;
  description: string;
  enabled: boolean;
  tags: Record<string, string>;
  target_table: string;
  cdc_mode: CdcMode;
  load_type: LoadType;
  schedule: string | null;
}

export interface SourceDetail {
  name: string;
  source_type: SourceType;
  description: string;
  enabled: boolean;
  tags: Record<string, string>;
  connection: Record<string, any>;
  extract: Record<string, any>;
  target: Record<string, any>;
  schedule: Record<string, any> | null;
  raw_yaml: string;
}

export interface SourceListResponse {
  sources: SourceSummary[];
  total: number;
}

export interface DashboardStats {
  total_sources: number;
  enabled_sources: number;
  disabled_sources: number;
  sources_by_type: Record<string, number>;
  recent_runs: number;
  recent_failures: number;
}

export interface RunRecord {
  source_name: string;
  environment: string;
  start_time: string | null;
  end_time: string | null;
  status: string;
  records_read: number;
  records_written: number;
  records_quarantined: number;
  error: string | null;
}

export interface RunHistoryResponse {
  source_name: string;
  runs: RunRecord[];
  total: number;
}

export interface DeadLetterResponse {
  source_name: string;
  total_count: number;
  recent_records: Record<string, any>[];
}

export interface ValidationResponse {
  valid: boolean;
  errors: string[];
  yaml_preview: string | null;
}

export interface EnvironmentInfo {
  name: string;
  variables: Record<string, string>;
}

export interface MetadataColumn {
  name: string;
  expression: string;
}

export interface SourceFormData {
  name: string;
  source_type: SourceType;
  description: string;
  enabled: boolean;
  tags: Record<string, string>;
  connection: {
    host?: string;
    port?: number;
    database?: string;
    driver?: string;
    url?: string;
    secret_scope?: string;
    secret_key_user?: string;
    secret_key_password?: string;
    properties: Record<string, string>;
  };
  extract: {
    load_type: LoadType;
    table?: string;
    query?: string;
    partition_column?: string;
    num_partitions: number;
    fetch_size: number;
    path?: string;
    format: string;
    format_options: Record<string, string>;
    auto_loader: boolean;
    checkpoint_path?: string;
    base_url?: string;
    endpoint?: string;
    method: string;
    headers: Record<string, string>;
    params: Record<string, string>;
    timeout_seconds: number;
    max_retries: number;
    retry_backoff_factor: number;
    response_root_path: string;
    kafka_bootstrap_servers?: string;
    kafka_topic?: string;
    kafka_consumer_group?: string;
    kafka_options: Record<string, string>;
    event_hub_connection_string_key?: string;
    event_hub_consumer_group: string;
    starting_offsets: string;
    watermark?: {
      column: string;
      type: string;
      default_value?: string;
    };
    auth?: {
      type: AuthType;
      secret_scope?: string;
      secret_key_token?: string;
      secret_key_client_id?: string;
      secret_key_client_secret?: string;
      token_url?: string;
      header_name: string;
      header_prefix: string;
    };
    pagination?: {
      type: PaginationType;
      page_size: number;
      max_pages?: number;
      offset_param: string;
      limit_param: string;
      cursor_param: string;
      cursor_response_path?: string;
      data_response_path: string;
    };
  };
  target: {
    catalog: string;
    schema: string;
    table: string;
    partition_by: string[];
    z_order_by: string[];
    table_properties: Record<string, string>;
    metadata_columns: MetadataColumn[];
    schema_evolution: {
      mode: SchemaEvolutionMode;
      rescued_data_column: string;
    };
    quality: {
      enabled: boolean;
      quarantine_threshold_pct: number;
    };
    cdc: {
      enabled: boolean;
      mode: CdcMode;
      primary_keys: string[];
      sequence_column?: string;
      exclude_columns_from_hash: string[];
      delete_condition_column?: string;
      delete_condition_value?: string;
    };
    landing: {
      path?: string;
      archive_path?: string;
      retention_days: number;
      cleanup_enabled: boolean;
    };
  };
  schedule?: {
    cron_expression?: string;
    timezone: string;
    pause_status: string;
  };
}

// RAG Assistant types
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  created_at?: string;
  query_type?: string;
  sources_used?: string[];
}

export interface ChatResponse {
  answer: string;
  query_type: string;
  sources_used: string[];
  session_id: string;
}

export interface IndexStatus {
  shared_doc_chunks: number;
  tenant_source_chunks: number;
}
