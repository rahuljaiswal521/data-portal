# Architecture Overview

The Data Platform Portal is built on the **Medallion Architecture** — an industry-standard pattern for organising data in a Lakehouse. This page explains what that means, how the layers relate to each other, and what the portal automates for you.

---

## What is the Medallion Architecture?

The Medallion Architecture organises data into three progressively refined layers, each stored as **Delta Tables** in a **Unity Catalog** on Databricks:

```
Raw Sources                Bronze Layer              Silver Layer             Gold Layer
─────────────     ──────────────────────────  ──────────────────────   ──────────────────
  CSV files    →  Raw ingestion, SCD2         Canonical business       Analytics-ready
  Databases       tracking, quality           entities, 3NF design,    star schema,
  REST APIs        quarantine, audit log       multi-source merge,      fact/dim tables,
  Kafka streams                                AI-assisted modelling    BI data products
```

| Layer | Also called | Purpose | Managed by |
|-------|-------------|---------|-----------|
| **Bronze** | Raw / Landing | Ingest data as-is; track history; quarantine bad records | Bronze Framework |
| **Silver** | Cleansed / Canonical | Merge multiple sources into authoritative business entities | Silver Framework |
| **Gold** | Analytics / Serving | Star schema tables optimised for BI tools | *(coming in v2.0)* |

---

## Bronze Layer — raw ingestion

Bronze is the **entry point** for all data into the Lakehouse. Every source system gets its own Bronze table. The framework handles:

- **SCD2 (Slowly Changing Dimension Type 2)** — every change to a record is tracked with `_valid_from` / `_valid_to` timestamps, so you can time-travel back to any historical state
- **CDC (Change Data Capture)** — detects inserts, updates, and deletes using watermark columns or CDC flags
- **Data quality** — records that fail null-checks or threshold rules are quarantined in a dead letter table, never silently dropped
- **Audit logging** — every pipeline run is recorded: start time, records loaded, records quarantined, duration

**Schema naming:** `dev.bronze.<table_name>`

---

## Silver Layer — canonical entities

Silver is where **raw data becomes trusted business data**. Multiple Bronze sources are merged into a single canonical entity:

- A `customer` entity might combine records from the CRM system (Bronze: `jdbc_crm_accounts`) and the ERP system (Bronze: `jdbc_erp_orders`) using **attribute-level source priority** — e.g. prefer the CRM name but the ERP email
- Relationships between entities are modelled as foreign keys (e.g. `customer_interaction.customer_id → customer.customer_id`)
- Full **SCD2** is applied at the Silver level too — every merge run captures a new version if anything changed

**Schema naming:** `dev.slv_<domain>.<entity_name>` (e.g. `dev.slv_customer.customer`)

---

## Gold Layer — analytics *(coming v2.0)*

Gold tables are optimised for BI tools. They use a **star schema** with `fact_` and `dim_` prefixes. The portal will support building Gold tables in a future release.

**Schema naming:** `dev.gld_<use_case>.<fact_or_dim_table>`

---

## How the portal fits in

Without the portal, every step below required a data engineer to hand-write code and configuration:

```
Traditional workflow (per source — ~2 days):
  1. Write source YAML config (understanding 40+ fields)
  2. Write Databricks notebook (PySpark + Delta merge logic)
  3. Upload notebook to Databricks workspace
  4. Create and configure a Databricks job
  5. Test manually by triggering runs
  6. Debug configuration errors
  7. Set up monitoring queries in a SQL notebook

With the portal (same outcome — ~20 minutes):
  1. Fill in the 8-step web wizard
  2. Click Deploy
  3. Done — monitor from the dashboard
```

The portal also provides:

- **AI-assisted Silver modelling** — describe an entity in English; Claude AI suggests the schema
- **Conversational pipeline builder** — describe a data source in the chat; the AI configures it for you
- **Automated test suites** — 8 standard test cases per source run with one click
- **Unified monitoring** — all pipelines, all layers, one dashboard

---

## Interactive diagram

Visit [Architecture Page](platform/architecture.md) in the portal to see an animated flow diagram showing data moving from sources through Bronze and Silver to Gold, and a GIF overview of the full architecture.
