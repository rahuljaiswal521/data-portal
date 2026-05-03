# Entity Relationship Diagram

The Entity Diagram provides an interactive visual map of all Silver entities in the Lakehouse, their domains, and how they relate to each other.

---

## Navigating to the diagram

In the sidebar, click **Silver Layer → Model Diagram** (or navigate to `/silver/diagram`).

---

## What the diagram shows

The diagram renders a **force-directed graph** where:

- Each **node** = one Silver entity (e.g. `customer`, `policy`, `payment`)
- Node **colour** = domain (each domain gets a distinct colour)
- An **edge** (line) between two nodes = a foreign key relationship (e.g. `customer_interaction.customer_id → customer.customer_id`)
- Node **size** = proportional to the number of attributes in that entity

---

## Interacting with the diagram

| Action | How |
|--------|-----|
| **Pan** | Click and drag on the background |
| **Zoom** | Scroll wheel or pinch gesture |
| **Move a node** | Click and drag a node |
| **See entity details** | Hover over a node — shows entity name, domain, and attribute count |
| **Highlight relationships** | Click a node — highlights all connected edges |

---

## What to do with the diagram

- **Architecture review** — share the diagram with stakeholders to explain the data model
- **Before creating a new entity** — check if a similar entity or relationship already exists
- **Finding integration points** — identify which entities a new source should feed into
- **Onboarding new team members** — the visual map is much faster to understand than reading individual YAML files

---

## Traditional approach (without the portal)

!!! success "Time saved: ~2–4 hours per diagram refresh"

    Without the portal, creating an ER diagram required:

    1. Reading all Silver entity YAML files manually (~30 min)
    2. Extracting foreign key relationships from attribute names and documentation (~30–60 min)
    3. Drawing the diagram in Lucidchart, draw.io, or Visio (~1–2 hrs)
    4. Keeping it up to date as entities change (~ongoing maintenance)

    **With the portal:** The diagram auto-generates from live YAML configs. Every time you create or update an entity, the diagram reflects it immediately.

---

## Related pages

- [Create an Entity](create-entity.md)
- [AI Model Advisor](model-advisor.md) — the Enterprise Advisor suggests relationships visible in this diagram
- [Silver Overview](index.md)
