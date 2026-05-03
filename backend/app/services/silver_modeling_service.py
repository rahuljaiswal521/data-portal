"""Service for AI-assisted Silver entity modeling."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Generator, List, Optional

from app.config import settings
from app.services import ai_client_service
from app.models.silver_modeling import (
    ColumnInfo,
    ColumnProfileStats,
    DomainSuggestion,
    EntitySuggestion,
    EnterpriseModelResponse,
    SuggestedColumnMapping,
    SuggestedSource,
    SuggestedTarget,
    SuggestModelResponse,
    TableProfileResponse,
)
from app.services.databricks_service import DatabricksService

logger = logging.getLogger(__name__)

# ── Claude system prompt for Silver modeling ────────────────────────────

MODELING_SYSTEM_PROMPT = """\
You are a senior data engineer designing Silver-layer entity models for a Databricks lakehouse.

## Enterprise Modeling Rules

### Schema & Naming
- Silver schemas use the pattern: slv_<domain> (e.g., slv_customer, slv_policy)
- Tables use plain descriptive names in snake_case (e.g., customer_profile, policy_details)
- No dim_/fact_ prefixes in Silver — those are for Gold layer only
- Silver follows 3NF / Canonical Domain Entity pattern

### CRITICAL: Two Separate Temporal Concepts

You MUST distinguish these two completely different things:

1. FRAMEWORK SCD2 tracking columns — auto-generated, NEVER map them:
   _effective_from, _effective_to — track WHEN this row version existed in the warehouse.
   For standard SCD2: when the warehouse DETECTED a change (lags behind reality).
   For temporal_join: represents the INTERSECTED business validity window (see below).

2. SOURCE SYSTEM business temporal columns — these ARE real business data, MUST preserve:
   Patterns to recognise: start_date, end_date, effective_date, expiry_date,
   valid_from, valid_to, from_date, to_date, begin_date, close_date,
   commencement_date, termination_date, cover_from, cover_to.

   Canonical target column names:
     start_date / effective_date / valid_from / from_date  → business_effective_date
     end_date   / expiry_date    / valid_to   / to_date    → business_expiry_date

   If multiple sources each contribute their own date range with DIFFERENT meanings, prefix:
     member_package.start_date   → package_effective_date
     member_package.end_date     → package_expiry_date
     member_suspension.start_date → suspension_effective_date
     member_suspension.end_date   → suspension_expiry_date

### SCD Type Decision Rules

| Scenario | entity_type | scd_type |
|---|---|---|
| Single source, mutable attributes, no date range | standard | scd2 |
| Multi-source, SAME business key, attributes only (no independent date ranges) | standard | scd2 |
| 2+ sources, EACH with its OWN start_date/end_date for the SAME entity | temporal_join | scd2 |
| Immutable event / transaction tables | standard | append |

### Detecting temporal_join Candidates

A table is a VALIDITY-PERIOD table when it has ALL THREE of:
  (a) a business key (e.g., member_id, policy_id)
  (b) a start date column (start_date, effective_date, valid_from, from_date, begin_date …)
  (c) an end date column (end_date, expiry_date, valid_to, to_date, close_date …)

Rule: if you have 2 or more VALIDITY-PERIOD tables joined on the SAME business key
      → MUST use entity_type: temporal_join

Why this matters:
  member_package has its own start_date/end_date (when the package is active).
  member_suspension has its own start_date/end_date (when the suspension is active).
  These two windows are INDEPENDENT. A member can change package while suspended.
  A temporal_join stitches the timelines so the framework computes:
    _effective_from = start of each unique combined-state window
    _effective_to   = end of that window
  This is the ONLY way to correctly answer "what was the member's status on date D?"

### Configuring temporal_join — BOTH temporal AND column mappings required

For EACH source in a temporal_join entity:
  - temporal.start_column: the SOURCE column name holding the business start date
  - temporal.end_column:   the SOURCE column name holding the business end date
  - temporal.end_inclusive: true if the end date is inclusive (usually true for date ranges)
  - Also add the business date columns to the columns[] mapping with the prefixed target names

