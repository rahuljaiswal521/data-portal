# Deploy a Silver Entity

This page explains how to deploy a configured Silver entity to Databricks and how to run it.

!!! warning "Before you start"
    - The entity must already exist — [create it](create-entity.md) first
    - The Bronze sources that feed this entity must already be deployed and have run at least once

---

## What Silver deploy does

When you click **Deploy** on a Silver entity, the portal:

```
1. Validates the entity YAML against the Silver framework schema
2. Resolves ${catalog} variables from conf/environments/dev.yaml
3. Uploads the entity YAML to:
       /Workspace/silver_framework/conf/entities/<name>.yaml
4. Uploads the Silver merge notebook to:
       /Workspace/silver_framework/notebooks/<name>
5. Creates or updates a Databricks job for this entity
6. Returns the job ID
```

---

## How to deploy

1. Navigate to **Silver Layer → Dashboard** and click on the entity name
2. On the entity detail page, click the **Deploy** button
3. A toast notification confirms success, and the entity status updates
4. The Databricks job is now ready

---

## Triggering a Silver run

After deploying, click **Trigger** to run the Silver merge immediately:

- The portal fires the Databricks job
- The Silver framework reads from the configured Bronze source tables
- Records are merged into the Silver entity table using SCD2 multi-source merge logic
- Run history appears in the **Runs tab** of the entity detail page

---

## What to expect after a successful run

- The Silver entity table is created / updated at `dev.slv_{domain}.{entity_name}`
- SCD2 columns are present: `_valid_from`, `_valid_to`, `_is_current`, `_record_hash`
- If multiple sources contributed, attribute-level priority resolution has been applied
- The entity appears in the [Entity Diagram](diagram.md) with its relationships

---

## Traditional approach (without the portal)

!!! success "Time saved: ~45 minutes per deploy"

    | Step | Without portal | With portal |
    |------|---------------|-------------|
    | Resolve YAML variable substitution | Manual (`${catalog}` → `dev`) | Automatic |
    | Upload YAML to Databricks | Databricks REST API or UI | Automatic |
    | Upload Silver notebook | Databricks workspace UI | Automatic |
    | Create/update Databricks job | 30 min in Databricks Jobs UI | Automatic |
    | Trigger first run | 5 min | One button click |

---

## Related pages

- [Create an Entity](create-entity.md)
- [Entity Diagram](diagram.md)
- [Silver Overview](index.md)
