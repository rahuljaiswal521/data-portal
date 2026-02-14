# CLAUDE.md

This file provides guidance to Claude Code when working with the Portal project.

## What This Is

A **self-service data ingestion portal** — a web UI + API that sits on top of the Bronze Framework (`../bronze_framework`). Users configure, deploy, and monitor data ingestion pipelines without writing code.

## Build & Run Commands

```bash
# Backend (FastAPI) — must use the .venv, not global Python
cd portal/backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# Frontend (Next.js 16)
cd portal/frontend
npm install
npm run dev          # Dev server on port 3000
npm run build        # Production build
npm run lint         # ESLint

# Tests (backend only — no tests exist yet)
# tests/ directory is empty
```

## Architecture Overview

```
portal/
├── backend/          FastAPI (Python)
│   ├── app/
│   │   ├── main.py              # App entry, CORS, lifespan
│   │   ├── config.py            # Pydantic BaseSettings (.env)
│   │   ├── dependencies.py      # @lru_cache DI singletons
│   │   ├── api/
│   │   │   ├── router.py        # Aggregates all sub-routers under /api/v1
│   │   │   ├── common/health.py # GET /health
│   │   │   └── bronze/
│   │   │       ├── sources.py   # CRUD: GET/POST/PUT/DELETE /bronze/sources
│   │   │       ├── deploy.py    # POST /bronze/sources/{name}/deploy|trigger
│   │   │       └── monitoring.py# GET /bronze/sources/{name}/runs|dead-letters, GET /bronze/stats
│   │   ├── models/
│   │   │   ├── enums.py         # SourceType, CdcMode, LoadType, etc.
│   │   │   ├── requests.py      # Deeply nested Pydantic models for source config
│   │   │   └── responses.py     # SourceSummary, SourceDetail, DashboardStats, etc.
│   │   ├── services/
│   │   │   ├── config_service.py    # YAML CRUD + Jinja2 rendering + validation
│   │   │   ├── git_service.py       # GitPython commit/delete
│   │   │   ├── databricks_service.py# SDK: upload, jobs, SQL queries
│   │   │   ├── audit_service.py     # SQL queries for run history & dead letters
│   │   │   └── deploy_service.py    # Orchestrator: validate → write → git → upload → job
│   │   └── templates/
│   │       └── source.yaml.j2       # Jinja2 template for YAML generation
│   ├── requirements.txt
│   └── .env                         # Databricks host/token/warehouse
│
└── frontend/         Next.js 16 + React 19 + TypeScript + Tailwind CSS
    └── src/
        ├── app/
        │   ├── page.tsx                 # Redirects / → /bronze
        │   ├── bronze/
        │   │   ├── layout.tsx           # Sidebar + Header + ToastProvider
        │   │   ├── page.tsx             # Dashboard: source list + stats cards
        │   │   ├── new/page.tsx         # 8-step form wizard to create source
        │   │   └── [name]/
        │   │       ├── page.tsx         # Source detail: 4 tabs (Config, YAML, Runs, Quality)
        │   │       └── edit/page.tsx    # Edit source form
        ├── components/
        │   ├── layout/                  # Sidebar, Header
        │   ├── ui/                      # Button, Input, Select, Toggle, Card, Badge, Tabs, Toast, etc.
        │   ├── forms/                   # FormWizard, DynamicList, KeyValueField, MetadataColumnsField, YamlPreview
        │   └── sources/                 # SourceTable (TanStack), StatsCards, StatusBadge
        ├── hooks/use-sources.ts         # SWR hooks: useSources, useSource, useDashboardStats, useRunHistory, useDeadLetters
        ├── types/index.ts               # TypeScript interfaces mirroring backend models
        └── lib/
            ├── api.ts                   # API client (fetch wrapper, all endpoints)
            ├── constants.ts             # Dropdown options for source types, CDC modes, etc.
            └── utils.ts                 # cn() — clsx + tailwind-merge
```

## API Endpoints