The temporal config drives the framework's stitching.
The column mappings preserve the source dates as queryable data attributes.

### For standard SCD2 with a single validity-period source

Map start_date → business_effective_date, end_date → business_expiry_date as data columns.
Add both to exclude_columns_from_hash — they define the record's scope, not its changing state.
The _effective_from/_effective_to remains the warehouse detection timeline (different from biz dates).

### Column Transforms
- Names (first, last, company): UPPER(TRIM({source}))
- Email addresses: LOWER(TRIM({source}))
- Date strings: TO_DATE({source}, 'yyyy-MM-dd') or appropriate format
- Phone numbers: REGEXP_REPLACE({source}, '[^0-9+]', '')
- Currency amounts: CAST({source} AS DECIMAL(18,2))
- Boolean flags: CAST({source} AS BOOLEAN)
- Only add transforms when they add value — simple pass-through columns need no transform

### Business Keys
- Must be unique, non-null columns that naturally identify the entity
- Examples: customer_id, policy_number, transaction_id
- Compound keys allowed: [policy_number, coverage_type]

### Multi-Source Priority
- priority 1 = highest priority (authoritative source)
- priority 2+ = supplementary sources
- The framework uses attribute-level survivorship: highest-priority non-null value wins

### System Columns (DO NOT include in mappings)
The framework auto-generates these — never map them:
_record_hash, _effective_from, _effective_to, _is_current, _source_system,
_ingested_at, _batch_id

### Watermark
- Default: column="_effective_from", type="timestamp"
- For temporal_join sources, you may also set watermark on the business start date column

### Columns to EXCLUDE from mappings
- Skip any column starting with _ (underscore) — Bronze SCD2 system columns
- Skip _metadata, _rescued_data
- Focus on business-meaningful columns only

## Response Format

### Standard SCD2 (no independent validity periods):
{
  "name": "entity_name",
  "domain": "domain_name",
  "description": "...",
  "entity_type": "standard",
  "sources": [
    {
      "bronze_table": "${catalog}.bronze.table_name",
      "priority": 1,
      "filter_condition": null,
      "watermark": {"column": "_effective_from", "type": "timestamp", "default_value": "2020-01-01T00:00:00"},
      "columns": [
        {"source": "src_col", "target": "tgt_col", "transform": null, "default_value": null, "reasoning": "why"}
      ],
      "temporal": null
    }
  ],
  "target": {
    "catalog": "${catalog}",
    "schema_name": "slv_domain",
    "table": "entity_name",
    "scd_type": "scd2",
    "business_keys": ["key_col"],
    "partition_by": [],
    "exclude_columns_from_hash": []
  },
  "reasoning": "...",
  "warnings": []
}

