# Data Platform Portal — User Guide

Welcome to the **Data Platform Portal** — a self-service web application that lets data engineers and analysts configure, deploy, and monitor Medallion Architecture data pipelines **without writing a single line of infrastructure code**.

---

## What can I do with this portal?

The portal covers the full journey from raw data to analytics-ready tables:

| Capability | What you can do |
|-----------|----------------|
| **Bronze Layer** | Ingest raw data from files, databases, APIs, and streams. Configure SCD2 tracking, data quality rules, and deploy to Databricks in under 30 minutes. [→ Bronze overview](bronze/index.md) |
| **Silver Layer** | Model canonical business entities from multiple Bronze sources. Use AI-assisted schema design or configure manually. Full SCD2 multi-source merge. [→ Silver overview](silver/index.md) |
| **AI Assistant** | Describe a data source or entity in plain English — the AI configures the pipeline for you with no YAML knowledge required. [→ AI Assistant](platform/ai-assistant.md) |
| **Pipeline Monitoring** | View run history, record counts, failures, and data quality rejections for every pipeline in one dashboard. [→ Monitor pipelines](bronze/monitor.md) |
| **Pipeline Testing** | Run 8 automated test cases per source — or generate custom tests using AI in seconds. [→ Testing](bronze/testing.md) |
| **Authentication & User Management** | Username + password login with bcrypt-hashed credentials. Admins can onboard teammates with a single API call — no SSO plumbing required. [→ Authentication](platform/authentication.md) · [→ User management](platform/user-management.md) |
| **Architecture Diagram** | Animated flow diagram showing the full Bronze → Silver → Gold data journey. [→ Architecture](platform/architecture.md) |

---

## How much time does the portal save?

| What you want to do | Without the portal | With the portal |
|---------------------|--------------------|-----------------|
| Onboard a new data source | ~2 days | **~20 minutes** |
| Create a Silver entity schema | ~1 day | **~30 minutes** |
| Model a new domain with AI | ~4 hours | **~5 minutes** |
| Investigate a quality failure | ~30 minutes | **~10 seconds** |
| Set up a Bronze test suite | ~1.5 days | **~30 minutes** |
| Onboard 5 teammates to the portal | ~2 days (IT tickets, IdP setup) | **~1 minute** (one bash loop) |

---

## Quick start

!!! tip "First time here?"
    Start at [Getting Started](platform/getting-started.md) to learn how to log in and navigate the portal, then follow the path that matches your goal below.

**Path 1 — I want to ingest a new data source:**

1. [Understand the Bronze layer](bronze/index.md)
2. [Create a source](bronze/create-source.md) (or use the [AI Assistant](platform/ai-assistant.md))
3. [Deploy to Databricks](bronze/deploy.md)
4. [Monitor your pipeline](bronze/monitor.md)

**Path 2 — I want to model a canonical business entity:**

1. [Understand the Silver layer](silver/index.md)
2. [Use the AI Model Advisor](silver/model-advisor.md) to design your schema
3. [Create the entity](silver/create-entity.md)
4. [Deploy to Databricks](silver/deploy.md)

**Path 3 — I want to validate my pipeline logic:**

1. [Bronze pipeline testing](bronze/testing.md) — run 8 automated test cases

**Path 4 — I'm an admin and need to onboard the team:**

1. Confirm you can [log in](platform/authentication.md) as `admin`
2. Read [User Management](platform/user-management.md) — pick the API method or the CLI script
3. Hand each teammate their username and one-time password

---

## Portal at a glance

```
Landing Page (/)
    └── Get Started → Bronze Dashboard (/bronze)
            ├── Add Source (/bronze/new)          ← 8-step wizard
            ├── Source Detail (/bronze/{name})     ← Config, YAML, Runs, Quality
            └── Bronze Testing (/testing/bronze)   ← Automated test suites

Silver Dashboard (/silver)
    ├── New Entity (/silver/new)                   ← Entity wizard
    ├── Model Advisor (/silver/model-advisor)      ← AI schema design
    ├── Entity Detail (/silver/{name})
    └── Entity Diagram (/silver/diagram)           ← ER graph

Platform
    ├── Architecture (/architecture)               ← Animated flow diagram
    ├── AI Assistant (/bronze/assistant)           ← Chat pipeline builder
    ├── Login (/login)                             ← Username + password
    └── (admin REST) /api/v1/auth/admin/users      ← Create/reset users
```
