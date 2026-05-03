# Create a Silver Entity

This page explains how to define a new canonical Silver entity using the portal's entity creation wizard.

!!! tip "Try the AI Model Advisor first"
    Before filling in the wizard manually, try the [AI Model Advisor](model-advisor.md). Describe your entity in plain English and the AI will pre-fill most of the wizard fields for you.

---

## Starting the wizard

1. In the sidebar, click **Silver Layer → New Entity** (or navigate to `/silver/new`)

---

## Wizard fields

### Entity name

A unique snake_case identifier for this entity. Used as the YAML filename and the Databricks table name.

**Convention:** Use the domain entity name directly — e.g. `customer`, `policy`, `payment_transaction`, `customer_interaction`.

### Domain

The business domain this entity belongs to. This determines the Silver schema:

| Domain | Schema |
|--------|--------|
| `customer` | `dev.slv_customer` |
| `policy` | `dev.slv_policy` |
| `payment` | `dev.slv_payment` |
| `interaction` | `dev.slv_interaction` |

### Load type

| Type | Description | Use when |
|------|-------------|---------|
| `scd2` | Track every change with full history | The entity's historical state matters (most entities) |
| `append` | Insert-only; no updates or history tracking | Event logs, immutable transaction records |

### Business keys

The column(s) that uniquely identify a record in this entity.

**Example:** For a `customer` entity, the business key might be `customer_id`. For a `policy` entity: `policy_number`.

You can add multiple business keys (composite key) using the **+ Add Key** button.

---

## Defining attributes

Each attribute is a column in the final Silver entity table.

For each attribute, configure:

| Field | Description | Example |
|-------|-------------|---------|
| **Attribute name** | Snake_case column name | `full_name` |
| **Data type** | String / Integer / Long / Double / Boolean / Date / Timestamp | `string` |
| **Source** | Which Bronze source this attribute comes from | `jdbc_crm_accounts` |
| **Source column** | The column name in the Bronze source | `customer_name` |
| **Priority** | If multiple sources have this attribute, which wins (lower = higher priority) | `1` |
| **Nullable** | Whether this column can be null | `false` |

### Multi-source attributes

If two Bronze sources both have a value for the same attribute (e.g. CRM and ERP both have `email`), add the attribute twice with different source + priority settings:

```
email  ← source: jdbc_crm_accounts,  priority: 1  (CRM wins)
email  ← source: jdbc_erp_orders,    priority: 2  (ERP is fallback)
```

The Silver merge logic uses **attribute-level source priority**: if the CRM has a non-null email, it uses that. If not, it falls back to the ERP email.

---

## Source mappings

In the **Sources** section, add every Bronze source that feeds this entity:

| Field | Description |
|-------|-------------|
| **Source name** | The Bronze source name (e.g. `jdbc_crm_accounts`) |
| **Join key** | How the source's primary key maps to the entity's business key (e.g. `account_id → customer_id`) |
| **Priority** | Source-level priority for conflict resolution |

---

## Reviewing the YAML

Before saving, the portal shows the generated YAML. A minimal entity YAML looks like this:

```yaml
entity:
  name: customer
  domain: customer
  load_type: scd2
  business_keys:
    - customer_id
  attributes:
    - name: full_name
      type: string
      source: jdbc_crm_accounts
      source_column: customer_name
      priority: 1
    - name: email
      type: string
      source: jdbc_crm_accounts
      source_column: email
      priority: 1
  sources:
    - name: jdbc_crm_accounts
      join_key:
        account_id: customer_id
      priority: 1
```

---

## What happens after saving

1. The YAML is written to `silver_framework/conf/entities/<name>.yaml`
2. A Git commit is created
3. You are redirected to the **entity detail page** at `/silver/{name}`
4. The entity appears in the Silver Dashboard

!!! info "Deploy required"
    The entity is saved but not yet in Databricks. Go to [Deploy an Entity](deploy.md) for the next step.

---

## Traditional approach (without the portal)

!!! success "Time saved: ~3–5 hours"

    1. Designing the 3NF attribute list by hand: ~1–2 hrs
    2. Writing the entity YAML with correct schema and merge config: ~1–2 hrs
    3. Understanding attribute-level source priority syntax: ~30 min
    4. Debugging YAML validation errors: ~30–60 min

    **With the portal:** Use [AI Model Advisor](model-advisor.md) to get a suggested schema, tweak it in the wizard, click Save. **~15–30 min.**

---

## Related pages

- [AI Model Advisor](model-advisor.md) — auto-generate the entity schema from a description
- [Deploy an Entity](deploy.md) — push the entity to Databricks
- [Entity Diagram](diagram.md) — see how this entity relates to others
