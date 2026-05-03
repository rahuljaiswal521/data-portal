# Bronze Pipeline Testing

The portal includes an automated test framework that validates your Bronze pipeline logic before you rely on it in production. Every source gets a pre-defined **8-case test suite** that you can run with one click.

---

## Why test Bronze pipelines?

Bronze pipelines handle complex logic: SCD2 merge, CDC detection, late-arriving data, soft-deletes, and data quality quarantine. A mis-configured pipeline can silently produce wrong data. The test suite catches these issues early.

---

## Navigating to the test suite

1. In the sidebar, click **Testing → Bronze Tests**
2. Select your source from the list
3. You are on the test suite page for that source: `/testing/bronze/{source_name}`

---

## The 8 standard test cases

Every Bronze source automatically gets these 8 test cases:

| TC | Name | What it validates |
|----|------|------------------|
| **TC001** | Initial full load | All records are loaded correctly on first run |
| **TC002** | No-change re-run | Re-running with the same data produces no duplicate records |
| **TC003** | Incremental update | Changed records are correctly detected and written as new SCD2 versions |
| **TC004** | Late-arriving data | A record that arrives out of order does not overwrite a newer version |
| **TC005** | Quality quarantine | Records with null primary keys are quarantined; good records still load |
| **TC006** | Soft delete | A delete flag triggers `_is_current = false` on the active SCD2 record |
| **TC007** | Schema evolution | Adding a new column in the source does not break the pipeline |
| **TC008** | Full refresh | An `overwrite` mode run replaces all existing data correctly |

---

## Running the test suite

### Run all 8 test cases

1. On the test suite page, click **Run All Tests**
2. The portal submits an async request (HTTP 202) and begins running each TC in sequence
3. A progress indicator shows which TC is currently running
4. Results appear as each TC completes — green (pass) or red (fail)
5. When all TCs complete, a summary banner shows overall pass/fail

### Run a single test case

1. Find the TC row in the table
2. Click the **Run** button on that row
3. Only that TC runs; results appear in the row

!!! info "Test isolation"
    Tests run in an isolated Databricks schema (`bronze_test`) and use a separate job named `bronze_portal_{source}_test_{env}`. They do not touch your production Bronze tables.

---

## Understanding test results

After a run, each TC row shows:

| Field | Meaning |
|-------|---------|
| **Status** | Pass / Fail / Running / Not run |
| **Records loaded** | How many records were written to the test table |
| **Records quarantined** | How many records were quarantined (expected for TC005) |
| **Assertion result** | Whether the test's assertion SQL returned the expected result |
| **Error message** | If failed, the reason (e.g. wrong record count, SCD2 version mismatch) |

### What to do when a TC fails

1. Read the **error message** for the TC
2. Common causes:
    - **TC001/TC003 fail** — primary key or watermark column misconfigured
    - **TC004 fail** — `late_arriving_guard` not triggered — check the watermark column
    - **TC005 fail** — quality primary keys not set correctly in the source config
    - **TC006 fail** — `delete_condition_column` not configured
3. Fix the source config (click **Edit** on the source detail page)
4. Re-run the failing TC

---

## Downloading the test report

After all TCs have run, click **Download Report** to get an **HTML stakeholder report** with:

- Summary pass/fail count
- Colour-coded TC table
- Record counts and assertion results
- Timestamp and source details

This report is suitable for sharing with stakeholders or storing as evidence of pipeline validation.

---

## Creating a custom test case

The 8 standard TCs cover the most common pipeline scenarios. If you have a business-specific scenario to validate — e.g. a particular data transformation rule, a multi-record edge case, or a domain-specific quality check — you can add a custom test case in two ways.

