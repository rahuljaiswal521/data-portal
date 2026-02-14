# RAG Architecture — Bronze Framework Portal

## Overview

The Bronze Framework Portal includes an AI Assistant powered by **Retrieval-Augmented Generation (RAG)** — a pattern where user questions are answered by first retrieving relevant context from a knowledge base, then passing that context to a Large Language Model (LLM) to generate grounded, accurate responses.

This document explains the architecture chosen, the alternatives considered, and the rationale behind each decision.

---

## Architecture: Corrective-Style Simple RAG with Tenant Isolation

We use a **Simple RAG** pipeline with **tenant-scoped vector stores** and a **hybrid retrieval** strategy that combines vector search (for static documentation and configs) with live SQL queries (for operational data).

### Pipeline Flow

```
User Question
     │
     ▼
┌─────────────────┐
│ Query Classifier │  ← Keyword scoring: operational / config / docs / general
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│              Context Retrieval                   │
│                                                  │
│  ┌──────────────┐    ┌────────────────────────┐  │
│  │  ChromaDB     │    │  Live Data (SQL)       │  │
│  │  Vector Search│    │  - AuditService        │  │
│  │  - shared_docs│    │  - Run history         │  │
│  │  - tenant_src │    │  - Record counts       │  │
│  └──────┬───────┘    └──────────┬─────────────┘  │
│         └──────────┬────────────┘                 │
└────────────────────┼─────────────────────────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │  Prompt Assembly     │
          │  - System prompt     │
          │  - Chat history      │
          │  - Retrieved context │
          │  - User question     │
          └──────────┬──────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │  Claude Sonnet API   │
          │  (Generation)        │
          └──────────┬──────────┘
                     │
                     ▼
              Answer + Sources
```

---

## RAG Approaches Considered

We evaluated multiple RAG architectures before selecting our approach:

| Architecture | Description | Verdict |
|-------------|-------------|---------|
| **Simple RAG** | Retrieve → Generate | **Selected for Phase 1** — minimal complexity, fast to ship |
| **Corrective RAG (CRAG)** | Adds a validation step that scores retrieved docs for relevance before generation | Planned for Phase 2 |
| **Agentic RAG** | LLM decides which tools/sources to query dynamically | Over-engineered for current needs |
| **Graph RAG** | Uses knowledge graphs for entity relationships and data lineage | Planned for Phase 3 |
| **Text-to-SQL RAG** | Converts natural language to SQL for live queries | Planned for Phase 2 |
| **Adaptive RAG** | Dynamically chooses between retrieval strategies | Too complex for MVP |
| **Self-RAG** | LLM self-reflects on whether retrieval is needed | Adds latency, marginal benefit here |

### Why Simple RAG First

1. **Bounded domain** — Our knowledge base is small and well-defined (framework docs + YAML configs + audit logs). We don't need sophisticated retrieval strategies for ~30 document chunks.
2. **Fast time-to-value** — A working assistant now is more valuable than a perfect one later.
3. **Clear upgrade path** — The architecture is designed so Corrective RAG validation and Text-to-SQL can be layered on without rewriting the core pipeline.

---

## Multi-Tenant Data Isolation

Data safety is critical — the portal is designed to be sold to multiple organizations. We use a **store-per-tenant** isolation model.

### Isolation Model

```
ChromaDB Collections
├── shared_docs              ← Framework docs, shared by ALL tenants (read-only)
├── tenant_default_sources   ← Source configs for "default" tenant
├── tenant_acme_sources      ← Source configs for "acme" tenant
└── tenant_contoso_sources   ← Source configs for "contoso" tenant
```

- **Shared collection** (`shared_docs`): Framework documentation, enum references, how-to guides. Same for every tenant — indexed once.
- **Tenant collections** (`tenant_{id}_sources`): Per-tenant source YAML configs and summaries. Each tenant only sees their own sources in search results.

### Why Store-Per-Tenant (vs. Row-Level Filtering)

| Approach | Pros | Cons |
|----------|------|------|
| **Row-level filtering** | Simple, single collection | Risk of data leakage via filter bugs; harder to audit; slower queries on large shared index |
| **Store-per-tenant** (chosen) | Complete isolation; easy to audit; can delete tenant data cleanly; independent scaling | More collections to manage |

For a multi-org product where data safety is a selling point, physical isolation is the right default. The overhead of extra collections is negligible at our scale.

### Authentication

- API key authentication via `X-API-Key` header
- Keys are generated as `bp_{random_token}`, stored as SHA-256 hashes in SQLite
- For local development: `rag_require_auth=False` uses a default tenant automatically
- For production: set `RAG_REQUIRE_AUTH=True` — all requests must include a valid API key

---

## Knowledge Base & Indexing

### What Gets Indexed

| Content | Collection | Chunking Strategy | Purpose |
|---------|-----------|-------------------|---------|
| `CLAUDE.md` (framework architecture) | `shared_docs` | Split by `## ` headings, max ~1000 chars | Architecture questions |
| `how_to_add_new_source.md` | `shared_docs` | Split by `## ` headings | How-to questions |
| Enum/config reference | `shared_docs` | Single chunk | "What CDC modes exist?" type questions |
| Source YAML (raw) | `tenant_{id}_sources` | One chunk per source | Exact config lookups |
| Source summary (natural language) | `tenant_{id}_sources` | One chunk per source | Semantic search ("which source handles payments?") |

### Embedding Model

**`all-MiniLM-L6-v2`** from sentence-transformers:
- Runs locally — no external API calls, no cost per embedding
- 384-dimensional vectors, ~90MB model
- Good quality for short text chunks (our use case)
- MIT licensed

### Vector Database

