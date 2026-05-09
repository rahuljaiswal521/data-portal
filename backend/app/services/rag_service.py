"""RAG orchestration: classify, retrieve context, generate answer."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

from app.config import settings
from app.services import ai_client_service
from app.services.audit_service import AuditService
from app.services.config_service import ConfigService
from app.services.deploy_service import DeployService
from app.services.embedding_service import EmbeddingService
from app.services.audit_tools import AUDIT_TOOLS, execute_audit_tool
from app.services.pipeline_tools import PIPELINE_TOOLS, execute_tool
from app.services.silver_config_service import SilverConfigService
from app.services.silver_deploy_service import SilverDeployService
from app.services.silver_modeling_tools import (
    SILVER_TOOLS,
    execute_silver_tool,
)
from app.services.tenant_service import TenantService

logger = logging.getLogger(__name__)


class QueryType:
    CONFIG = "config"
    OPERATIONAL = "operational"
    DOCS = "docs"
    GENERAL = "general"
    BUILD = "build"
    MODEL = "model"


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
they are coming soon and answer what you can from existing context.

Pipeline Building (when the user wants to CREATE a new Bronze source):
9. You have tools to preview and create bronze pipelines. When the user asks \
to create, build, set up, or onboard a new source, gather the essential info:
   - Source name (snake_case)
   - Source type (file, jdbc, api, stream)
   - Extract details (path for files, table/query for JDBC, base_url for API, kafka topic for streams)
   - Target catalog and table name
   - CDC mode (append, upsert, scd2) and primary keys if upsert/scd2
10. Use smart defaults — don't ask about every field. Assume schema "bronze", \
quality enabled, schema evolution "merge" unless the user says otherwise.
11. ALWAYS call preview_bronze_pipeline first so the user can review the YAML. \
Only call create_bronze_pipeline AFTER the user explicitly confirms.
12. If the user wants to change something after seeing the preview, adjust the \
parameters and preview again.

Silver Data Modeling (when the user wants to MODEL a Bronze table for Silver):
13. You have tools to profile Bronze tables, preview Silver entity configs, and \
deploy Silver entities. The Silver layer is the conformed, cleaned layer with \
domain-driven organization.
14. When a user wants to model a Bronze table for Silver:
   a. First call profile_bronze_table to understand the table's schema, stats, \
and sample data.
   b. Analyze the results and propose a Silver entity model:
      - Suggest a domain (customer, policy, payment, interaction, etc.)
      - Recommend SCD2 (for mutable data with history) or append (for events/logs)
      - Identify business keys (unique, non-null columns)
      - Map columns with appropriate transformations (UPPER/TRIM for names, \
LOWER for emails, TO_DATE for dates, etc.)
      - Use slv_<domain> schema naming (e.g. slv_customer, slv_policy)
   c. ALWAYS call preview_silver_model first so the user can review the YAML.
   d. Only call create_silver_entity AFTER the user explicitly confirms.
15. If the user doesn't have data definitions, use profiling data to infer types \
and suggest appropriate mappings. Mention any columns with high null rates or \
low cardinality.
16. For multi-source entities (same business key from multiple Bronze tables), \
set priority: 1 for the primary source and 2+ for secondary sources. Lower \
priority number wins for attribute-level survivorship.
17. Temporal Join entities (entity_type: "temporal_join"): Use when multiple SCD2 \
Bronze tables have independent validity periods (start_date/end_date) that don't \
align. Each source must have a temporal config with start_column, end_column, and \
end_inclusive (true for closed [start,end], false for half-open [start,end)). \
The framework stitches non-aligned intervals via breakpoint merge — it collects \
all boundary dates, creates micro-intervals, joins sources, and collapses \
consecutive identical intervals. Use temporal_join when the user mentions \
non-aligned dates, overlapping validity periods, temporal stitching, or combining \
tables with different effective date ranges. Set entity_type to "temporal_join" \
and add a temporal block to each source."""


