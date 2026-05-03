# Deploy to Databricks

This page explains how to deploy a configured Bronze source to your Databricks workspace and how to trigger a manual pipeline run.

!!! warning "Before you start"
    - The source must already exist — [create it first](create-source.md) if you haven't
    - Your Databricks connection must be healthy (green indicator in the header)
    - The Databricks cluster `1225-063853-8un63us8` must be running

---

## What "Deploy" does

When you click **Deploy**, the portal performs these steps automatically in sequence:

```
1. Validate the YAML config against the Bronze framework schema
2. Upload the source YAML to: /Workspace/bronze_framework/conf/sources/<name>.yaml
3. Upload the Bronze notebook to: /Workspace/bronze_framework/notebooks/<name>
4. Create or update a Databricks job for this source
5. Return the job ID
```

The whole process takes approximately **30–60 seconds**.

---

## How to deploy

1. Navigate to **Bronze Layer → Dashboard** and click on your source name
2. You are on the **source detail page** at `/bronze/{name}`
3. Click the **Deploy** button (top right of the page)
4. A loading indicator appears while the deployment runs
5. On success: a green toast notification confirms deployment, and the source status updates

!!! info "Re-deploying"
    You can click Deploy at any time — it is safe to re-deploy. If the Databricks job already exists, it is updated with the latest config. If it does not exist, it is created fresh.

---

## Trigger a run

After deploying, you can manually trigger a pipeline run immediately:

1. On the source detail page, click the **Trigger** button (next to Deploy)
2. The portal fires the Databricks job
3. A `run_id` is returned and the run appears in the **Runs tab** within a few seconds
4. Watch the status update from `Running` → `Success` or `Failed`

!!! tip "Scheduled runs"
    The Databricks job runs on a schedule configured in the source YAML (`schedule` field). Manual triggering is for ad-hoc testing or re-running after fixing an issue. You do not need to trigger manually for regular production loads.

---

## The Runs tab

After triggering, click the **Runs** tab on the source detail page to see:

| Column | Description |
|--------|-------------|
| Started at | Timestamp of the run start |
| Status | Running / Success / Failed |
| Records loaded | Number of new/changed records written to the target table |
| Records quarantined | Records rejected by data quality rules |
| Duration | How long the run took |

The table shows the most recent runs in descending order. Runs are sourced from the Databricks audit log table (`dev.bronze_meta.ingestion_audit_log`).

---

## What to expect after a successful run

- **Runs tab** shows a new row with status `Success` and a non-zero record count
- **Target table** in Databricks (`dev.bronze.<table_name>`) is populated with data and SCD2 columns (`_valid_from`, `_valid_to`, `_is_current`)
- **Audit log** has a new entry for this run
- **Dashboard stat cards** update to reflect the latest run

---

## Handling a failed run

If the run status shows **Failed**:

1. Click on the run row to expand the error message (if available)
2. Common causes:
    - **Cluster not running** — start the Databricks cluster manually
    - **Secret not found** — the password/token secret referenced in the config does not exist in Databricks secrets
    - **Schema mismatch** — the source data has different columns than expected; check the YAML `columns` config
    - **Quality threshold breached** — too many bad records; check the Quality tab for details
3. Fix the underlying issue, then click **Trigger** again

---

## Traditional approach (without the portal)

!!! success "Time saved: ~45–90 minutes per deploy"
    | Step | Without portal | With portal |
    |------|---------------|-------------|
    | Upload YAML to Databricks | 15 min (Databricks UI or REST API call) | Automatic |
    | Upload notebook | 10 min (Databricks workspace UI, overwrite existing) | Automatic |
    | Create Databricks job | 30–45 min (UI: configure task, cluster, schedule, parameters) | Automatic |
    | Verify job exists | 10 min (navigate Databricks Jobs UI) | Shown in portal |
    | Trigger test run | 5 min (Databricks UI) | One button click |
    | **Total** | **~75 min** | **~2 min** |

---

## Related pages

- [Monitor pipeline runs](monitor.md)
- [Data quality & quarantine](quality.md)
- [Create a source](create-source.md)
