# Source Types Reference

Full field reference for all four Bronze source types supported by the portal.

---

## File

Reads structured files (CSV, Parquet, JSON) from a Unity Catalog Volume landing area.

**Typical use:** Daily/hourly file drops from upstream systems, data received via SFTP, partner data feeds.

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `volume_path` | Yes | UC Volume path where files land | `/Volumes/dev/bronze/landing_data/crm/` |
| `file_format` | Yes | `csv` / `parquet` / `json` / `delta` | `csv` |
| `delimiter` | CSV only | Column separator character | `,` |
| `header` | CSV only | First row contains column names | `true` |
| `encoding` | No | File character encoding | `utf-8` |
| `path_expression` | No | Glob to match files (default: all files) | `customers_*.csv` |
| `recursive` | No | Scan subdirectories | `false` |
| `schema_inference` | No | Auto-detect column types | `true` |

**SCD2 note:** For file sources, the watermark column is typically a `modified_date` or `updated_at` column in the file. If no such column exists, use `overwrite` CDC mode.

---

## JDBC

Connects to relational databases via a JDBC driver.

**Supported databases:** PostgreSQL, MySQL, SQL Server, Oracle, DB2, Snowflake.

**Typical use:** Operational databases (CRM, ERP, billing systems), data warehouses.

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `host` | Yes | Database server hostname | `postgres-prod.internal` |
| `port` | Yes | Database port | `5432` |
| `database` | Yes | Database / catalog name | `salesdb` |
| `schema` | No | Schema within the database | `public` |
| `username` | Yes | Login user | `bronze_reader` |
| `password_secret` | Yes | Databricks secret key name | `postgres_bronze_password` |
| `driver` | Yes | JDBC driver class | `org.postgresql.Driver` |
| `query` | No | Custom SQL query (overrides table) | `SELECT * FROM orders WHERE active = true` |
| `table` | No | Table name (used if no query) | `orders` |
| `watermark_column` | SCD2 | Timestamp column for incremental detection | `updated_at` |
| `watermark_start` | No | Earliest watermark date to load from | `2020-01-01` |
| `fetch_size` | No | JDBC fetch size (tuning) | `10000` |

!!! tip "Storing credentials"
    Never put passwords directly in the portal. Store them in **Databricks Secrets** (under a scope like `bronze`) and reference the key name in the `password_secret` field. The portal never stores credentials — only the key reference.

---

## API

Reads from REST APIs with support for pagination.

**Typical use:** Third-party SaaS platforms (Salesforce, HubSpot, Stripe), internal microservices.

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `base_url` | Yes | API base endpoint | `https://api.example.com/v1/` |
| `endpoint` | Yes | Resource path | `customers` |
| `auth_type` | Yes | `bearer` / `api_key` / `basic` / `none` | `bearer` |
| `auth_secret` | Auth | Databricks secret key for the token | `salesforce_api_token` |
| `headers` | No | Additional HTTP headers (key/value) | `X-Tenant-ID: acme` |
| `response_path` | No | JSONPath to the records array | `$.data.items` |
| `pagination_type` | No | `page` / `cursor` / `offset` / `none` | `page` |
| `page_size` | No | Records per request | `100` |
| `page_param` | No | Query param name for page number | `page` |
| `cursor_path` | cursor | JSONPath to next cursor in response | `$.meta.next_cursor` |

---

## Stream

Reads from Apache Kafka or Azure Event Hubs using Structured Streaming.

**Typical use:** Real-time clickstream events, IoT telemetry, application event logs.

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `bootstrap_servers` | Yes | Kafka broker list | `kafka1:9092,kafka2:9092` |
| `topic` | Yes | Kafka topic name | `clickstream_events` |
| `consumer_group` | Yes | Consumer group ID | `bronze_portal_consumer` |
| `format` | Yes | Message format: `json` / `avro` / `protobuf` | `json` |
| `starting_offset` | No | `earliest` / `latest` | `latest` |
| `trigger_interval` | No | Micro-batch interval | `1 minute` |
| `max_offsets_per_trigger` | No | Limits records per batch | `10000` |
| `schema_registry_url` | Avro | Confluent Schema Registry URL | `http://registry:8081` |

!!! warning "Streaming monitoring"
    Stream sources run continuously. The portal shows run status but does not display message-level monitoring. Use Databricks Structured Streaming dashboards in the Databricks UI for detailed streaming metrics.

---

## Common fields (all source types)

These fields apply to every source regardless of type:

| Field | Required | Description |
|-------|----------|-------------|
| `source_name` | Yes | Unique identifier (snake_case) |
| `source_type` | Yes | `file` / `jdbc` / `api` / `stream` |
| `description` | No | Human-readable description |
| `enabled` | Yes | `true` / `false` — disables without deleting |
| `tags` | No | List of string labels |
| `target.catalog` | Yes | Unity Catalog name (e.g. `dev`) |
| `target.schema` | Yes | Delta schema (e.g. `bronze`) |
| `target.table` | Yes | Delta table name |
| `cdc.mode` | Yes | `scd2` / `append` / `overwrite` |
| `cdc.primary_keys` | SCD2 | List of PK column names |
| `cdc.watermark_column` | SCD2 | Timestamp column for change detection |
| `quality.primary_keys` | No | Columns that must not be null |
| `quality.quarantine_threshold_pct` | No | Max % bad records before halting |
| `schedule` | No | Cron expression for scheduled runs |

---

## Related pages

- [Create a Source](../bronze/create-source.md)
- [YAML Schema Reference](yaml-schema.md)
- [Glossary](glossary.md)