**ChromaDB** (persistent mode):
- Stores vectors on disk at `portal/backend/data/chromadb/`
- Cosine similarity search
- No external infrastructure required
- Suitable for the current scale (tens to low hundreds of chunks)

---

## Query Classification

Before retrieval, queries are classified to determine what additional context to fetch:

| Type | Keywords | Additional Context |
|------|----------|-------------------|
| `operational` | "run", "failed", "records", "error", "dead letter", "when was" | Live audit data via AuditService SQL queries |
| `config` | "source", "configured", "yaml", "table", "cdc", "primary key" | Source list summary from ConfigService |
| `docs` | "how do i", "what is", "explain", "adapter", "architecture" | Vector search only |
| `general` | (no keyword match) | Vector search only |

This is intentionally simple keyword scoring. It works well for our domain because the vocabulary is distinct across categories. A future improvement could use the LLM itself for classification.

---

## Hybrid Retrieval Strategy

The assistant uses two complementary retrieval methods:

### 1. Vector Search (All Query Types)
- Searches both `shared_docs` and `tenant_{id}_sources` collections
- Returns top 5 results by cosine similarity
- Merges results from both collections, sorted by distance

### 2. Live Data Fetch (Operational Queries Only)
- Calls `AuditService.get_run_history()` for each configured source (up to 5)
- Returns real-time run status, record counts, timestamps, errors
- This data is NOT embedded — it's fetched fresh every query

### Why Hybrid?

Operational data (run history, record counts) changes constantly. Embedding it would mean stale answers. By fetching it live at query time, the assistant always has current data for "when was the last run?" or "how many records were ingested?" questions.

Static content (framework docs, YAML configs) changes rarely, making it ideal for vector search.

---

## Generation

### LLM

**Claude Sonnet** (`claude-sonnet-4-5-20250929`):
- Best balance of quality, speed, and cost for RAG responses
- ~$3/million input tokens, ~$15/million output tokens
- Configurable via `RAG_MODEL` environment variable

### System Prompt

The system prompt constrains the assistant to:
1. Answer ONLY from provided context — never hallucinate
2. Use exact source names and settings from configs
3. Cite specific numbers and timestamps for operational data
4. Format responses in Markdown
5. Never fabricate source names, configurations, or operational data

### Conversation History

- Last 10 messages from the session are included in the prompt
- Enables follow-up questions ("What about its primary keys?" after asking about a source)
- Stored in SQLite per tenant, per session

---

## Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Vector DB | ChromaDB (local, persistent) | Zero infrastructure, good enough for current scale |
| Embeddings | all-MiniLM-L6-v2 (local) | Free, fast, no API dependency |
| LLM | Claude Sonnet (API) | High quality generation, good cost/quality ratio |
| Tenant storage | SQLite | Built-in Python, no extra DB server needed |
| Chat history | SQLite (same DB) | Co-located with tenant data for simplicity |

---

## Configuration Reference

All settings in `portal/backend/.env`:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-api03-...

# Optional (defaults shown)
RAG_MODEL=claude-sonnet-4-5-20250929
RAG_MAX_TOKENS=1024
RAG_TEMPERATURE=0.3
RAG_REQUIRE_AUTH=false
CHROMADB_PERSIST_DIR=./data/chromadb
TENANT_DB_PATH=./data/tenants.db
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/rag/chat` | Send a question, get an answer |
| `GET` | `/api/v1/rag/chat/history?session_id=X` | Retrieve chat history for a session |
| `POST` | `/api/v1/rag/index/rebuild` | Rebuild the vector index |
| `GET` | `/api/v1/rag/index/status` | Get chunk counts |

---

## Future Phases

### Phase 2: Corrective RAG + Text-to-SQL
- Add a **relevance scoring** step that evaluates retrieved documents before passing them to the LLM
- If retrieved context scores below a threshold, trigger a fallback (web search or broader query)
- Add **Text-to-SQL** for operational queries — let the LLM write SQL against the audit log directly instead of pre-fetching fixed queries

### Phase 3: Graph RAG + Actions
- Build a **knowledge graph** of data lineage (source → table → downstream consumers)
- Enable **action capabilities** — "deploy this source", "trigger a run", "disable this pipeline" via the assistant
- Add **proactive alerts** — the assistant notices anomalies and suggests fixes

---

## File Structure

```
portal/backend/
├── app/
│   ├── api/
│   │   ├── common/
│   │   │   └── auth.py              # X-API-Key tenant authentication
│   │   └── rag/
│   │       ├── chat.py              # POST /rag/chat, GET /rag/chat/history
│   │       └── index.py             # POST /rag/index/rebuild, GET /rag/index/status
│   ├── models/
│   │   ├── rag.py                   # ChatRequest, ChatResponse, IndexStatus models
│   │   └── tenant.py               # TenantCreate, TenantInfo models
│   └── services/
│       ├── embedding_service.py     # ChromaDB + sentence-transformers
│       ├── rag_service.py           # Query classify → retrieve → generate
│       └── tenant_service.py        # SQLite tenant/API key/chat history
├── data/
│   ├── chromadb/                    # Vector store (auto-created)
│   └── tenants.db                   # Tenant + chat history DB (auto-created)

portal/frontend/
├── src/
│   ├── app/bronze/assistant/
│   │   └── page.tsx                 # AI Assistant page
│   ├── components/assistant/
│   │   ├── chat-container.tsx       # Full chat UI container
│   │   ├── chat-input.tsx           # Input with send button
│   │   ├── chat-message.tsx         # Message bubbles (user/assistant)
│   │   └── suggested-questions.tsx  # Empty state with 6 suggestions
│   └── hooks/
│       └── use-chat.ts              # Chat state management hook
```
