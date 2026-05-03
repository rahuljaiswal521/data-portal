# Monitor Pipelines

The portal provides real-time visibility into every Bronze pipeline — run history, record counts, failures, and quarantined records — without needing to open Databricks.

---

## Bronze Dashboard — stats overview

Navigate to **Bronze Layer → Dashboard** (`/bronze`).

The four **stat cards** at the top give you an instant health snapshot:

| Card | What it shows |
|------|--------------|
| **Total Sources** | Total number of configured sources (enabled + disabled) |
| **Active Sources** | Sources that are currently enabled |
| **Recent Runs** | Number of pipeline runs in the last 24 hours across all sources |
| **Recent Failures** | Runs that ended in a `Failed` status in the last 24 hours |

!!! tip
    If **Recent Failures > 0**, click into each source and check its **Runs tab** to find the error.

---

## Source-level run history

1. Go to **Bronze Dashboard** and click any source name
2. Click the **Runs** tab on the source detail page

You will see a table of all recent runs:

| Column | Description |
|--------|-------------|
| **Started at** | When the run began (local timezone) |
| **Status** | `Success` (green) / `Failed` (red) / `Running` (blue spinner) |
| **Records loaded** | New and updated records written to the target Delta Table |
| **Records quarantined** | Records rejected by data quality rules (written to dead letter table) |
| **Duration** | How long the run took (seconds or minutes) |

### Run status meanings

| Status | Meaning |
|--------|---------|
| `Success` | All records processed; quality threshold not breached |
| `Failed` | Pipeline encountered an error; check logs in Databricks |
| `Running` | Pipeline is currently executing |
| `Quarantine-only` | No records loaded to target; all records were bad (check Quality tab) |

---

## Dead letters — inspecting rejected records { #dead-letters }

When a record fails a data quality rule (e.g. a null primary key), it is written to a **dead letter table** instead of the target table. This means bad data never silently reaches your Bronze table.

To inspect rejected records:

1. Go to the source detail page
2. Click the **Quality** tab

You will see a table of quarantined records with:

| Column | Description |
|--------|-------------|
| **Record content** | The raw field values of the rejected record |
| **Rejection reason** | Why it was rejected (e.g. `null_primary_key: order_id`, `rescued_data`) |
| **Run timestamp** | Which pipeline run produced this rejection |

### What to do with dead letters

- If the data is genuinely bad (e.g. test records, incomplete upstream data): no action needed — the portal has protected your Bronze table
- If the data should have been accepted (e.g. a misconfigured quality rule): fix the rule in [source settings](create-source.md), re-deploy, and re-trigger
- Dead letter records are stored permanently in `dev.bronze_meta.dead_letter_{table_name}` and can be queried directly in Databricks SQL if needed

---

## Tracking data volumes over time

The Runs tab shows cumulative `records_loaded` per run. To understand data volume trends:

- **Stable counts** (similar records each run) = normal incremental load
- **Zero records** on a run = no new/changed data since the last run (this is normal for SCD2 if the source data did not change)
- **Sudden spike** = a backfill or schema change; check the YAML `watermark_start` setting
- **Zero records + quarantine count** = all data failed quality checks; investigate immediately

---

## Traditional approach (without the portal)

!!! success "Time saved: ~15–30 minutes per monitoring check"

    Without the portal, checking pipeline health required:

    1. Opening Databricks Jobs UI to find the latest run status (~5 min)
    2. Running SQL against `dev.bronze_meta.ingestion_audit_log` to get record counts (~10 min to write + run the query)
    3. Running SQL against `dev.bronze_meta.dead_letter_{table}` to check quarantined records (~10 min)
    4. No aggregated cross-source dashboard — each source checked separately

    **With the portal:** Open the dashboard → see all sources at a glance → click into any source for detail. **Under 30 seconds.**

---

## Related pages

- [Data quality rules](quality.md) — configure what gets quarantined
- [Deploy & trigger](deploy.md) — start a new run
- [Bronze testing](testing.md) — automated validation of pipeline logic
