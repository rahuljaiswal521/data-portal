# Create a Bronze Source

This page explains how to configure a new data source using the portal's 8-step wizard.

!!! warning "Before you start"
    - You need a Databricks workspace with a running cluster. Check the connection status indicator in the header — it should show green.
    - Know your source system's connection details (host, credentials, file path, etc.) before you begin.

---

## Two ways to create a source

=== "Using the 8-step Wizard"

    1. In the sidebar, click **Bronze Layer → Add Source** (or navigate to `/bronze/new`)
    2. Complete all 8 steps described below
    3. On Step 8, click **Create Source**

=== "Using the AI Assistant"

    1. In the sidebar, click **Platform → AI Assistant** (or navigate to `/bronze/assistant`)
    2. Describe your source in plain English. For example:

        > *"Create a JDBC source for our PostgreSQL ERP database. Table is `orders`, primary key is `order_id`, watermark column is `updated_at`."*

    3. The AI will generate a full configuration and show you a YAML preview
    4. If the preview looks correct, type **"create it"** and the AI will save it for you
    5. You will still need to [Deploy](deploy.md) after creation

    !!! tip
        The AI Assistant is ideal when you are not familiar with all the configuration options, or when you want to describe multiple sources quickly.

---

## The 8-step wizard

### Step 1 — General

| Field | Description | Example |
|-------|-------------|---------|
| **Source name** | Unique snake_case identifier. Used as the YAML filename and Databricks job name. | `jdbc_erp_orders` |
| **Source type** | File / JDBC / API / Stream | `JDBC` |
| **Description** | What this source is (shown on the dashboard) | `ERP order records from SAP` |
| **Enabled** | Toggle off to disable without deleting | On |
| **Tags** | Free-text labels for filtering | `erp`, `finance` |

!!! tip "Naming convention"
    Use `{type}_{domain}_{subject}` — e.g. `file_crm_customers`, `api_payments_transactions`, `stream_events_clickstream`. This makes sources easy to find in the dashboard.

---

### Step 2 — Connection

This step adapts to the **source type** you selected in Step 1.

=== "File"
    | Field | Description |
    |-------|-------------|
    | Volume path | Unity Catalog Volume path where files land (e.g. `/Volumes/dev/bronze/landing_data/crm/`) |
    | File format | CSV, Parquet, JSON, Delta |
    | Delimiter | Character separating fields (CSV only) |
    | Header | Whether the first row contains column names |
    | Encoding | File encoding (default: UTF-8) |

=== "JDBC"
    | Field | Description |
    |-------|-------------|
    | Host | Database server hostname or IP |
    | Port | Database port (e.g. 5432 for PostgreSQL) |
    | Database | Database / schema name |
    | Username | Login username |
    | Password secret | Databricks secret key name (never stored in plain text) |
    | Driver | JDBC driver class (auto-populated for common databases) |

=== "API"
    | Field | Description |
    |-------|-------------|
    | Base URL | REST API endpoint |
    | Auth type | Bearer token / API key / Basic auth |
    | Auth secret | Databricks secret key name for the credential |
    | Headers | Additional HTTP headers (key/value pairs) |

=== "Stream"
    | Field | Description |
    |-------|-------------|
    | Bootstrap servers | Kafka broker list (e.g. `broker1:9092,broker2:9092`) |
    | Topic | Kafka topic name |
    | Consumer group | Consumer group ID |
    | Format | Message format: JSON, Avro, Protobuf |
    | Starting offset | `earliest` or `latest` |

---

### Step 3 — Extract

How to read data from the source.

=== "File"
    - **Path expression** — glob pattern to match files (e.g. `*.csv`, `orders_*.parquet`)
    - **Recursive** — scan subdirectories

=== "JDBC"
    - **Query** — SQL query or table name (e.g. `SELECT * FROM orders` or just `orders`)
    - **Watermark column** — timestamp column for incremental loads (e.g. `updated_at`)
    - **Watermark start** — earliest date to load from (e.g. `2020-01-01`)

=== "API"
    - **Response path** — JSONPath to the array of records (e.g. `$.data.items`)
    - **Pagination type** — page-based / cursor-based / offset
    - **Page size** — records per request