=== "Using AI (recommended)"

    ### Generate a test case with AI

    The testing page has a built-in **AI Test Case Generator** panel at the bottom of every source suite page. You describe what you want to test in plain English — the AI handles everything else.

    #### Where to find it

    1. Go to **Testing → Bronze Tests** and click on your source
    2. Scroll to the bottom of the page — you will see the **"Generate a test case with AI"** panel with a sparkle icon
    3. It is always visible; no extra navigation needed

    #### What the AI does for you automatically

    Before generating anything, the AI silently reads your source's context:

    | What AI reads | Where it reads from | Why |
    |--------------|--------------------|----|
    | Column names and data types | Existing test data files for this source | So generated records match your actual schema |
    | Primary key columns | Source YAML config + suite definition | So records have unique, non-null PKs |
    | Existing TC IDs (TC001–TC008) | Suite YAML | So the new TC gets the correct next ID (e.g. TC009) automatically |
    | Target test table name | Suite definition | So assertion SQL queries the right table |
    | Catalog and schema | Suite definition | So SQL paths are exactly right (`dev.bronze_test.your_table`) |

    You never need to specify any of this. Just describe the business rule.

    #### Step 1 — Describe what you want to test

    Type a plain-English description of your test scenario in the text box. Be specific about the business rule:

    **Good prompts:**

    > *"Make sure that if two records arrive with the same order_id in the same batch, only one gets loaded and the duplicate is handled correctly."*

    > *"Test that a record with a null customer_id is quarantined to the dead letter table."*

    > *"Verify that updating the status field from 'pending' to 'active' creates a new SCD2 version while closing the old one."*

    > *"Check that the pipeline correctly handles 5 new records followed by an update to one of them in a second run."*

    Press **Generate TC** (or `Ctrl+Enter` to submit).

    #### Step 2 — Review the AI preview

    The AI responds with a structured preview card showing everything it generated:

    | Preview field | What it shows |
    |--------------|--------------|
    | **TC ID** | Auto-assigned next sequential ID (e.g. `TC009`) |
    | **Category** | What kind of test this is (e.g. `data quality`, `duplicate`, `null pk`, `update`) |
    | **Type** | Positive (valid data should pass) or Negative (bad data should be rejected) |
    | **Name** | A concise test case title |
    | **Explanation** | 2–3 sentences describing what the TC tests and why the test data was chosen |
    | **Assertions** | 1–3 SQL checks with type (`row_count`, `scalar_equals`) and expected value |
    | **Test data** | Collapsible section — click to expand and see the 3–8 NDJSON records the AI generated |

    !!! tip "Not happy with the preview?"
        Click **Try again** to discard and regenerate. You can also refine your prompt — add more detail about the specific constraint or edge case you want to cover.

    #### Step 3 — Add & Run

    When the preview looks correct, click **Add & Run**. The portal will:

    1. Write the generated NDJSON records to `portal/testing/data/{source}/tc009_*.json`
    2. Append the TC definition to `portal/testing/suites/{source}.yaml`
    3. **Immediately run the new TC on Databricks** — no manual trigger needed
    4. Show the live result (PASSED / FAILED) inline in the same panel

    The new TC also **instantly appears in the suite table** above — you do not need to refresh.

    !!! success "Time saved vs. manual approach"
        | Step | Manual | With AI |
        |------|--------|---------|
        | Design the test scenario | Done by you | Done by you (just describe it) |
        | Write NDJSON test data records | 15–30 min | Automatic |
        | Write assertion SQL | 15–30 min | Automatic |
        | Add to suite YAML | 10 min | Automatic |
        | Run the TC | Manual trigger | Automatic (runs immediately on confirm) |
        | **Total** | **~1 hour** | **~2 minutes** |

=== "Manually (advanced)"

    ### Create a test case by hand

    Use this approach when you need full control — for example, when the test requires a complex multi-step setup, a specific file pattern, or assertion logic the AI cannot easily express.

    #### What a test case is made of

    Each TC has three parts stored on disk:

    | Part | What it is | Location |
    |------|-----------|----------|
    | **Suite YAML entry** | TC definition: name, category, data file reference, assertion SQL | `portal/testing/suites/{source_name}.yaml` |
    | **Test data file** | NDJSON — one JSON record per line, matching your source schema | `portal/testing/data/{source_name}/tc00N_{description}.json` |
    | **Assertion SQL** | Embedded in the suite YAML — queries the test table after the pipeline runs | Inline in YAML |

    #### Step 1 — Create the test data file

    Create an NDJSON file at `portal/testing/data/{source_name}/tc009_my_scenario.json`. Each line is one record using your source's actual column names:

    ```json
    {"order_id": "ORD-001", "customer_id": "C001", "amount": 99.99, "updated_at": "2024-01-15 10:00:00"}
    {"order_id": "ORD-002", "customer_id": "C002", "amount": 149.00, "updated_at": "2024-01-15 11:00:00"}
    ```

    !!! tip "Naming convention"
        Use `tc00N_{short_slug}.json` — e.g. `tc009_duplicate_keys.json`, `tc010_null_status.json`.

    #### Step 2 — Add the entry to the suite YAML

    Open `portal/testing/suites/{source_name}.yaml` and append a new entry under `test_cases`:

    ```yaml
    - id: TC009
      name: "Custom — duplicate key in one batch"
      category: duplicate
      positive: false
      data_file: tc009_duplicate_keys.json
      setup_data_file: null        # optional: run this baseline file first (TC004 pattern)
      setup:
        - truncate_test_table
      teardown: []
      assertions:
        - type: row_count
          sql: "SELECT COUNT(*) FROM dev.bronze_test.{table_name} WHERE _is_current = true"
          expected: 1
          description: "Only one record survives deduplication"
    ```

    **Category values:** `insert` / `update` / `delete` / `late_arriving` / `null_pk` / `duplicate` / `idempotency` / `data_quality` / `audit`

    **Assertion types:**

    | Type | What it checks |
    |------|---------------|
    | `row_count` | `COUNT(*) = expected` |
    | `row_count_gte` | `COUNT(*) >= expected` |
    | `scalar_equals` | A single scalar value equals expected |

    #### Step 3 — Run the TC

    Go to **Testing → Bronze Tests → {your source}**, find your new TC in the table, and click the **Run** button on that row.

    !!! info "Portal detects new TCs automatically"
        The suite table reads directly from the YAML file — new entries appear immediately without restarting anything.

---

## Traditional approach (without the portal)

!!! success "Time saved: ~1–2 days per source"

    Without the portal, setting up Bronze pipeline tests required:

    1. Writing pytest test cases (~4 hrs)
    2. Creating mock or real test data files (~2 hrs)
    3. Setting up Databricks test infrastructure (test schema, test job, teardown logic) (~3 hrs)
    4. Running tests manually and interpreting results from Databricks logs (~1 hr)
    5. Writing a test report for stakeholders (~1 hr)

    **With the portal:** The test suite is auto-generated when you create a source. Click Run All → download the HTML report. **~30 minutes.**

---

## Related pages

- [Create a source](create-source.md) — test suites are auto-generated on source creation
- [Data quality rules](quality.md) — TC005 validates your quarantine configuration
- [Deploy](deploy.md) — deploy the latest config before re-running tests after a fix
