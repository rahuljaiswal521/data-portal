export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const SOURCE_TYPES = [
  { value: "jdbc", label: "JDBC", description: "Database via JDBC driver" },
  { value: "file", label: "File", description: "Cloud storage files" },
  { value: "api", label: "API", description: "REST API endpoint" },
  { value: "stream", label: "Stream", description: "Kafka / Event Hub" },
] as const;

export const CDC_MODES = [
  { value: "append", label: "Append", description: "Insert-only, no dedup" },
  { value: "upsert", label: "Upsert", description: "Overwrite matched rows" },
  { value: "scd2", label: "SCD2", description: "Full history tracking" },
] as const;

export const LOAD_TYPES = [
  { value: "full", label: "Full Load" },
  { value: "incremental", label: "Incremental" },
] as const;

export const SCHEMA_EVOLUTION_MODES = [
  { value: "merge", label: "Merge", description: "Auto-add new columns" },
  { value: "strict", label: "Strict", description: "Fail on schema change" },
  { value: "rescue", label: "Rescue", description: "Store unknown in rescue column" },
] as const;

export const AUTH_TYPES = [
  { value: "none", label: "None" },
  { value: "oauth2", label: "OAuth2" },
  { value: "api_key", label: "API Key" },
  { value: "bearer", label: "Bearer Token" },
] as const;

export const PAGINATION_TYPES = [
  { value: "offset", label: "Offset" },
  { value: "cursor", label: "Cursor" },
  { value: "link_header", label: "Link Header" },
] as const;

export const FILE_FORMATS = [
  "parquet", "json", "csv", "avro", "orc", "delta",
] as const;

export const METADATA_EXPRESSIONS = [
  { label: "Current Timestamp", value: "current_timestamp()" },
  { label: "Current Date", value: "current_date()" },
  { label: "Input File Name", value: "input_file_name()" },
  { label: "Custom Literal", value: "lit('')" },
] as const;
