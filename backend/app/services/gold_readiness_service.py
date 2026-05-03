"""GoldReadinessService — gates the gold-mart build on bronze + silver readiness.

For each source referenced by the parsed gold IR (dim/fact `source_entity`), this
service verifies:

  1. Bronze sources mentioned by the dims/facts have YAML configs present
     (and, when Databricks is reachable, the target table actually exists).
  2. Silver entities mentioned have YAML configs present
     (and, when Databricks is reachable, the table is queryable).
  3. Every column referenced by the gold spec (dim attribute source columns,
     fact grain columns, fact watermark, fact FK source columns) actually
     exists on the resolved bronze/silver source — verified via
     `DESCRIBE TABLE` when Databricks is available.

Result returns:

  {
    "ready": bool,
    "summary": { ok / missing / warn counts per category },
    "sources":      [SourceCheck...],
    "column_issues": [ColumnIssue...],
    "errors":   [ ... blocking messages ],
    "warnings": [ ... non-blocking messages ]
  }

It deliberately surfaces *advice* (e.g. "build dim_customer in silver first")
rather than auto-building anything.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ── Result dataclasses ──────────────────────────────────────────────────────


@dataclass
class SourceCheck:
    """Per-source readiness verdict."""

    full_name: str                    # "dev.slv_sales.order_line"
    classified_layer: str             # "bronze" | "silver" | "unknown"
    yaml_present: bool
    table_reachable: Optional[bool]   # None when Databricks not configured
    referenced_by: List[str] = field(default_factory=list)  # ["dim_customer", "fact_orders"]
    error: Optional[str] = None       # blocking issue text
    warning: Optional[str] = None     # non-blocking issue text


@dataclass
class ColumnIssue:
    source_full_name: str
    referenced_by: str        # e.g. "dim_customer.country_code"
    missing_column: str
    available_columns: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)   # populated by AI step


@dataclass
class ReadinessReport:
    ready: bool
    summary: Dict[str, int]
    sources: List[SourceCheck]
    column_issues: List[ColumnIssue]
    errors: List[str]
    warnings: List[str]
    databricks_available: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ready": self.ready,
            "summary": self.summary,
            "sources": [asdict(s) for s in self.sources],
            "column_issues": [asdict(c) for c in self.column_issues],
            "errors": self.errors,
            "warnings": self.warnings,
            "databricks_available": self.databricks_available,
        }


# ── Service ──────────────────────────────────────────────────────────────────


_FQN_RE = re.compile(r"^([^.]+)\.([^.]+)\.([^.]+)$")


class GoldReadinessService:
    """Inspects a gold IR and produces a ReadinessReport."""

    def __init__(
        self,
        bronze_config_service,
        silver_config_service,
        databricks_service,
    ) -> None:
        self._bronze = bronze_config_service
        self._silver = silver_config_service
        self._dbx = databricks_service

    # ── Public ───────────────────────────────────────────────────────────────

    def check(self, ir: Dict[str, Any]) -> ReadinessReport:
        # 1. Build a usage index: {full_table_name: [referenced_by labels]}
        usage = self._collect_source_usage(ir)

        # 2. Build YAML lookups (cheap, local)
        bronze_targets = self._bronze_target_index()
        silver_targets = self._silver_target_index()

        # 3. Check Databricks reachability
        dbx_ok = bool(getattr(self._dbx, "available", False))

        # 4. Per-source verdict
        source_checks: List[SourceCheck] = []
        for fqn, refs in usage.items():
            check = self._check_one_source(fqn, refs, bronze_targets, silver_targets, dbx_ok)
            source_checks.append(check)

        # 5. Column-level checks (only for sources that resolved + dbx available)
        column_issues = self._check_columns(ir, source_checks, dbx_ok)

        # 6. Aggregate verdict
        errors: List[str] = []
        warnings: List[str] = []
        for sc in source_checks:
            if sc.error:
                errors.append(sc.error)
            if sc.warning:
                warnings.append(sc.warning)
        for ci in column_issues:
            errors.append(
                f"Column '{ci.missing_column}' referenced by {ci.referenced_by} "
                f"is missing from {ci.source_full_name}"
            )

        ready = len(errors) == 0
        summary = {
            "sources_total": len(source_checks),
            "sources_ok": sum(1 for s in source_checks if not s.error and not s.warning),
            "sources_missing_bronze": sum(
                1 for s in source_checks
                if s.classified_layer == "bronze" and not s.yaml_present
            ),
            "sources_missing_silver": sum(
                1 for s in source_checks
                if s.classified_layer == "silver" and not s.yaml_present
            ),
            "column_issues": len(column_issues),
        }

        return ReadinessReport(
            ready=ready,
            summary=summary,
            sources=source_checks,
            column_issues=column_issues,
            errors=errors,
            warnings=warnings,
            databricks_available=dbx_ok,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _collect_source_usage(self, ir: Dict[str, Any]) -> Dict[str, List[str]]:
        usage: Dict[str, List[str]] = {}
        for d in ir.get("dimensions", []) or []:
            src = (d.get("source_entity") or "").strip()
            if src:
                usage.setdefault(src, []).append(f"dim:{d.get('name', '')}")
        for f in ir.get("facts", []) or []:
            src = (f.get("source_entity") or "").strip()
            if src:
                usage.setdefault(src, []).append(f"fact:{f.get('name', '')}")
            # Also record dim refs as references — useful for diagnostics
            for fk in f.get("foreign_keys", []) or []:
                ref_dim = fk.get("dim", "")
                if ref_dim:
                    # This isn't a source, but track it to reconcile later
                    pass
        return usage

    def _bronze_target_index(self) -> Dict[str, str]:
        """Map full_table_name -> bronze source name."""
        out: Dict[str, str] = {}
        try:
            for s in self._bronze.list_sources():
                tt = getattr(s, "target_table", "") or ""
                if tt:
                    out[tt] = s.name
        except Exception as e:
            logger.warning("Could not list bronze sources: %s", e)
        return out

    def _silver_target_index(self) -> Dict[str, str]:
        """Map full_table_name -> silver entity name."""
        out: Dict[str, str] = {}
        try:
            for e in self._silver.list_entities():
                tt = getattr(e, "target_table", "") or ""
                if tt:
                    out[tt] = e.name
        except Exception as ex:
            logger.warning("Could not list silver entities: %s", ex)
        return out

    @staticmethod
    def _classify(fqn: str) -> str:
        """Return 'bronze' | 'silver' | 'unknown' based on the schema part."""
        m = _FQN_RE.match(fqn)
        if not m:
            return "unknown"
        schema = m.group(2).lower()
        if schema.startswith("slv_") or schema.startswith("silver"):
            return "silver"
        if schema.startswith("bronze") or schema.startswith("brz_"):
            return "bronze"
        return "unknown"

    def _check_one_source(
        self,
        fqn: str,
        refs: List[str],
        bronze_targets: Dict[str, str],
        silver_targets: Dict[str, str],
        dbx_ok: bool,
    ) -> SourceCheck:
        layer = self._classify(fqn)
        yaml_present = False
        if layer == "bronze":
            yaml_present = fqn in bronze_targets
        elif layer == "silver":
            yaml_present = fqn in silver_targets
        else:
            # Unknown layer — try both indices anyway
            yaml_present = fqn in bronze_targets or fqn in silver_targets

        check = SourceCheck(
            full_name=fqn,
            classified_layer=layer,
            yaml_present=yaml_present,
            table_reachable=None,
            referenced_by=refs,
        )

        # YAML diagnostics
        if not yaml_present:
            if layer == "bronze":
                check.error = (
                    f"Bronze source '{fqn}' is not ingested. "
                    f"Referenced by: {', '.join(refs)}. "
                    f"Build the bronze pipeline first."
                )
            elif layer == "silver":
                check.error = (
                    f"Silver entity '{fqn}' is missing. "
                    f"Referenced by: {', '.join(refs)}. "
                    f"Build it in the silver layer first."
                )
            else:
                check.warning = (
                    f"Source '{fqn}' has an unrecognised schema — could not classify "
                    f"as bronze or silver. Referenced by: {', '.join(refs)}."
                )
            return check

        # Databricks reachability
        if dbx_ok:
            try:
                rows = self._dbx.query_sql(f"SELECT 1 FROM {fqn} LIMIT 1")
                check.table_reachable = True
            except Exception as e:
                logger.info("Reachability check failed for %s: %s", fqn, e)
                check.table_reachable = False
                check.warning = (
                    f"YAML for '{fqn}' exists, but the table is not reachable on "
                    f"Databricks ({e}). Did you deploy + run the pipeline?"
                )

        return check

    def _check_columns(
        self,
        ir: Dict[str, Any],
        source_checks: List[SourceCheck],
        dbx_ok: bool,
    ) -> List[ColumnIssue]:
        if not dbx_ok:
            return []

        # Only DESCRIBE sources whose YAML exists and which are reachable
        describable: Set[str] = {
            sc.full_name for sc in source_checks
            if sc.yaml_present and sc.table_reachable
        }
        if not describable:
            return []

        # Cache of source -> column set
        columns_by_source: Dict[str, List[str]] = {}
        for fqn in describable:
            try:
                rows = self._dbx.query_sql(f"DESCRIBE TABLE {fqn}")
                # `DESCRIBE TABLE` returns col_name / data_type / comment (camelCase varies)
                cols: List[str] = []
                for r in rows or []:
                    name = r.get("col_name") or r.get("colName") or r.get("name") or ""
                    name = str(name).strip()
                    if name and not name.startswith("#"):
                        cols.append(name)
                columns_by_source[fqn] = cols
            except Exception as e:
                logger.warning("DESCRIBE failed for %s: %s", fqn, e)
                columns_by_source[fqn] = []

        issues: List[ColumnIssue] = []

        # Dim attributes
        for d in ir.get("dimensions", []) or []:
            src = (d.get("source_entity") or "").strip()
            if src not in columns_by_source:
                continue
            available = columns_by_source[src]
            available_lower = {c.lower() for c in available}
            for attr in d.get("attributes", []) or []:
                col = (attr.get("source_column") or attr.get("name") or "").strip()
                if col and col.lower() not in available_lower:
                    issues.append(
                        ColumnIssue(
                            source_full_name=src,
                            referenced_by=f"{d.get('name', '')}.{attr.get('name', '')}",
                            missing_column=col,
                            available_columns=available,
                        )
                    )
            # Business keys
            for bk in d.get("business_key", []) or []:
                if bk and bk.lower() not in available_lower:
                    issues.append(
                        ColumnIssue(
                            source_full_name=src,
                            referenced_by=f"{d.get('name', '')}.business_key[{bk}]",
                            missing_column=bk,
                            available_columns=available,
                        )
                    )

        # Fact grain + watermark + FK source columns
        for f in ir.get("facts", []) or []:
            src = (f.get("source_entity") or "").strip()
            if src not in columns_by_source:
                continue
            available = columns_by_source[src]
            available_lower = {c.lower() for c in available}
            for col in f.get("grain", []) or []:
                if col and col.lower() not in available_lower:
                    issues.append(
                        ColumnIssue(
                            source_full_name=src,
                            referenced_by=f"{f.get('name', '')}.grain[{col}]",
                            missing_column=col,
                            available_columns=available,
                        )
                    )
            wm = f.get("watermark_column")
            if wm and wm.lower() not in available_lower:
                issues.append(
                    ColumnIssue(
                        source_full_name=src,
                        referenced_by=f"{f.get('name', '')}.watermark_column",
                        missing_column=wm,
                        available_columns=available,
                    )
                )
            for fk in f.get("foreign_keys", []) or []:
                col = fk.get("source_column")
                if col and col.lower() not in available_lower:
                    issues.append(
                        ColumnIssue(
                            source_full_name=src,
                            referenced_by=f"{f.get('name', '')}.foreign_keys[{fk.get('dim', '')}].source_column",
                            missing_column=col,
                            available_columns=available,
                        )
                    )

        return issues

    # ── AI suggestions (Phase 3c-a) ──────────────────────────────────────────

    def enrich_with_ai_suggestions(
        self,
        report: ReadinessReport,
        *,
        tenant_service=None,
        tenant_id: Optional[str] = None,
    ) -> ReadinessReport:
        """For every ColumnIssue, ask the configured LLM for the closest column matches.

        Mutates `report.column_issues[*].suggestions` in place. Silently no-ops
        when no API key is configured or the LLM call fails — readiness logic
        does not depend on this.
        """
        if not report.column_issues:
            return report

        try:
            from app.services.ai_client_service import create_message, NoApiKeyError
        except ImportError:
            return report

        # Group issues by source so we make at most one LLM call per source
        by_source: Dict[str, List[ColumnIssue]] = {}
        for ci in report.column_issues:
            by_source.setdefault(ci.source_full_name, []).append(ci)

        for src, issues in by_source.items():
            available = issues[0].available_columns
            missing = [ci.missing_column for ci in issues]
            prompt = self._build_suggestion_prompt(src, missing, available)

            try:
                resp = create_message(
                    system=(
                        "You are a data engineer helping users reconcile column "
                        "names between a gold mart spec and a silver/bronze table. "
                        "Reply ONLY with valid JSON; no prose."
                    ),
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=512,
                    temperature=0.0,
                    tenant_service=tenant_service,
                    tenant_id=tenant_id,
                )
            except NoApiKeyError:
                logger.info("Skipping AI suggestions: no API key configured")
                return report
            except Exception as e:
                logger.warning("AI suggestion call failed for %s: %s", src, e)
                continue

            text = ""
            for block in getattr(resp, "content", []) or []:
                if getattr(block, "type", None) == "text":
                    text += getattr(block, "text", "") or ""
            text = text.strip().strip("`")
            if text.startswith("json"):
                text = text[4:].strip()

            import json
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                logger.warning("AI returned non-JSON for %s: %s", src, text[:200])
                continue
            if not isinstance(parsed, dict):
                continue

            # Match suggestions back onto the issue list
            for ci in issues:
                cands = parsed.get(ci.missing_column) or []
                if isinstance(cands, list):
                    ci.suggestions = [str(c) for c in cands][:3]

        return report

    @staticmethod
    def _build_suggestion_prompt(
        source: str, missing: List[str], available: List[str]
    ) -> str:
        return (
            f"Source table: {source}\n"
            f"Available columns ({len(available)}):\n"
            f"{', '.join(available)}\n\n"
            f"For each of the following missing column names, suggest up to 3 "
            f"likely matches from the available columns above (closest first). "
            f"Use semantic similarity, common abbreviations, and case "
            f"differences. If no good match exists, return [].\n\n"
            f"Missing columns: {missing}\n\n"
            "Reply with a JSON object mapping each missing name to an array of "
            "candidate column names from the available list. Example:\n"
            '{"country": ["country_code", "cust_country"], "first_name": ["fname"]}'
        )
