"""RAG orchestration: classify, retrieve context, generate answer."""

import hashlib
import logging
from pathlib import Path
from typing import Optional

import anthropic

from app.config import settings
from app.services.audit_service import AuditService
from app.services.config_service import ConfigService
from app.services.embedding_service import EmbeddingService
from app.services.tenant_service import TenantService

logger = logging.getLogger(__name__)


class QueryType:
    CONFIG = "config"
    OPERATIONAL = "operational"
    DOCS = "docs"
    GENERAL = "general"


SYSTEM_PROMPT = """\
You are the Data Platform Assistant, an AI helper for a metadata-driven \
data lakehouse built on the medallion architecture (Bronze, Silver, Gold).

You help users understand:

Bronze Layer (Raw Ingestion):
- Source configurations (YAML files that define data ingestion pipelines)
- Pipeline behavior (SCD2, CDC modes, schema evolution, quality checks)
- Operational data (run history, record counts, errors, dead letters)

Silver Layer (Cleaned & Conformed):
- Transformation rules, data quality validations, business logic
- Deduplication, standardization, enrichment joins
- Silver table lineage back to Bronze sources

Gold Layer (Curated & Aggregated):
- Star schemas, dimension/fact tables, KPI definitions
- Aggregation schedules, materialized views
- Reporting datasets and downstream consumers

General:
- Framework documentation (how to add sources, available adapters, architecture)
- Cross-layer data lineage and pipeline orchestration

Rules:
1. Answer based ONLY on the provided context. If the context doesn't contain \
the answer, say so clearly.
2. When referencing source configs, use the exact source names and settings.
3. For operational questions, cite specific numbers and timestamps from the data.
4. Keep answers concise and actionable.
5. If a question is about something outside this data platform, politely redirect.
6. Format responses in Markdown when helpful (tables, code blocks, bullet points).
7. NEVER fabricate source names, configurations, or operational data.
8. If Silver or Gold layer features are not yet available, let the user know \
they are coming soon and answer what you can from existing context."""


