# AI Model Advisor

The Model Advisor uses **Claude AI** to suggest a complete Silver entity schema from a plain English description. It analyses your description and recommends the domain, attributes, data types, business keys, and load type — saving hours of manual schema design.

---

## Navigating to the Model Advisor

In the sidebar, click **Silver Layer → Model Advisor** (or navigate to `/silver/model-advisor`).

---

## Two advisor modes

The Model Advisor has two tabs:

=== "Entity Advisor (Single Entity)"

    Design the schema for **one specific entity** from a description.

    **Best for:**
    - Onboarding a new domain for the first time
    - Designing an entity you have not modelled before

=== "Enterprise Advisor (Cross-Domain)"

    Analyse **how a new entity fits across all existing entities** in your Lakehouse. Considers relationships, avoids duplication, and suggests where to add cross-domain bridge tables.

    **Best for:**
    - Adding an entity to a domain that already has several entities
    - Checking if an attribute belongs in an existing entity rather than a new one
    - Getting relationship recommendations (`customer_id` → `customer.customer_id`)

---

## Using the Entity Advisor

1. Go to the **Entity Advisor** tab
2. In the text box, describe your entity in plain English. Be specific:

    > *"I need a customer entity. It comes from two sources: our CRM system (which has the customer's name, email, and account tier) and our ERP system (which has the same customer's billing address and credit limit). The CRM data is more trusted for personal details. Each customer has a unique customer_id."*

3. Click **Get Suggestion**
4. The advisor returns a suggested schema:

    ```
    Domain:         customer
    Load type:      scd2
    Business keys:  customer_id
    Attributes:
      - full_name      string    source: jdbc_crm    priority: 1
      - email          string    source: jdbc_crm    priority: 1
      - account_tier   string    source: jdbc_crm    priority: 1
      - billing_addr   string    source: jdbc_erp    priority: 1
      - credit_limit   double    source: jdbc_erp    priority: 1
    Sources:
      - jdbc_crm_accounts    priority: 1
      - jdbc_erp_customers   priority: 2
    ```

5. Review the suggestion. If it looks right, click **Apply to Form**
6. The entity creation wizard opens at `/silver/new` with all fields **pre-filled** from the AI suggestion
7. Adjust anything that needs changing, then save

!!! tip "Be descriptive"
    The more context you give (source systems, how they relate, which source is more authoritative), the better the suggestion. Mention primary keys explicitly.

---

## Using the Enterprise Advisor

1. Go to the **Enterprise Advisor** tab
2. Describe the new entity or business concept you want to model
3. The advisor reads **all existing Silver entity YAMLs** and suggests:
    - Whether this should be a new entity or an extension of an existing one
    - Which attributes overlap with existing entities (avoid duplication)
    - Recommended foreign key relationships
    - Which domain schema it belongs in
    - Whether a cross-domain bridge table is needed

**Example prompt:**
> *"I want to model customer support tickets. Each ticket is raised by a customer and relates to a specific policy. Tickets have a status, priority, category, and resolution notes."*

**Enterprise Advisor output:**
```
Recommended entity:  support_ticket
Domain:              slv_interaction (interaction domain)
Load type:           append (tickets are immutable records)

Relationships:
  - customer_id  → slv_customer.customer.customer_id
  - policy_id    → slv_policy.policy.policy_id

Note: Consider slv_xref.ticket_customer_policy as a bridge table
      if you need multi-policy ticket associations.

Attributes:
  - ticket_id     string    business key
  - customer_id   string    FK → customer
  - policy_id     string    FK → policy
  - status        string
  - priority      string
  - category      string
  - resolution    string
  - raised_at     timestamp
  - resolved_at   timestamp (nullable)
```

---

## What the AI does not decide

The Model Advisor makes suggestions — **you are always in control**. Review every suggestion before applying it. The AI may not know:

- Your organisation's specific naming conventions
- Business rules that affect which source is authoritative
- Planned future sources that should be included from the start

---

## Traditional approach (without the portal)

!!! success "Time saved: ~2–4 hours per entity"

    Without the AI Advisor, designing a Silver entity schema required:

    1. Meeting with domain experts to understand the business object (~1 hr)
    2. Reviewing all source system schemas to find relevant columns (~1 hr)
    3. Deciding attribute-level source priority based on data quality knowledge (~30 min)
    4. Drawing the 3NF schema on a whiteboard / in Visio (~30 min)
    5. Cross-checking against existing entities for duplication (~30 min)

    **With the portal:** Describe the entity in a paragraph → review the AI suggestion → click Apply. **~5–10 minutes.**

---

## Related pages

- [Create an Entity](create-entity.md) — complete the entity after applying the AI suggestion
- [Silver Overview](index.md)
- [Entity Diagram](diagram.md) — visualise the relationships the Advisor recommended