=== "Stream"
    - **Trigger interval** — how often to process new messages (e.g. `1 minute`)
    - **Max files per trigger** — limits batch size

---

### Step 4 — Target

Where to write the data in Databricks.

| Field | Description | Example |
|-------|-------------|---------|
| **Catalog** | Unity Catalog name | `dev` |
| **Schema** | Database schema | `bronze` |
| **Table** | Delta Table name | `erp_orders` |
| **Partition columns** | Columns to partition by (optional) | `year`, `month` |
| **Z-order columns** | Columns to Z-order for query performance (optional) | `customer_id` |

!!! info "Full table path"
    The target table will be created at `{catalog}.{schema}.{table}` — e.g. `dev.bronze.erp_orders`.

---

### Step 5 — CDC & Quality

How to detect changes and enforce data quality.

**CDC (Change Data Capture) settings:**

| Field | Description |
|-------|-------------|
| **CDC mode** | `append` (insert-only) / `scd2` (track all changes) / `overwrite` (full refresh) |
| **Primary keys** | Columns that uniquely identify a record (e.g. `order_id`) |
| **Watermark column** | Used by `scd2` to detect which records changed |
| **Delete condition column** | Column that flags soft-deletes (e.g. `_cdc_operation = 'D'`) |

**Data quality settings:**

| Field | Description |
|-------|-------------|
| **Quality primary keys** | Columns that must not be null (triggers quarantine if null) |
| **Quarantine threshold %** | If more than this % of records are bad, halt the pipeline. Set to `100` to quarantine without halting. |
| **Dead letter table** | Where rejected records are written (auto-populated as `dev.bronze_meta.dead_letter_{table}`) |

---

### Step 6 — Metadata

Optional system columns injected into every row.

| Column | Description | Default |
|--------|-------------|---------|
| `_ingested_at` | Timestamp when the record was ingested | Auto |
| `_source_file` | Path of the file this record came from (File sources) | Auto |
| `_source_system` | Name of the source system | Source name |
| Custom columns | Any additional key/value metadata pairs | — |

---

### Step 7 — Review (YAML Preview)

Before submitting, the portal renders the full YAML configuration that will be written to disk. **Review this carefully.**

- All fields are shown in their final form
- Sensitive values (passwords, tokens) are referenced by secret key name — never stored in plain text
- If anything looks wrong, click **Back** to fix it

---

### Step 8 — Submit

Click **Create Source** to:

1. Validate the configuration against the Bronze framework schema
2. Write the YAML file to `conf/sources/<name>.yaml`
3. Commit the file to Git
4. Redirect you to the **source detail page**

!!! info "What happens next"
    The source is saved but **not yet deployed**. You will see a "Not deployed" status. Go to [Deploy to Databricks](deploy.md) for the next step.

---

## What to expect after creation

You are taken to the **source detail page** at `/bronze/{name}`, which has four tabs:

| Tab | What you see |
|-----|-------------|
| **Config** | Human-readable rendered view of your configuration |
| **YAML** | Raw YAML file content |
| **Runs** | Empty (no runs yet) |
| **Quality** | Empty (no runs yet) |

The source also appears in the **Bronze Dashboard** table with status **Enabled** but no run history.

---

## Traditional approach (without the portal)

!!! success "Time saved: ~4–6 hours"
    Without the portal, creating a source config required:

    1. Reading the Bronze Framework YAML schema documentation (~30 min)
    2. Hand-writing a 40–80 line YAML file (~1–2 hrs)
    3. Validating it by running the framework CLI locally (~30 min)
    4. Committing to Git with the correct path and filename (~15 min)
    5. Debugging any schema validation errors (~1–2 hrs)

    **With the portal:** Fill in a guided form → review the generated YAML → click Create. **~20 minutes.**

---

## Related pages

- [Deploy to Databricks](deploy.md) — next step after creation
- [Edit a source](../bronze/index.md) — update any field after creation
- [Source Types reference](../reference/source-types.md) — full field reference by type
- [AI Assistant](../platform/ai-assistant.md) — create sources via natural language
