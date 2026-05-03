# Architecture Page

The Architecture page provides a visual overview of the Medallion Architecture — how data flows from raw source systems through Bronze and Silver layers to the Gold analytics layer.

---

## Navigating to the Architecture page

In the sidebar, click **Platform → Architecture** (or navigate to `/architecture`).

---

## Two views

The Architecture page has two tabs:

=== "Animated Flow"

    An **interactive SVG diagram** showing:

    - Source systems (left column): CSV files, databases, APIs, Kafka streams
    - **Bronze layer** (middle-left): raw ingestion tables with SCD2 tracking
    - **Silver layer** (middle-right): canonical business entities with multi-source merge
    - **Gold layer** (right): analytics-ready star schema tables (coming in v2.0)

    Animated flowing dots show **data moving** between the layers in real time, making it easy to explain the architecture to stakeholders.

    **Layers are colour-coded:**
    - Bronze: rust/orange (`#D97757`)
    - Silver: steel blue (`#8FA8C0`)
    - Gold: gold (`#C4A43B`)

=== "GIF Overview"

    A detailed animated GIF showing the full Medallion Architecture breakdown — Delta Tables at each layer, Unity Catalog organisation, SCD2 history, and the relationship between layers.

    Use this tab for:
    - Demo presentations
    - Onboarding new team members
    - Stakeholder overviews

---

## When to use the Architecture page

| Audience | Recommended tab |
|----------|----------------|
| New data engineers joining the team | GIF Overview — see the full picture quickly |
| Stakeholders / management | Animated Flow — easy to follow in a presentation |
| Architects reviewing the data model | Both — animated flow for structure, GIF for detail |
| Demos and sales | Animated Flow — visually impressive |

---

## Related pages

- [Architecture Overview](../overview.md) — written explanation of Medallion Architecture
- [Bronze Layer Overview](../bronze/index.md)
- [Silver Layer Overview](../silver/index.md)
