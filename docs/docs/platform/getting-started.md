# Getting Started

This page walks you through your first login, explains the portal's navigation, and helps you understand where everything lives.

---

## Accessing the portal

| Environment | URL |
|-------------|-----|
| Production (Azure) | `https://ecran-data-platform-ui.azurewebsites.net` |
| Local development | `http://localhost:3000` |

---

## Logging in

!!! warning "Authentication required"
    All portal pages require you to be logged in. If you visit any URL without a session, you will be automatically redirected to the login page.

1. Navigate to the portal URL above
2. You will be redirected to **`/login`** if you do not have an active session
3. Enter your **username** and **password** and click **Sign In**
4. You will be redirected back to the page you originally tried to visit (or to the Bronze Dashboard by default)

!!! info "Session persistence"
    Your API key is stored in `localStorage` and reused across browser tabs. You will not be asked to log in again until you sign out or the next successful login rotates your key.

For the full auth model (logout, profile dropdown, password storage, REST endpoints), see [Authentication](authentication.md). If you need to add or reset a teammate's account, see [User Management](user-management.md).

---

## The landing page

When you first visit `/`, you will see the **landing page** — a dark-screen overview of the portal with:

- An animated **Medallion Architecture GIF** showing the Bronze → Silver → Gold data flow
- A **Get Started** button that takes you to the Bronze Dashboard
- A summary of all three layers at the bottom

This page is designed for demos and onboarding. If you are already familiar with the portal, click **Get Started** to go straight to work.

---

## Navigation

The portal uses a **fixed left sidebar** that is visible on all pages once you enter the application.

```
Sidebar sections:
┌────────────────────────┐
│  Data Portal           │
│  Lakehouse Platform    │
├────────────────────────┤
│  BRONZE LAYER          │
│    Dashboard           │  ← /bronze
│    Add Source          │  ← /bronze/new
├────────────────────────┤
│  SILVER LAYER          │
│    Dashboard           │  ← /silver
│    Model Advisor       │  ← /silver/model-advisor
│    New Entity          │  ← /silver/new
│    Model Diagram       │  ← /silver/diagram
├────────────────────────┤
│  TESTING               │
│    Bronze Tests        │  ← /testing/bronze
│    Silver Tests        │  (coming soon)
├────────────────────────┤
│  COMING SOON           │
│    Gold Layer          │  (planned v2.0)
├────────────────────────┤
│  PLATFORM              │
│    Architecture        │  ← /architecture
│    AI Assistant        │  ← /bronze/assistant
├────────────────────────┤
│  Settings              │
└────────────────────────┘
```

The **active page** is highlighted in orange in the sidebar.

---

## The header

At the top of every page you will find:

- **Page title** — the name of the current section
- **Connection status** — a status indicator showing whether the Databricks backend is reachable
- **Action buttons** — context-sensitive buttons (e.g. "Add Source" on the Bronze dashboard)
- **Avatar badge** (top-right) — a circular accent badge showing the first letter of your display name. Click it for a dropdown showing your full display name, role, and a **Sign out** button.

---

## Key concepts before you start

| Term | Meaning |
|------|---------|
| **Source** | A Bronze-layer data pipeline configuration. One source = one raw table in Databricks. |
| **Entity** | A Silver-layer canonical business object (e.g. Customer, Policy, Payment). |
| **Deploy** | The act of uploading your config to Databricks and creating/updating a job. |
| **Trigger** | Manually starting a pipeline run immediately. |
| **SCD2** | Slowly Changing Dimension Type 2 — every historical version of a record is kept. |
| **Dead letter** | A record that was rejected by a data quality rule; stored separately for inspection. |
| **YAML** | The configuration file format used by the Bronze and Silver frameworks. The portal generates these for you. |

---

## Recommended first steps

If you are new to the portal, follow this sequence:

1. Read [Architecture Overview](../overview.md) to understand the Bronze → Silver → Gold model
2. Go to the [Bronze Dashboard](../bronze/index.md) to see existing sources
3. Try [creating a new source](../bronze/create-source.md) using the 8-step wizard
4. Explore the [AI Assistant](ai-assistant.md) to see how to build a pipeline from a plain English description