All under `/api/v1`:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| GET | `/environments` | List environment configs |
| GET | `/bronze/sources` | List sources (filter: source_type, domain, enabled) |
| POST | `/bronze/sources` | Create source |
| GET | `/bronze/sources/{name}` | Get source detail + raw YAML |
| PUT | `/bronze/sources/{name}` | Update source |
| DELETE | `/bronze/sources/{name}` | Delete source |
| POST | `/bronze/sources/{name}/validate` | Validate config |
| POST | `/bronze/sources/{name}/deploy` | Redeploy to Databricks |
| POST | `/bronze/sources/{name}/trigger` | Trigger Databricks job run |
| GET | `/bronze/sources/{name}/runs` | Run history from audit log |
| GET | `/bronze/sources/{name}/dead-letters` | Dead letter records |
| GET | `/bronze/stats` | Dashboard stats (totals, recent runs/failures) |

## Key Design Patterns

### Service Layer (Backend)

Five services with a dependency chain:
```
ConfigService (YAML CRUD, Jinja2 rendering, validation)
GitService (commit/delete files)
DatabricksService (upload, jobs, SQL)
AuditService (queries via DatabricksService)
DeployService (orchestrates Config + Git + Databricks)
```

**Dependency injection** via `dependencies.py` using `@lru_cache` for singletons.

**Orchestration flow** (create source):
```
validate → write YAML → git commit → upload to Databricks → create/update job
```

**Graceful degradation**: All services return None/empty on failure and log errors instead of throwing. Monitoring endpoints return empty data when Databricks is unavailable.

### Form Wizard (Frontend)

The create-source page (`/bronze/new`) is an **8-step wizard**:
1. General (name, type, description, enabled, tags)
2. Connection (JDBC/API connection details)
3. Extract (type-specific: query/path/url/kafka config)
4. Target (catalog, schema, table, partitioning)
5. CDC & Quality (mode, primary keys, dead letter config)
6. Metadata (injected columns like timestamps)
7. Review (YAML preview)
8. Submit

**State management**: Plain `useState` with `updateNested(path, value)` helper for deep updates. No react-hook-form in the wizard (despite being a dependency).

### Data Fetching (Frontend)

**SWR** for all GET requests — provides caching, revalidation, loading/error states. API client at `src/lib/api.ts` wraps fetch with base URL from `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000/api/v1`).

### YAML Generation

Jinja2 template (`source.yaml.j2`) renders source config with:
- Conditional sections based on source type (JDBC vs File vs API vs Stream)
- Smart defaults: only renders non-default values
- Boolean values lowercased (`{{ value | lower }}`)
- Nested optional structures (auth, pagination, watermark, CDC, landing)

### Validation

Two-phase validation in `ConfigService.validate_config()`:
1. **Basic + type-specific checks** (required fields per source type)
2. **Framework validation** — imports `ConfigLoader` from bronze_framework and calls `_parse_source()`

## Important Gotchas

1. **Schema alias**: `TargetRequest` uses `schema_name` field but YAML expects `schema`. The template uses `{{ target.schema_name }}` and `ConfigService._extract_nested()` handles the conversion.

2. **No authentication**: The API has no auth middleware — it's open. CORS restricts to localhost:3000/3001 and allianzis:3000/3001.

3. **No backend tests**: The `tests/` directory is empty.

4. **SQL injection risk**: `AuditService` constructs SQL with f-strings on `source_name` — no parameterized queries.

5. **Framework path injection**: `ConfigService` adds `bronze_framework/src` to `sys.path` at runtime for validation imports.

6. **Partial updates**: `SourceUpdateRequest` has all optional fields; `ConfigService.update_source()` merges with existing config and re-renders the full template.

7. **Git auto-push disabled**: `git_auto_push=false` in settings — commits are local only.

## Tech Stack

**Backend**: FastAPI, Pydantic v2, PyYAML, Jinja2, GitPython, Databricks SDK
**Frontend**: Next.js 16, React 19, TypeScript, Tailwind CSS 4, SWR, TanStack Table, Lucide icons
**Design**: Anthropic-inspired warm beige/cream palette with rust/burnt orange accent (#d97757)

## Configuration

Backend settings via `.env` at `portal/backend/.env`:
- `FRAMEWORK_ROOT` — path to bronze_framework
- `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_WAREHOUSE_ID` — Databricks connection
- `GIT_ENABLED`, `GIT_AUTO_PUSH` — Git integration
- `DEFAULT_ENVIRONMENT` — defaults to "dev"

Frontend env via `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000/api/v1`).
