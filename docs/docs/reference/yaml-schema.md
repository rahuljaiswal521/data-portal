# YAML Schema Reference

The portal generates YAML configuration files automatically from the wizard. This page is a complete reference for every field — useful if you need to understand or manually review a generated YAML.

!!! info "You don't need to write YAML"
    The portal writes and manages all YAML files. This reference is for understanding what was generated, or for advanced manual edits.

---

## Bronze source YAML — full structure

```yaml
source:
  # ── Identity ────────────────────────────────────────────────────────
  name: jdbc_erp_orders           # Unique snake_case identifier
  type: jdbc                      # file | jdbc | api | stream
  description: "ERP order records from SAP"
  enabled: true
  tags:
    - erp
    - finance

  # ── Connection (JDBC example) ────────────────────────────────────────
  connection:
    host: erp-db.internal
    port: 1433
    database: erp_prod
    schema: dbo
    username: bronze_reader
    password_secret: erp_db_password   # Databricks secret key
    driver: com.microsoft.sqlserver.jdbc.SQLServerDriver

  # ── Extract ─────────────────────────────────────────────────────────
  extract:
    query: "SELECT * FROM dbo.orders"  # or table: orders
    watermark_column: updated_at
    watermark_start: "2020-01-01"
    fetch_size: 5000

  # ── Target ──────────────────────────────────────────────────────────
  target:
    catalog: dev
    schema: bronze
    table: erp_orders
    partition_columns:
      - year
      - month
    z_order_columns:
      - customer_id

  # ── CDC ─────────────────────────────────────────────────────────────
  cdc:
    mode: scd2                     # scd2 | append | overwrite
    primary_keys:
      - order_id
    watermark_column: updated_at
    delete_condition_column: _cdc_operation   # optional: column that signals deletes

  # ── Data Quality ────────────────────────────────────────────────────
  quality:
    primary_keys:
      - order_id
    quarantine_threshold_pct: 5
    dead_letter_table: dev.bronze_meta.dead_letter_erp_orders

  # ── Metadata columns ────────────────────────────────────────────────
  metadata_columns:
    - name: _ingested_at
      expression: current_timestamp()
    - name: _source_system
      expression: "'erp_orders'"

  # ── Schedule ────────────────────────────────────────────────────────
  schedule: "0 */4 * * *"         # Cron: every 4 hours
```

---

## File source YAML additions

```yaml
  connection:
    volume_path: /Volumes/dev/bronze/landing_data/crm/
    file_format: csv              # csv | parquet | json | delta
    delimiter: ","
    header: true
    encoding: utf-8

  extract:
    path_expression: "customers_*.csv"
    recursive: false
```

---

## API source YAML additions

```yaml
  connection:
    base_url: https://api.salesforce.com/v1/
    endpoint: customers
    auth_type: bearer
    auth_secret: salesforce_api_token
    headers:
      X-API-Version: "2024"

  extract:
    response_path: "$.data.records"
    pagination_type: cursor
    page_size: 200
    cursor_path: "$.meta.next_cursor"
```

---

## Stream source YAML additions

```yaml
  connection:
    bootstrap_servers: "kafka1:9092,kafka2:9092"
    topic: clickstream_events
    consumer_group: bronze_portal_consumer
    format: json
    starting_offset: latest

  extract:
    trigger_interval: "1 minute"
    max_offsets_per_trigger: 50000
```

---

## Silver entity YAML — full structure

```yaml
entity:
  # ── Identity ────────────────────────────────────────────────────────
  name: customer
  domain: customer               # customer | policy | payment | interaction
  load_type: scd2                # scd2 | append
  enabled: true
  description: "Canonical customer entity merged from CRM and ERP"

  # ── Business keys ────────────────────────────────────────────────────
  business_keys:
    - customer_id

  # ── Attributes ──────────────────────────────────────────────────────
  attributes:
    - name: customer_id
      type: string
      source: jdbc_crm_accounts
      source_column: account_id
      priority: 1
      nullable: false

    - name: full_name
      type: string
      source: jdbc_crm_accounts
      source_column: customer_name
      priority: 1
      nullable: true

    - name: email
      type: string
      source: jdbc_crm_accounts
      source_column: email
      priority: 1         # CRM wins if both have email
      nullable: true

    - name: email
      type: string
      source: jdbc_erp_orders
      source_column: billing_email
      priority: 2         # ERP is fallback
      nullable: true

    - name: credit_limit
      type: double
      source: jdbc_erp_orders
      source_column: credit_limit
      priority: 1
      nullable: true

  # ── Sources ─────────────────────────────────────────────────────────
  sources:
    - name: jdbc_crm_accounts
      join_key:
        account_id: customer_id   # source_column: entity_business_key
      priority: 1

    - name: jdbc_erp_orders
      join_key:
        erp_cust_id: customer_id
      priority: 2

  # ── Target ──────────────────────────────────────────────────────────
  target:
    catalog: ${catalog}           # Resolved from environments/dev.yaml
    schema: slv_customer
    table: customer
```

---

## SCD2 system columns (auto-added by framework)

These columns are automatically added to every SCD2 table — you do not configure them:

| Column | Type | Description |
|--------|------|-------------|
| `_valid_from` | timestamp | When this version of the record became active |
| `_valid_to` | timestamp | When this version expired (`9999-12-31` if still current) |
| `_is_current` | boolean | `true` for the latest version of this record |
| `_record_hash` | string | MD5 hash of all non-key attributes (used to detect changes) |
| `_ingested_at` | timestamp | When this record was written by the pipeline |

---

## Related pages

- [Source Types Reference](source-types.md) — field descriptions by type
- [Create a Source](../bronze/create-source.md)
- [Create an Entity](../silver/create-entity.md)
- [Glossary](glossary.md)
