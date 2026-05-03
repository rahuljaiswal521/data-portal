# Data Quality

The Bronze framework enforces **data quality rules at ingestion time**. Records that fail are quarantined into a separate dead letter table — they never silently reach your Bronze Delta Table.

---

## How data quality works

Every time a Bronze pipeline runs, records go through a two-stage filter:

```
Incoming records
       │
       ▼
┌──────────────────────────────┐
│  Stage 1: Null primary key   │  ← Records with null PK columns → dead letter
└──────────────────────────────┘
       │
       ▼
┌──────────────────────────────┐
│  Stage 2: Rescued data       │  ← Records with unrecognised schema → dead letter
└──────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│  Quarantine threshold check                   │
│  If bad_records / total_records > threshold%  │  ← Halt pipeline (circuit breaker)
│  → raise error, do not write any records      │
└──────────────────────────────────────────────┘
       │
       ▼
   Good records written to target Delta Table
```

---

## Configuring quality rules

Quality rules are set in **Step 5 (CDC & Quality)** of the [source creation wizard](create-source.md).

### Primary key columns (null check)

Enter one or more column names that must not be null. Any record where any of these columns is null is immediately quarantined.

**Example:** For an orders source with `order_id` as the primary key — set quality primary keys to `order_id`. A record with `order_id = null` goes to the dead letter table.

### Quarantine threshold %

The maximum percentage of incoming records that are allowed to be bad before the pipeline **halts entirely** (circuit breaker).

| Setting | Behaviour |
|---------|-----------|
| `5` | If more than 5% of records are bad, stop the run and write nothing to the target table |
| `100` | Never halt — always quarantine bad records but continue writing good ones |
| `0` | Halt immediately if even one bad record is found |

!!! tip "Recommended setting"
    Use `100` during initial onboarding and testing to see what your data quality actually looks like. Tighten the threshold once you understand the expected bad-record rate.

### Dead letter table

Auto-populated as `dev.bronze_meta.dead_letter_{your_table_name}`. You cannot change this — it follows the naming convention of the framework.

---

## Viewing quarantined records

1. Open the source detail page (`/bronze/{name}`)
2. Click the **Quality** tab

Each rejected record is shown with its field values and the rejection reason:

| Reason code | Meaning |
|-------------|---------|
| `null_primary_key: {column}` | The named column was null |
| `rescued_data` | The record had columns not in the expected schema |

---

## Editing quality rules on an existing source

1. Open the source detail page
2. Click the **Edit** button (top right)
3. Navigate to **Step 5 — CDC & Quality**
4. Update the primary key columns or threshold
5. Click **Save Changes**
6. [Re-deploy](deploy.md) the source so the new rules take effect in Databricks

---

## Traditional approach (without the portal)

!!! success "Time saved: ~1–2 hours per source"

    Without the portal, implementing data quality for a source required:

    1. Manually writing the `quality:` block in the YAML file (understanding the framework schema)
    2. Writing a custom PySpark null-check filter in the notebook
    3. Writing logic to route bad records to a separate table
    4. Implementing the threshold circuit-breaker yourself
    5. Testing all edge cases (null PK, rescued data, threshold boundary)

    **With the portal:** Select columns in the wizard → set a threshold percentage → quality enforcement is fully automated.

---

## Related pages

- [Monitor dead letters](monitor.md#dead-letters) — view quarantined records after a run
- [Create a source](create-source.md) — configure quality rules in the wizard
- [Pipeline testing](testing.md) — TC005 specifically tests the quality quarantine behaviour