class RAGService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        config_service: ConfigService,
        audit_service: AuditService,
        tenant_service: TenantService,
    ) -> None:
        self._embeddings = embedding_service
        self._config = config_service
        self._audit = audit_service
        self._tenants = tenant_service
        self._client: Optional[anthropic.Anthropic] = None
        if settings.anthropic_api_key:
            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    @property
    def available(self) -> bool:
        return self._client is not None

    # ── Query Classification ──

    def classify_query(self, question: str) -> str:
        """Simple keyword-based classification."""
        q = question.lower()

        operational_keywords = [
            "run", "last run", "history", "records", "ingested",
            "failed", "failure", "error", "dead letter", "quarantine",
            "status", "when was", "how many records", "successful",
            "refresh", "schedule",
        ]
        config_keywords = [
            "source", "configured", "yaml", "config", "connection",
            "table", "catalog", "schema", "cdc", "scd2", "primary key",
            "extract", "target", "enabled", "disabled",
            "how is", "what sources", "list sources",
            "transformation", "transform", "silver", "gold",
            "dimension", "fact", "star schema", "kpi", "aggregate",
        ]
        docs_keywords = [
            "how do i", "how to", "what is", "explain", "adapter",
            "architecture", "framework", "add a new", "documentation",
            "platform", "snowflake", "databricks", "watermark",
            "schema evolution", "quality threshold",
            "medallion", "bronze layer", "silver layer", "gold layer",
            "lineage", "end to end",
        ]

        op_score = sum(1 for kw in operational_keywords if kw in q)
        cfg_score = sum(1 for kw in config_keywords if kw in q)
        doc_score = sum(1 for kw in docs_keywords if kw in q)

        scores = {
            QueryType.OPERATIONAL: op_score,
            QueryType.CONFIG: cfg_score,
            QueryType.DOCS: doc_score,
        }
        max_score = max(scores.values())
        if max_score == 0:
            return QueryType.GENERAL

        return max(scores, key=scores.get)

    # ── Context Retrieval ──

    def _get_operational_context(self, tenant_id: str) -> str:
        """Fetch live operational data from AuditService."""
        context_parts = []

        sources = self._config.list_sources()
        if not sources:
            return "No sources are currently configured."

        context_parts.append(
            f"There are {len(sources)} configured sources: "
            + ", ".join(s.name for s in sources)
        )

        for source in sources[:5]:
            detail = self._config.get_source(source.name)
            if not detail:
                continue
            catalog = detail.target.get("catalog", "")
            if not catalog:
                continue

            try:
                runs = self._audit.get_run_history(source.name, catalog, limit=5)
            except Exception:
                runs = []

            if runs:
                context_parts.append(f"\nRecent runs for '{source.name}':")
                for run in runs:
                    line = (
                        f"  - {run.get('status', 'UNKNOWN')} at "
                        f"{run.get('start_time', 'N/A')}: "
                        f"read={run.get('records_read', 0)}, "
                        f"written={run.get('records_written', 0)}, "
                        f"quarantined={run.get('records_quarantined', 0)}"
                    )
                    if run.get("error"):
                        line += f", error={run['error']}"
                    context_parts.append(line)

        return "\n".join(context_parts)

    def _get_config_context(self, tenant_id: str) -> str:
        """Get source configuration summary."""
        sources = self._config.list_sources()
        if not sources:
            return "No sources are currently configured."

        lines = [f"Configured sources ({len(sources)} total):"]
        for s in sources:
            lines.append(
                f"  - {s.name}: type={s.source_type.value}, "
                f"table={s.target_table}, cdc={s.cdc_mode.value}, "
                f"load={s.load_type.value}, enabled={s.enabled}"
            )
        return "\n".join(lines)

    # ── Answer Generation ──

    def answer(
        self,
        tenant_id: str,
        question: str,
        session_id: str,
    ) -> dict:
        """Main entry point: classify, retrieve context, generate answer."""
        if not self.available:
            return {
                "answer": "The AI assistant is not configured. "
                "Please set ANTHROPIC_API_KEY in .env.",
                "query_type": "error",
                "sources_used": [],
            }

        # 1. Classify
        query_type = self.classify_query(question)

        # 2. Retrieve context
        context_parts = []
        sources_used = []

        # Always retrieve from vector store
        vector_results = self._embeddings.query_tenant_and_shared(
            tenant_id, question, n_results=5
        )
        if vector_results:
            context_parts.append("=== Retrieved Documentation & Config Context ===")
            for hit in vector_results:
                source_label = hit["metadata"].get("source", "unknown")
                context_parts.append(f"[Source: {source_label}]\n{hit['text']}\n")
                if source_label not in sources_used:
                    sources_used.append(source_label)

        # For operational queries, also fetch live data
        if query_type == QueryType.OPERATIONAL:
            op_context = self._get_operational_context(tenant_id)
            context_parts.append(f"\n=== Live Operational Data ===\n{op_context}")
            sources_used.append("live_audit_data")

        # For config queries, also add source list summary
        if query_type == QueryType.CONFIG:
            cfg_context = self._get_config_context(tenant_id)
            context_parts.append(
                f"\n=== Source Configuration Summary ===\n{cfg_context}"
            )
            sources_used.append("source_configs")

        full_context = (
            "\n\n".join(context_parts) if context_parts else "No relevant context found."
        )

        # 3. Build conversation history
        history = self._tenants.get_chat_history(tenant_id, session_id, limit=10)
        messages = []
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append(
            {
                "role": "user",
                "content": f"Context:\n{full_context}\n\nQuestion: {question}",
            }
        )

        # 4. Call Claude API
        try:
            response = self._client.messages.create(
                model=settings.rag_model,
                max_tokens=settings.rag_max_tokens,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
            answer_text = response.content[0].text
        except Exception as e:
            logger.error("Claude API call failed: %s", e)
            answer_text = f"I encountered an error generating a response: {e}"

        # 5. Save to chat history
        self._tenants.save_chat_message(tenant_id, "user", question, session_id)
        self._tenants.save_chat_message(
            tenant_id, "assistant", answer_text, session_id
        )

        return {
            "answer": answer_text,
            "query_type": query_type,
            "sources_used": sources_used,
        }

    # ── Indexing ──

    def build_index(self, tenant_id: str) -> dict:
        """Rebuild the full index for a tenant: shared docs + source YAMLs."""
        results = {"shared_docs": 0, "source_configs": 0}

        # 1. Index shared documentation
        doc_chunks = self._chunk_framework_docs()
        results["shared_docs"] = self._embeddings.index_shared_docs(doc_chunks)

        # 2. Index tenant source configs
        source_chunks = self._chunk_source_configs(tenant_id)
        self._embeddings.clear_tenant_sources(tenant_id)
        results["source_configs"] = self._embeddings.index_tenant_sources(
            tenant_id, source_chunks
        )

        logger.info(
            "Index rebuilt for tenant '%s': %d shared docs, %d source chunks",
            tenant_id,
            results["shared_docs"],
            results["source_configs"],
        )
        return results

    def _chunk_framework_docs(self) -> list[dict]:
        """Load and chunk framework documentation files."""
        chunks = []
        framework_root = Path(settings.framework_root)

        doc_files = [
            (framework_root / "CLAUDE.md", "framework_architecture"),
            (framework_root / "docs" / "how_to_add_new_source.md", "how_to_guide"),
        ]

        for file_path, source_label in doc_files:
            if not file_path.exists():
                continue
            text = file_path.read_text(encoding="utf-8")
            file_chunks = self._split_markdown(text, source_label, str(file_path))
            chunks.extend(file_chunks)

        # Embed the enum/model reference as a doc chunk
        enums_text = self._build_enum_doc()
        chunk_id = hashlib.md5("enums_reference".encode()).hexdigest()
        chunks.append(
            {
                "id": f"enums_{chunk_id}",
                "text": enums_text,
                "metadata": {"source": "config_reference", "type": "reference"},
            }
        )

        return chunks

    def _split_markdown(
        self, text: str, source_label: str, file_path: str
    ) -> list[dict]:
        """Split markdown by ## headings into chunks. Max ~1000 chars per chunk."""
        chunks = []
        sections = text.split("\n## ")

        for i, section in enumerate(sections):
            if i > 0:
                section = "## " + section

            if len(section) > 1200:
                paragraphs = section.split("\n\n")
                current_chunk = ""
                chunk_idx = 0
                for para in paragraphs:
                    if len(current_chunk) + len(para) > 1000 and current_chunk:
                        chunk_id = hashlib.md5(
                            f"{file_path}_{i}_{chunk_idx}".encode()
                        ).hexdigest()
                        chunks.append(
                            {
                                "id": f"{source_label}_{chunk_id}",
                                "text": current_chunk.strip(),
                                "metadata": {
                                    "source": source_label,
                                    "file": file_path,
                                    "type": "documentation",
                                },
                            }
                        )
                        current_chunk = para
                        chunk_idx += 1
                    else:
                        current_chunk += "\n\n" + para
                if current_chunk.strip():
                    chunk_id = hashlib.md5(
                        f"{file_path}_{i}_{chunk_idx}".encode()
                    ).hexdigest()
                    chunks.append(
                        {
                            "id": f"{source_label}_{chunk_id}",
                            "text": current_chunk.strip(),
                            "metadata": {
                                "source": source_label,
                                "file": file_path,
                                "type": "documentation",
                            },
                        }
                    )
            elif section.strip():
                chunk_id = hashlib.md5(f"{file_path}_{i}".encode()).hexdigest()
                chunks.append(
                    {
                        "id": f"{source_label}_{chunk_id}",
                        "text": section.strip(),
                        "metadata": {
                            "source": source_label,
                            "file": file_path,
                            "type": "documentation",
                        },
                    }
                )

        return chunks

    def _chunk_source_configs(self, tenant_id: str) -> list[dict]:
        """Load all YAML source configs and chunk them.

        Each source becomes 2 chunks: raw YAML + natural-language summary.
        """
        chunks = []
        sources = self._config.list_sources()

        for source_summary in sources:
            detail = self._config.get_source(source_summary.name)
            if not detail:
                continue

            # Chunk 1: Raw YAML (for exact config lookups)
            yaml_id = hashlib.md5(f"yaml_{detail.name}".encode()).hexdigest()
            chunks.append(
                {
                    "id": f"source_yaml_{yaml_id}",
                    "text": detail.raw_yaml,
                    "metadata": {
                        "source": f"source_config:{detail.name}",
                        "source_name": detail.name,
                        "type": "source_yaml",
                    },
                }
            )

            # Chunk 2: Natural-language summary (for semantic search)
            target = detail.target
            cdc = target.get("cdc", {})
            summary = (
                f"Source '{detail.name}' is a {detail.source_type.value} source. "
                f"Description: {detail.description or 'No description'}. "
                f"Enabled: {detail.enabled}. "
                f"Target table: {target.get('catalog', '')}"
                f".{target.get('schema', 'bronze')}"
                f".{target.get('table', '')}. "
                f"CDC mode: {cdc.get('mode', 'append')}. "
                f"Primary keys: {', '.join(cdc.get('primary_keys', []))}. "
                f"Load type: {detail.extract.get('load_type', 'full')}. "
                f"Tags: {detail.tags}."
            )
            summary_id = hashlib.md5(f"summary_{detail.name}".encode()).hexdigest()
            chunks.append(
                {
                    "id": f"source_summary_{summary_id}",
                    "text": summary,
                    "metadata": {
                        "source": f"source_config:{detail.name}",
                        "source_name": detail.name,
                        "type": "source_summary",
                    },
                }
            )

        return chunks

    def _build_enum_doc(self) -> str:
        """Build a reference doc chunk from the framework enums."""
        return (
            "Data Platform Configuration Reference:\n\n"
            "== Medallion Architecture ==\n"
            "Bronze Layer: Raw data ingestion from sources into Delta Lake tables. "
            "Handles CDC (change data capture), schema evolution, and data quality.\n"
            "Silver Layer: Cleaned, conformed, and enriched data. Applies business "
            "rules, deduplication, standardization, and enrichment joins. (Coming soon)\n"
            "Gold Layer: Curated, aggregated data for reporting. Star schemas, "
            "dimension/fact tables, KPIs, and materialized views. (Coming soon)\n\n"
            "== Bronze Layer Configuration ==\n\n"
            "Source Types: jdbc (database via JDBC driver), file (cloud storage files), "
            "api (REST API endpoint), stream (Kafka / Event Hub)\n\n"
            "CDC Modes: append (insert-only, no dedup), upsert (overwrite matched rows), "
            "scd2 (slowly changing dimension type 2 - full history tracking with "
            "_effective_from, _effective_to, _is_current, _record_hash, "
            "_cdc_operation columns)\n\n"
            "Load Types: full (complete reload every run), "
            "incremental (only new/changed records via watermark)\n\n"
            "Schema Evolution Modes: merge (auto-add new columns), "
            "strict (fail on schema change), "
            "rescue (store unknown fields in _rescued_data column)\n\n"
            "Auth Types: none, oauth2, api_key, bearer\n\n"
            "Pagination Types: offset, cursor, link_header\n\n"
            "Quality: quarantine_threshold_pct controls the maximum percentage "
            "of bad records before the pipeline fails. Dead letter records are "
            "written to a separate table.\n\n"
            "SCD2 System Columns: _effective_from (TIMESTAMP), "
            "_effective_to (TIMESTAMP, NULL=current), "
            "_is_current (BOOLEAN), _record_hash (STRING, MD5 of non-key cols), "
            "_cdc_operation (STRING: INSERT/UPDATE/DELETE)"
        )