class RAGService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        config_service: ConfigService,
        audit_service: AuditService,
        tenant_service: TenantService,
        deploy_service: DeployService,
        silver_config_service: SilverConfigService,
        silver_deploy_service: SilverDeployService,
    ) -> None:
        self._embeddings = embedding_service
        self._config = config_service
        self._audit = audit_service
        self._tenants = tenant_service
        self._deploy = deploy_service
        self._silver_config = silver_config_service
        self._silver_deploy = silver_deploy_service

    @property
    def available(self) -> bool:
        # Core AI is available as soon as *any* provider key is resolvable for
        # the default tenant (rag_service no longer owns a single SDK client).
        return settings.anthropic_api_key is not None

    def _has_key_for_tenant(self, tenant_id: str) -> bool:
        """True if the tenant has a key for their currently-selected provider."""
        model = ai_client_service.get_selected_model(self._tenants, tenant_id)
        provider = ai_client_service.get_provider(model)
        try:
            if provider == "anthropic":
                if self._tenants.get_anthropic_api_key(tenant_id):
                    return True
                return settings.anthropic_api_key is not None
            if provider == "openai":
                return self._tenants.get_openai_api_key(tenant_id) is not None
            if provider == "gemini":
                return self._tenants.get_gemini_api_key(tenant_id) is not None
        except Exception:
            pass
        return False

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
        build_keywords = [
            "create", "build", "set up", "setup", "new pipeline",
            "ingest", "onboard", "add source", "new source",
            "deploy a", "i want to ingest", "add a source",
            "create a pipeline", "build a pipeline",
        ]
        model_keywords = [
            "model", "profile", "analyze bronze", "silver entity",
            "data model", "normalize", "model for silver",
            "silver model", "design silver", "map to silver",
            "create silver", "build silver", "silver table",
            "canonical entity", "conformed", "business entity",
            "i want to model", "model a bronze",
            "temporal join", "temporal stitch", "non-aligned",
            "validity period", "overlapping dates",
        ]

        op_score = sum(1 for kw in operational_keywords if kw in q)
        cfg_score = sum(1 for kw in config_keywords if kw in q)
        doc_score = sum(1 for kw in docs_keywords if kw in q)
        build_score = sum(1 for kw in build_keywords if kw in q)
        model_score = sum(1 for kw in model_keywords if kw in q)

        scores = {
            QueryType.OPERATIONAL: op_score,
            QueryType.CONFIG: cfg_score,
            QueryType.DOCS: doc_score,
            QueryType.BUILD: build_score,
            QueryType.MODEL: model_score,
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

    def _get_silver_context(self) -> str:
        """Get Silver entity summary for context."""
        try:
            entities = self._silver_config.list_entities()
        except Exception:
            entities = []

        if not entities:
            return "No Silver entities are currently configured."

        lines = [f"Configured Silver entities ({len(entities)} total):"]
        domains: dict[str, list[str]] = {}
        for e in entities:
            domains.setdefault(e.domain, []).append(
                f"{e.name} (scd={e.scd_type}, sources={e.source_count}, enabled={e.enabled})"
            )

        for domain, entity_lines in sorted(domains.items()):
            lines.append(f"  Domain slv_{domain}:")
            for el in entity_lines:
                lines.append(f"    - {el}")

        return "\n".join(lines)

    # ── Answer Generation ──

    def answer(
        self,
        tenant_id: str,
        question: str,
        session_id: str,
        api_key: Optional[str] = None,
    ) -> dict:
        """Main entry point: classify, retrieve context, generate answer."""
        # The unified ai_client_service resolves keys internally.
        # We only short-circuit if the user has no key for their selected provider.
        if not api_key and not self._has_key_for_tenant(tenant_id):
            model = ai_client_service.get_selected_model(self._tenants, tenant_id)
            provider = ai_client_service.get_provider(model)
            return {
                "answer": (
                    f"The AI assistant is not configured. "
                    f"Please add a {provider.title()} API key in Settings, "
                    f"or choose a different model."
                ),
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

        # For model queries, add Silver entity context
        if query_type == QueryType.MODEL:
            silver_context = self._get_silver_context()
            if silver_context:
                context_parts.append(
                    f"\n=== Silver Entity Summary ===\n{silver_context}"
                )
                sources_used.append("silver_entities")

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

        # 4. Determine whether to include tools
        include_build_tools = (
            query_type == QueryType.BUILD
            or self._session_has_build_or_model_context(history, "build")
        )
        include_silver_tools = (
            query_type == QueryType.MODEL
            or self._session_has_build_or_model_context(history, "model")
        )
        include_audit_tools = query_type == QueryType.OPERATIONAL

        # 5. Call AI API (with tool loop if needed) via the multi-provider helper
        try:
            answer_text = self._call_with_tool_loop(
                messages, include_build_tools, include_silver_tools, include_audit_tools,
                tenant_id=tenant_id, api_key=api_key,
            )
        except ai_client_service.NoApiKeyError as e:
            answer_text = str(e)
        except Exception as e:
            logger.error("AI API call failed: %s", e)
            answer_text = f"I encountered an error generating a response: {e}"

        # 6. Save to chat history
        self._tenants.save_chat_message(tenant_id, "user", question, session_id)
        self._tenants.save_chat_message(
            tenant_id, "assistant", answer_text, session_id
        )

        if include_build_tools and "pipeline_tools" not in sources_used:
            sources_used.append("pipeline_tools")
        if include_silver_tools and "silver_modeling_tools" not in sources_used:
            sources_used.append("silver_modeling_tools")
        if include_audit_tools and "audit_log" not in sources_used:
            sources_used.append("audit_log")

        return {
            "answer": answer_text,
            "query_type": query_type,
            "sources_used": sources_used,
        }

    # ── Tool-Use Loop ──

    def _call_with_tool_loop(
        self,
        messages: list[dict],
        include_build_tools: bool,
        include_silver_tools: bool = False,
        include_audit_tools: bool = False,
        max_iterations: int = 5,
        tenant_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> str:
        """Call the selected AI provider, executing any tool_use blocks and looping back.

        Returns the final text response after all tools have been resolved.
        Dispatches through ai_client_service so Anthropic / OpenAI / Gemini all work.
        """
        tools = []
        if include_build_tools:
            tools.extend(PIPELINE_TOOLS)
        if include_silver_tools:
            tools.extend(SILVER_TOOLS)
        if include_audit_tools:
            tools.extend(AUDIT_TOOLS)

        has_tools = bool(tools)
        max_tokens = 2048 if has_tools else settings.rag_max_tokens

        # Build sets of known tool names for routing
        silver_tool_names = {t["name"] for t in SILVER_TOOLS}
        audit_tool_names = {t["name"] for t in AUDIT_TOOLS}

        for _ in range(max_iterations):
            response = ai_client_service.create_message(
                system=SYSTEM_PROMPT,
                messages=messages,
                max_tokens=max_tokens,
                tools=tools if tools else None,
                tenant_service=self._tenants,
                tenant_id=tenant_id,
                api_key=api_key,
            )

            # Check if there are any tool_use blocks
            tool_use_blocks = [
                block for block in response.content
                if block.type == "tool_use"
            ]

            if not tool_use_blocks:
                # Pure text response — extract and return
                text_parts = [
                    block.text for block in response.content
                    if block.type == "text" and block.text
                ]
                return "\n".join(text_parts) if text_parts else ""

            # There are tool calls — execute them and loop back.
            # Append the assistant's response in canonical (dict) form so the
            # messages list remains serialisable across providers.
            assistant_blocks: list[dict] = []
            for block in response.content:
                if block.type == "text" and block.text:
                    assistant_blocks.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_blocks.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input or {},
                    })
            messages.append({"role": "assistant", "content": assistant_blocks})

            # Execute each tool and build tool_result messages
            tool_results = []
            for tool_block in tool_use_blocks:
                if tool_block.name in audit_tool_names:
                    # Reuse the per-tenant DatabricksService already held by audit_service.
                    result = execute_audit_tool(
                        tool_block.name,
                        tool_block.input,
                        self._audit._db,
                    )
                elif tool_block.name in silver_tool_names:
                    result = execute_silver_tool(
                        tool_block.name,
                        tool_block.input,
                        self._silver_config,
                        self._silver_deploy,
                        self._audit._db,
                    )
                else:
                    result = execute_tool(
                        tool_block.name,
                        tool_block.input,
                        self._config,
                        self._deploy,
                    )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": json.dumps(result),
                })

            messages.append({"role": "user", "content": tool_results})

        # Hit max iterations — return whatever text we have
        logger.warning("Tool loop hit max iterations (%d)", max_iterations)
        return "I was unable to complete the request within the allowed steps. Please try again."

    def _session_has_build_or_model_context(
        self, history: list[dict], context_type: str = "build"
    ) -> bool:
        """Check if recent chat history contains build or model context.

        This ensures tools stay available on follow-up messages in a build/model
        conversation (e.g. user says "yes, deploy it" after seeing a preview).
        """
        build_indicators = [
            "preview_bronze_pipeline", "create_bronze_pipeline",
            "yaml_preview", "Should I deploy",
            "want to create", "want to ingest", "want to build",
            "new pipeline", "new source", "onboard",
            "yes, deploy", "go ahead", "looks good",
        ]
        model_indicators = [
            "profile_bronze_table", "preview_silver_model",
            "create_silver_entity", "silver entity",
            "silver model", "yaml_preview",
            "model for silver", "want to model",
            "yes, deploy", "go ahead", "looks good",
            "business key", "scd2", "slv_",
            "temporal_join", "temporal join", "temporal stitch",
        ]

        indicators = model_indicators if context_type == "model" else build_indicators

        # Check last 6 messages
        recent = history[-6:] if len(history) > 6 else history
        for msg in recent:
            content = msg.get("content", "")
            if isinstance(content, str):
                content_lower = content.lower()
                if any(ind.lower() in content_lower for ind in indicators):
                    return True
        return False

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
            "Silver Layer: Cleaned, conformed, and domain-organized canonical entities. "
            "Multi-source survivorship, SCD2/append, deduplication, standardization.\n"
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
            "SCD2 System Columns (Bronze): _effective_from (TIMESTAMP), "
            "_effective_to (TIMESTAMP, NULL=current), "
            "_is_current (BOOLEAN), _record_hash (STRING, MD5 of non-key cols), "
            "_cdc_operation (STRING: INSERT/UPDATE/DELETE)\n\n"
            "== Silver Layer Configuration ==\n\n"
            "Schema Naming: slv_<domain> (e.g. slv_customer, slv_policy, slv_payment)\n"
            "Cross-Domain: slv_xref (bridges & cross-references), "
            "slv_ref (reference/lookup tables), slv_meta (governance)\n\n"
            "SCD Types: scd2 (full history with _effective_from/_effective_to/_is_current), "
            "append (event/log data, no merge)\n\n"
            "Multi-Source Survivorship: Each source has a priority (1=highest). "
            "For overlapping business keys, lower priority number wins per attribute.\n\n"
            "Silver SCD2 System Columns: _effective_from, _effective_to, _is_current, "
            "_record_hash, _cdc_operation, _source_bronze_table, _loaded_at, _batch_id\n\n"
            "Silver Append System Columns: _source_bronze_table, _loaded_at, _batch_id\n\n"
            "Watermark: Configurable per source. Default: _effective_from for SCD2 Bronze, "
            "_ingest_timestamp for append-only Bronze. Enables incremental reads.\n\n"
            "Domains: customer, policy, payment, interaction — each a self-contained "
            "data product in its own slv_<domain> schema.\n\n"
            "Entity Types: standard (default, priority-based survivorship), "
            "temporal_join (breakpoint-based temporal merge for non-aligned SCD2 "
            "sources). Temporal join creates micro-intervals from all boundary dates, "
            "joins each source, and collapses consecutive identical intervals. Each "
            "source needs a temporal config: start_column, end_column, end_inclusive "
            "(true for closed [start,end], false for half-open [start,end))."
        )