### Temporal Join (2+ sources with independent validity periods):
{
  "name": "member_entitlement",
  "domain": "member",
  "description": "Combined member package and suspension timeline using business validity dates",
  "entity_type": "temporal_join",
  "sources": [
    {
      "bronze_table": "${catalog}.bronze.member_package",
      "priority": 1,
      "filter_condition": null,
      "watermark": {"column": "start_date", "type": "date", "default_value": "2020-01-01"},
      "columns": [
        {"source": "member_id",    "target": "member_id",            "transform": null, "default_value": null, "reasoning": "Business key"},
        {"source": "package_code", "target": "package_code",         "transform": null, "default_value": null, "reasoning": "Package identifier"},
        {"source": "start_date",   "target": "package_effective_date","transform": "TO_DATE(start_date, 'yyyy-MM-dd')", "default_value": null, "reasoning": "Business start date preserved as data column"},
        {"source": "end_date",     "target": "package_expiry_date",  "transform": "TO_DATE(end_date, 'yyyy-MM-dd')",   "default_value": null, "reasoning": "Business end date preserved as data column"}
      ],
      "temporal": {
        "start_column": "start_date",
        "end_column": "end_date",
        "end_inclusive": true
      }
    },
    {
      "bronze_table": "${catalog}.bronze.member_suspension",
      "priority": 2,
      "filter_condition": null,
      "watermark": {"column": "start_date", "type": "date", "default_value": "2020-01-01"},
      "columns": [
        {"source": "member_id",     "target": "member_id",               "transform": null, "default_value": null, "reasoning": "Business key"},
        {"source": "suspense_code", "target": "suspension_code",          "transform": null, "default_value": null, "reasoning": "Suspension type"},
        {"source": "start_date",    "target": "suspension_effective_date","transform": "TO_DATE(start_date, 'yyyy-MM-dd')", "default_value": null, "reasoning": "Business suspension start preserved as data column"},
        {"source": "end_date",      "target": "suspension_expiry_date",   "transform": "TO_DATE(end_date, 'yyyy-MM-dd')",   "default_value": null, "reasoning": "Business suspension end preserved as data column"}
      ],
      "temporal": {
        "start_column": "start_date",
        "end_column": "end_date",
        "end_inclusive": true
      }
    }
  ],
  "target": {
    "catalog": "${catalog}",
    "schema_name": "slv_member",
    "table": "member_entitlement",
    "scd_type": "scd2",
    "business_keys": ["member_id"],
    "partition_by": [],
    "exclude_columns_from_hash": ["package_effective_date","package_expiry_date","suspension_effective_date","suspension_expiry_date"]
  },
  "reasoning": "member_package and member_suspension each have independent start_date/end_date validity windows for the same member_id. A temporal_join stitches these timelines so the framework creates one silver row per distinct combined-state window. The framework _effective_from/_effective_to will represent the intersected business validity period. Source business dates are also preserved as prefixed data columns (package_effective_date etc.) for direct querying without SCD2 traversal.",
  "warnings": ["Verify end_inclusive setting matches source system semantics — use true for date-only ranges, false for timestamp ranges"]
}

Respond ONLY with the JSON object. No markdown fencing, no explanation outside the JSON.
"""


ENTERPRISE_SYSTEM_PROMPT = """\
You are a senior data architect designing a Silver-layer data model for a Databricks lakehouse.

## Task
You will be given a list of Bronze table names.
Your job is to:
1. Group the tables into business domains (e.g., customer, policy, finance, member)
2. Within each domain, suggest 1 or more Silver entities
3. For each entity, identify: entity_type, scd_type, business keys, source tables, and reasoning
4. Do NOT suggest column mappings — only the entity structure

## Silver Layer Rules
- Silver schemas: slv_<domain> (e.g., slv_customer, slv_policy, slv_finance)
- No dim_/fact_ prefixes — plain snake_case names (customer_profile, policy_detail, payment_event)
- Business keys: stable, unique, non-null natural identifiers

## CRITICAL: Two Separate Temporal Concepts

Do NOT confuse these:

1. FRAMEWORK tracking dates (_effective_from, _effective_to):
   Auto-generated. Track WHEN the data warehouse knows about a version.
   NOT the same as business validity.

2. SOURCE SYSTEM business temporal columns:
   start_date, end_date, effective_date, expiry_date, valid_from, valid_to, etc.
   These represent WHEN an event/state is actually valid in the real world.
   They are DATA columns that must be preserved in Silver.

## Entity Type Decision Rules

| Scenario | entity_type | scd_type |
|---|---|---|
| Single source, mutable attributes | standard | scd2 |
| Multi-source, same business key, attributes only (no independent date ranges) | standard | scd2 |
| 2+ sources, EACH with its OWN start_date/end_date for the SAME business key | temporal_join | scd2 |
| Immutable events / transactions / logs | standard | append |

## Detecting temporal_join Candidates

