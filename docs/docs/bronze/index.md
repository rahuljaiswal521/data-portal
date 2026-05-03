# Bronze Layer — Overview

The Bronze layer is the **entry point for all data** into the Lakehouse. It ingests raw data from external systems, tracks every change with SCD2 history, enforces data quality rules, and logs every pipeline run.

---

## What is a Bronze source?

A **source** is a configured data pipeline that reads from one system (a file, a database, an API, or a stream) and writes to a Delta Table in the `dev.bronze` schema on Databricks.

Each source has:

- A **unique name** (e.g. `file_crm_customers`, `jdbc_erp_orders`)
- A **source type** — File, JDBC, API, or Stream
- A **target table** in Databricks (`dev.bronze.<table_name>`)
- **SCD2 configuration** — how to detect and track changes
- **Data quality rules** — which columns cannot be null; what percentage of bad records to tolerate before halting

---

## What you can do in the Bronze layer

| Action | Where | Time |
|--------|-------|------|
| View all sources and pipeline health | [Bronze Dashboard](index.md) | Instant |
| Create a new data source | [Add Source wizard](create-source.md) | ~20 min |
| Deploy a source to Databricks | [Deploy](deploy.md) | ~2 min |
| Manually trigger a pipeline run | [Deploy](deploy.md#trigger-a-run) | ~30 sec |
| View run history and record counts | [Monitor](monitor.md) | Instant |
| Inspect rejected / quarantined records | [Monitor](monitor.md#dead-letters) | Instant |
| Run automated test cases | [Testing](testing.md) | ~5 min |

---

## Bronze Dashboard

Navigate to **Bronze Layer → Dashboard** in the sidebar (or go to `/bronze`).

The dashboard shows:

**Stat cards (top row):**

- **Total Sources** — how many source configs exist
- **Active Sources** — how many are enabled and deployed
- **Recent Runs** — number of pipeline runs in the last 24 hours
- **Recent Failures** — runs that ended with an error in the last 24 hours

**Source table (below cards):**

Every source is listed with:

| Column | Description |
|--------|-------------|
| Name | Unique identifier (click to open detail page) |
| Type | File / JDBC / API / Stream |
| Target table | The Databricks Delta Table being written to |
| Status | Enabled / Disabled |
| Last run | Timestamp and status of the most recent run |
| Actions | Edit, Deploy, Delete |

---

## How Bronze sources are stored

Behind the scenes, the portal generates a **YAML configuration file** for each source and stores it in:

```
silver_framework/conf/sources/<source_name>.yaml
```

This file is version-controlled in Git (commits happen automatically when you create or update a source). The portal renders this YAML visually so you never have to read it directly — but you can always view the raw YAML on the source detail page.

---

## Traditional approach (without the portal)

!!! success "Time saved: ~2 days per source"
    | Step | Without portal | With portal |
    |------|---------------|-------------|
    | Write source YAML config | 1–2 hrs (40+ fields, documentation required) | Automated from wizard answers |
    | Write Databricks notebook | 3–4 hrs (PySpark, Delta merge, SCD2 logic) | Automated — framework handles it |
    | Upload notebook to workspace | 15 min (Databricks UI or CLI) | One-click Deploy button |
    | Create Databricks job | 30 min (UI configuration, schedule, cluster) | Automated by Deploy |
    | Configure data quality rules | 1 hr (understand quarantine framework) | Wizard step — select columns + threshold |
    | First successful test run | 2–4 hrs (debugging config mistakes) | ~2 min (validation before deploy) |
    | **Total** | **~2 days** | **~20 minutes** |

---

## Next steps

- [Create your first source](create-source.md)
- [Deploy to Databricks](deploy.md)
- [Monitor pipeline health](monitor.md)
- [Set up data quality rules](quality.md)
- [Run automated tests](testing.md)
