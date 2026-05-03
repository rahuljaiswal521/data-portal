# AI Assistant

The AI Assistant is a conversational pipeline builder. Describe a data source in plain English and the AI will configure it for you — no YAML knowledge required.

---

## Navigating to the AI Assistant

In the sidebar, click **Platform → AI Assistant** (or navigate to `/bronze/assistant`).

---

## What the AI Assistant can do

| Capability | Example prompt |
|-----------|---------------|
| **Configure a Bronze source** | *"Create a JDBC source for our PostgreSQL orders database"* |
| **Preview a source config** | *"Show me what the YAML would look like for a CSV file source with SCD2 on customer_id"* |
| **Answer questions** | *"What CDC mode should I use for a streaming Kafka source?"* |
| **Explain configurations** | *"What does the quarantine_threshold_pct field do?"* |

The assistant uses **RAG (Retrieval-Augmented Generation)** — it has access to your existing source configurations and the Bronze framework documentation, so its answers are tailored to your specific setup.

---

## Creating a source via the AI Assistant

=== "Step-by-step"

    1. Open the AI Assistant (`/bronze/assistant`)
    2. Describe your source clearly:

        > *"I want to ingest data from our MySQL orders database. The table is `sales.orders`, primary key is `order_id`, and there's an `updated_at` timestamp column I can use to detect changes. The database host is `mysql-prod.internal`, port 3306, and the password is stored in Databricks secrets as `mysql_orders_password`."*

    3. The AI responds with a **configuration preview** showing all fields it has determined from your description
    4. Review the preview. If anything is wrong, ask the AI to correct it:

        > *"Change the schema to `finance` instead of `sales`"*

    5. Once happy, confirm creation:

        > *"Create it"* or *"Looks good, create the source"*

    6. The AI creates the source and confirms with the source name
    7. You will still need to [Deploy](../bronze/deploy.md) the source to Databricks

=== "What to expect"

    The AI uses a **tool-use loop** (up to 5 iterations) to:

    1. Parse your description and identify all configuration fields
    2. Fill in sensible defaults for anything you did not mention
    3. Generate the YAML preview using the **preview tool**
    4. On confirmation, call the **create tool** to save the source

    If the AI is unsure about something, it will ask a clarifying question rather than guessing.

---

## Tips for effective prompts

**Be specific about these fields** (the AI cannot guess them reliably):

- Primary key columns
- Watermark / timestamp column for incremental loads
- Databricks secret names for credentials
- Target table name (if different from the source table name)

**You do not need to specify:**

- SCD2 merge logic (handled by the framework)
- YAML structure or field names
- Databricks job configuration
- Notebook code

**Example of a detailed, effective prompt:**

> *"Create a file source for our daily customer export. Files are CSV format, dropped at midnight to `/Volumes/dev/bronze/landing_data/customers/`. The primary key is `cust_id`. The `modified_date` column tracks changes. Use SCD2 mode. Target table should be `bronze.crm_customers`. Set a quarantine threshold of 5%."*

---

## Conversation context

The AI maintains context within a session. You can:

- Refer back to earlier messages: *"Change the source type we just discussed to File instead of JDBC"*
- Build up a config iteratively across multiple messages
- Ask follow-up questions: *"What watermark column should I use if my source doesn't have an updated_at?"*

---

## Traditional approach (without the portal)

!!! success "Time saved: ~2–4 hours for complex sources"

    Without the AI Assistant, configuring a source required:

    1. Reading the Bronze Framework documentation to understand all YAML fields (~30–60 min)
    2. Understanding which fields apply to which source type (~30 min)
    3. Writing the YAML manually, field by field (~1–2 hrs)
    4. Validating and debugging the YAML (~30–60 min)

    **With the AI Assistant:** Describe it once in plain English. **~5–15 minutes.**

---

## Related pages

- [Create a source (wizard)](../bronze/create-source.md) — manual 8-step form alternative
- [Deploy to Databricks](../bronze/deploy.md) — next step after the AI creates your source
- [Source Types reference](../reference/source-types.md) — full field reference