A table is a VALIDITY-PERIOD table when its name/columns suggest it has:
  (a) a business key (member_id, policy_id, customer_id …)
  (b) a business start date (start_date, effective_date, valid_from, from_date, begin_date …)
  (c) a business end date (end_date, expiry_date, valid_to, to_date, close_date …)

Typical validity-period table name patterns:
  *_package, *_cover, *_entitlement, *_benefit, *_suspension, *_membership,
  *_enrollment, *_assignment, *_allocation, *_rate, *_tier

Rule: if 2 or more validity-period tables share the SAME business key → temporal_join.

Why: each source tracks an independent business timeline. Combining them with a standard
SCD2 merge would LOSE the independent validity windows. A temporal_join stitches the
timelines so each distinct combined-state window becomes one Silver row, with the
framework's _effective_from/_effective_to representing the INTERSECTED business period.

## Response Format

You MUST respond with valid JSON ONLY — no markdown, no explanation outside JSON:
{
  "domains": [
    {
      "domain": "member",
      "schema": "slv_member",
      "reasoning": "Why these tables belong together in this domain",
      "entities": [
        {
          "name": "member_profile",
          "description": "Core member attributes with SCD2 history",
          "entity_type": "standard",
          "scd_type": "scd2",
          "business_keys": ["member_id"],
          "source_tables": ["dev.bronze.members"],
          "reasoning": "Single source, mutable attributes — standard SCD2"
        },
        {
          "name": "member_entitlement",
          "description": "Combined member package and suspension timeline built from independent validity-period tables",
          "entity_type": "temporal_join",
          "scd_type": "scd2",
          "business_keys": ["member_id"],
          "source_tables": ["dev.bronze.member_package", "dev.bronze.member_suspension"],
          "reasoning": "Both tables are validity-period tables sharing member_id. member_package has start_date/end_date for when a package is active; member_suspension has start_date/end_date for when a suspension is active. These windows are independent — a member can change package while suspended. A temporal_join stitches the two timelines: _effective_from/_effective_to in Silver will represent the intersected business validity window. Source business dates are also preserved as prefixed data columns (package_effective_date, suspension_effective_date etc.)."
        }
      ]
    }
  ],
  "ungrouped_tables": [],
  "overall_reasoning": "2-4 sentences summarising the entire domain model and any temporal_join decisions"
}

Rules:
- ungrouped_tables: list any input tables that genuinely do not fit a domain
- overall_reasoning: mention any temporal_join entities and why they were chosen
- Respond ONLY with the JSON object. No markdown fencing, no text outside the JSON.
"""


class SilverModelingService:
    """Profiles Bronze tables and generates AI-powered Silver model suggestions."""

    def __init__(
        self,
        databricks_service: DatabricksService,
        tenant_service=None,
    ) -> None:
        self._databricks = databricks_service
        self._tenants = tenant_service

    def list_bronze_tables(self, catalog: str = "dev", schema: str = "bronze") -> List[Dict[str, Any]]:
        """Return available tables in the given catalog.schema."""
        return self._databricks.list_tables(catalog, schema)

    # Haiku is 3-5× faster than Sonnet and perfectly capable for domain grouping
    ENTERPRISE_MODEL = "claude-haiku-4-5-20251001"
    ENTERPRISE_MAX_TOKENS = 2000

    def _build_enterprise_message(self, tables: List[str], catalog: str) -> str:
        parts = ["Analyze these Bronze tables and design an enterprise Silver layer model.", ""]
        parts.append(f"Catalog: {catalog}")
        parts.append(f"Bronze tables to model ({len(tables)} total):")
        parts.append("")
        for tbl in tables:
            parts.append(f"  - {tbl}")
        parts.append("")
        parts.append(
            "Group these into business domains and suggest Silver entities per domain. "
            "Focus on entity structure (SCD type, business keys, source tables). "
            "Do NOT suggest column-level mappings."
        )
        return "\n".join(parts)

    def suggest_enterprise_model(
        self,
        tables: List[str],
        catalog: str = "dev",
        api_key: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> EnterpriseModelResponse:
        """Call the selected AI model to group Bronze tables into domains and suggest Silver entities."""
        user_message = self._build_enterprise_message(tables, catalog)

        try:
            # For Anthropic we stick with Haiku for speed; for other providers use the selected model.
            selected = ai_client_service.get_selected_model(self._tenants, tenant_id)
            model = self.ENTERPRISE_MODEL if ai_client_service.get_provider(selected) == "anthropic" else selected
            response = ai_client_service.create_message(
                system=ENTERPRISE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
                max_tokens=self.ENTERPRISE_MAX_TOKENS,
                model=model,
                temperature=0.2,
                tenant_service=self._tenants,
                tenant_id=tenant_id,
                api_key=api_key,
            )

            text = ""
            for block in response.content:
                if getattr(block, "type", None) == "text" and getattr(block, "text", None):
                    text += block.text

            return self._parse_enterprise_response(text)

        except ai_client_service.NoApiKeyError as e:
            return EnterpriseModelResponse(error=str(e))
        except Exception as e:
            logger.exception("Enterprise modeling call failed")
            return EnterpriseModelResponse(
                error=f"AI enterprise modeling failed: {str(e)}",
            )

    def suggest_enterprise_model_stream(
        self,
        tables: List[str],
        catalog: str = "dev",
        api_key: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """Stream raw text chunks for the enterprise model, then emit [DONE].

        Uses native streaming for Anthropic; OpenAI/Gemini fall back to a single
        emit via ai_client_service.stream_text().
        """
        user_message = self._build_enterprise_message(tables, catalog)

        try:
            selected = ai_client_service.get_selected_model(self._tenants, tenant_id)
            model = self.ENTERPRISE_MODEL if ai_client_service.get_provider(selected) == "anthropic" else selected
            for text in ai_client_service.stream_text(
                prompt=user_message,
                max_tokens=self.ENTERPRISE_MAX_TOKENS,
                system=ENTERPRISE_SYSTEM_PROMPT,
                model=model,
                temperature=0.2,
                tenant_service=self._tenants,
                tenant_id=tenant_id,
                api_key=api_key,
            ):
                yield f"data: {json.dumps({'chunk': text})}\n\n"
        except ai_client_service.NoApiKeyError as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        except Exception as e:
            logger.exception("Enterprise stream failed")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    def _parse_enterprise_response(self, text: str) -> EnterpriseModelResponse:
        """Parse Claude's JSON enterprise model response."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse enterprise Claude response: %s", e)
            return EnterpriseModelResponse(
                error=f"AI returned invalid JSON. Raw response: {text[:500]}",
            )

        domains = []
        for d in data.get("domains", []):
            entities = []
            for e in d.get("entities", []):
                entities.append(EntitySuggestion(
                    name=e.get("name", ""),
                    description=e.get("description", ""),
                    entity_type=e.get("entity_type", "standard"),
                    scd_type=e.get("scd_type", "scd2"),
                    business_keys=e.get("business_keys", []),
                    source_tables=e.get("source_tables", []),
                    reasoning=e.get("reasoning", ""),
                ))
            domains.append(DomainSuggestion(
                domain=d.get("domain", ""),
                schema=d.get("schema", f"slv_{d.get('domain', '')}"),
                reasoning=d.get("reasoning", ""),
                entities=entities,
            ))

        return EnterpriseModelResponse(
            domains=domains,
            ungrouped_tables=data.get("ungrouped_tables", []),
            overall_reasoning=data.get("overall_reasoning", ""),
        )

    def profile_table(self, catalog: str, schema: str, table: str) -> TableProfileResponse:
        """Profile a Bronze table — reuses the same logic as _execute_profile in silver_modeling_tools."""
        full_name = f"{catalog}.{schema}.{table}"

        if not self._databricks.available:
            return TableProfileResponse(
                table=full_name,
                error="Databricks connection is not available. Cannot profile table.",
            )

        try:
            # Get schema
            describe_rows = self._databricks.query_sql(f"DESCRIBE TABLE {full_name}")
            if not describe_rows:
                return TableProfileResponse(
                    table=full_name,
                    error=f"Table {full_name} not found or empty",
                )

            columns = []
            for row in describe_rows:
                col_name = row.get("col_name", "")
                if col_name and not col_name.startswith("#"):
                    columns.append(ColumnInfo(
                        name=col_name,
                        type=row.get("data_type", ""),
                        comment=row.get("comment"),
                    ))

            # Row count
            count_rows = self._databricks.query_sql(f"SELECT COUNT(*) as cnt FROM {full_name}")
            row_count = int(count_rows[0]["cnt"]) if count_rows else 0

            # Sample data (prefer current records for SCD2)
            has_is_current = any(c.name == "_is_current" for c in columns)
            sample_sql = f"SELECT * FROM {full_name}"
            if has_is_current:
                sample_sql += " WHERE _is_current = true"
            sample_sql += " LIMIT 100"
            sample_data = self._databricks.query_sql(sample_sql)

            # Basic profiling for non-system columns
            data_columns = [c.name for c in columns if not c.name.startswith("_")]
            profiling: List[ColumnProfileStats] = []
            if data_columns:
                profile_exprs = []
                for col_name in data_columns[:10]:
                    profile_exprs.append(
                        f"COUNT(DISTINCT `{col_name}`) as `{col_name}_distinct`"
                    )
                    profile_exprs.append(
                        f"SUM(CASE WHEN `{col_name}` IS NULL THEN 1 ELSE 0 END) as `{col_name}_nulls`"
                    )
                profile_sql = f"SELECT {', '.join(profile_exprs)} FROM {full_name}"
                if has_is_current:
                    profile_sql += " WHERE _is_current = true"
                profile_rows = self._databricks.query_sql(profile_sql)

                if profile_rows:
                    stats = profile_rows[0]
                    for col_name in data_columns[:10]:
                        profiling.append(ColumnProfileStats(
                            column=col_name,
                            distinct_count=stats.get(f"{col_name}_distinct", 0),
                            null_count=stats.get(f"{col_name}_nulls", 0),
                        ))

            return TableProfileResponse(
                table=full_name,
                row_count=row_count,
                columns=columns,
                profiling=profiling,
                sample_data=sample_data[:5] if sample_data else [],
                has_scd2_columns=has_is_current,
            )

        except Exception as e:
            return TableProfileResponse(
                table=full_name,
                error=f"Failed to profile {full_name}: {str(e)}",
            )

    def suggest_model(
        self,
        tables: List[Dict[str, Any]],
        profiles: Dict[str, TableProfileResponse],
        domain_hint: Optional[str] = None,
        entity_name_hint: Optional[str] = None,
        api_key: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> SuggestModelResponse:
        """Call the selected AI model to suggest a Silver entity model based on table profiles."""
        # Build user message with profile data
        user_message = self._build_user_message(
            tables, profiles, domain_hint, entity_name_hint
        )

        try:
            response = ai_client_service.create_message(
                system=MODELING_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
                max_tokens=3000,
                temperature=0.3,
                tenant_service=self._tenants,
                tenant_id=tenant_id,
                api_key=api_key,
            )

            # Extract text response
            text = ""
            for block in response.content:
                if getattr(block, "type", None) == "text" and getattr(block, "text", None):
                    text += block.text

            # Parse JSON
            return self._parse_suggestion(text)

        except ai_client_service.NoApiKeyError as e:
            return SuggestModelResponse(error=str(e))
        except Exception as e:
            logger.exception("Silver modeling call failed")
            return SuggestModelResponse(
                error=f"AI modeling failed: {str(e)}",
            )

    def _build_user_message(
        self,
        tables: List[Dict[str, Any]],
        profiles: Dict[str, TableProfileResponse],
        domain_hint: Optional[str],
        entity_name_hint: Optional[str],
    ) -> str:
        """Build the user prompt from profiles and optional definitions."""
        parts = []

        if domain_hint:
            parts.append(f"Domain: {domain_hint}")
        if entity_name_hint:
            parts.append(f"Suggested entity name: {entity_name_hint}")

        parts.append("")
        parts.append("Design a Silver entity model from the following Bronze table(s):")
        parts.append("")

        for tbl in tables:
            full_name = tbl["full_table_name"]
            defs = tbl.get("column_definitions")
            profile = profiles.get(full_name)

            parts.append(f"## Table: {full_name}")

            if profile and not profile.error:
                parts.append(f"Row count: {profile.row_count}")
                parts.append(f"Has SCD2 system columns: {profile.has_scd2_columns}")
                parts.append("")

                # Column info
                parts.append("Columns:")
                for col in profile.columns:
                    comment = f" -- {col.comment}" if col.comment else ""
                    parts.append(f"  - {col.name} ({col.type}){comment}")
                parts.append("")

                # Profiling stats
                if profile.profiling:
                    parts.append("Column stats (current records):")
                    for p in profile.profiling:
                        parts.append(
                            f"  - {p.column}: {p.distinct_count} distinct, {p.null_count} nulls"
                        )
                    parts.append("")

                # Sample data
                if profile.sample_data:
                    parts.append("Sample data (first 3 rows):")
                    for row in profile.sample_data[:3]:
                        # Filter out system columns for clarity
                        biz_data = {
                            k: v for k, v in row.items() if not k.startswith("_")
                        }
                        parts.append(f"  {json.dumps(biz_data, default=str)}")
                    parts.append("")

            elif profile and profile.error:
                parts.append(f"Profiling error: {profile.error}")
                parts.append("")

            if defs:
                parts.append("Column definitions provided by user:")
                parts.append(defs)
                parts.append("")
            elif not defs:
                parts.append(
                    "No column definitions provided — infer column meanings from names and types."
                )
                parts.append("")

        return "\n".join(parts)

    def _parse_suggestion(self, text: str) -> SuggestModelResponse:
        """Parse Claude's JSON response into a SuggestModelResponse."""
        # Strip markdown fencing if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last fence lines
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Claude response as JSON: %s", e)
            return SuggestModelResponse(
                error=f"AI returned invalid JSON. Raw response: {text[:500]}",
            )

        # Build typed response
        sources = []
        for s in data.get("sources", []):
            columns = [
                SuggestedColumnMapping(
                    source=c.get("source", ""),
                    target=c.get("target", ""),
                    transform=c.get("transform"),
                    default_value=c.get("default_value"),
                    reasoning=c.get("reasoning"),
                )
                for c in s.get("columns", [])
            ]
            sources.append(SuggestedSource(
                bronze_table=s.get("bronze_table", ""),
                priority=s.get("priority", 1),
                filter_condition=s.get("filter_condition"),
                watermark=s.get("watermark"),
                columns=columns,
                temporal=s.get("temporal"),
            ))

        target = None
        if data.get("target"):
            t = data["target"]
            target = SuggestedTarget(
                catalog=t.get("catalog", "${catalog}"),
                schema_name=t.get("schema_name", t.get("schema", "")),
                table=t.get("table", ""),
                scd_type=t.get("scd_type", "scd2"),
                business_keys=t.get("business_keys", []),
                partition_by=t.get("partition_by", []),
                exclude_columns_from_hash=t.get("exclude_columns_from_hash", []),
            )

        return SuggestModelResponse(
            name=data.get("name"),
            domain=data.get("domain"),
            description=data.get("description"),
            entity_type=data.get("entity_type", "standard"),
            sources=sources,
            target=target,
            reasoning=data.get("reasoning"),
            warnings=data.get("warnings", []),
        )
