"""Unit tests for GoldReadinessService — covers the four user-stated paths:

1. source ingested in bronze AND silver AND columns present  -> ready
2. source missing from bronze                                -> hard error
3. source ingested in bronze but missing from silver         -> hard error w/ silver-CTA wording
4. source present but column missing from silver             -> column issue (when DBX up)
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from app.services.gold_readiness_service import (
    ColumnIssue,
    GoldReadinessService,
    ReadinessReport,
    SourceCheck,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


def _make_bronze(target_table: str, name: str = "src"):
    return SimpleNamespace(name=name, target_table=target_table)


def _make_silver(target_table: str, name: str = "ent"):
    return SimpleNamespace(name=name, target_table=target_table)


def _ir_simple_sales() -> Dict[str, Any]:
    """Sales mart IR referencing one silver dim source + one silver fact source."""
    return {
        "mart": {"name": "sales"},
        "dimensions": [
            {
                "name": "dim_customer",
                "source_entity": "dev.slv_customer.customer",
                "business_key": ["customer_id"],
                "scd_type": "scd2",
                "is_conformed": True,
                "attributes": [
                    {"name": "customer_name"},
                    {"name": "country_code"},
                ],
            }
        ],
        "facts": [
            {
                "name": "fact_orders",
                "source_entity": "dev.slv_sales.order_line",
                "grain": ["order_id", "order_line_id"],
                "load_type": "merge",
                "watermark_column": "order_updated_at",
                "foreign_keys": [
                    {"dim": "dim_customer", "source_column": "customer_id"}
                ],
                "measures": [{"name": "amount", "expr": "qty * price"}],
            }
        ],
        "metrics": [],
    }


def _service(
    *,
    bronze_targets: List[str] = (),
    silver_targets: List[str] = (),
    dbx_available: bool = False,
    describe_columns: Dict[str, List[str]] = None,
):
    bronze = MagicMock()
    bronze.list_sources.return_value = [_make_bronze(t) for t in bronze_targets]
    silver = MagicMock()
    silver.list_entities.return_value = [_make_silver(t) for t in silver_targets]
    dbx = MagicMock()
    dbx.available = dbx_available

    cols = describe_columns or {}

    def query_sql(sql: str):
        # Accept SELECT 1 ... LIMIT 1 (reachability) and DESCRIBE TABLE ...
        if sql.upper().startswith("SELECT 1"):
            return [{"1": 1}]
        if sql.upper().startswith("DESCRIBE TABLE"):
            fqn = sql.split()[-1]
            return [{"col_name": c} for c in cols.get(fqn, [])]
        return []

    dbx.query_sql.side_effect = query_sql
    return GoldReadinessService(bronze, silver, dbx)


# ── Tests ────────────────────────────────────────────────────────────────────


def test_path1_all_silver_yamls_present_no_dbx_is_ready():
    """User story step 5: all required silver entities exist -> ready (without dbx column check)."""
    svc = _service(
        silver_targets=["dev.slv_customer.customer", "dev.slv_sales.order_line"],
        dbx_available=False,
    )
    report = svc.check(_ir_simple_sales())
    assert report.ready is True
    assert report.errors == []
    assert report.summary["sources_total"] == 2
    assert report.summary["sources_missing_silver"] == 0
    assert report.column_issues == []


def test_path2_source_missing_from_silver_blocks_with_silver_cta():
    """User story step 4: silver missing -> hard error referencing the silver layer."""
    svc = _service(
        silver_targets=["dev.slv_customer.customer"],   # only one of two
        dbx_available=False,
    )
    report = svc.check(_ir_simple_sales())
    assert report.ready is False
    assert any("slv_sales.order_line" in e for e in report.errors)
    assert any("silver" in e.lower() for e in report.errors)
    assert report.summary["sources_missing_silver"] == 1


def test_path3_bronze_missing_blocks_with_bronze_cta():
    """User story step 3: bronze source not ingested -> hard error."""
    ir = {
        "mart": {"name": "ops"},
        "dimensions": [],
        "facts": [
            {
                "name": "fact_clicks",
                "source_entity": "dev.bronze.clickstream_events",
                "grain": ["event_id"],
                "load_type": "incremental_append",
                "watermark_column": "event_time",
                "foreign_keys": [],
                "measures": [],
            }
        ],
        "metrics": [],
    }
    svc = _service(bronze_targets=[])  # no bronze
    report = svc.check(ir)
    assert report.ready is False
    assert any("not ingested" in e for e in report.errors)
    assert any("bronze" in e.lower() for e in report.errors)
    assert report.summary["sources_missing_bronze"] == 1


def test_path4_column_missing_from_silver_when_dbx_available():
    """User story step 6 prerequisite: silver exists but the column gold expects is gone."""
    svc = _service(
        silver_targets=["dev.slv_customer.customer", "dev.slv_sales.order_line"],
        dbx_available=True,
        describe_columns={
            # `country_code` IS missing in silver — gold spec uses the wrong name
            "dev.slv_customer.customer": ["customer_id", "customer_name", "country"],
            "dev.slv_sales.order_line": [
                "order_id", "order_line_id", "customer_id", "qty", "price", "order_updated_at",
            ],
        },
    )
    report = svc.check(_ir_simple_sales())
    assert report.ready is False
    assert len(report.column_issues) == 1
    issue = report.column_issues[0]
    assert issue.missing_column == "country_code"
    assert issue.referenced_by == "dim_customer.country_code"
    assert "country" in issue.available_columns


def test_classification_handles_unknown_schema_with_warning():
    ir = {
        "mart": {"name": "x"},
        "dimensions": [
            {
                "name": "dim_x",
                "source_entity": "dev.weird_schema.table",
                "business_key": ["id"],
                "attributes": [{"name": "n"}],
            }
        ],
        "facts": [],
        "metrics": [],
    }
    svc = _service()
    report = svc.check(ir)
    # Unknown schemas are non-blocking (warning only) — not all sources need to
    # be in bronze/silver (e.g. external metrics tables, ref data)
    sc = report.sources[0]
    assert sc.classified_layer == "unknown"
    assert sc.warning is not None
    assert "unrecognised" in sc.warning
    assert report.warnings, "Unknown-schema warning should propagate to report.warnings"


def test_databricks_unreachable_warns_but_yaml_still_ok():
    """When YAML exists but the table is not in Databricks -> warn, don't block."""
    bronze = MagicMock()
    bronze.list_sources.return_value = []
    silver = MagicMock()
    silver.list_entities.return_value = [
        _make_silver("dev.slv_customer.customer"),
        _make_silver("dev.slv_sales.order_line"),
    ]
    dbx = MagicMock()
    dbx.available = True
    # Reachability check raises -> table_reachable=False -> warning, not error
    dbx.query_sql.side_effect = Exception("workspace down")

    svc = GoldReadinessService(bronze, silver, dbx)
    report = svc.check(_ir_simple_sales())

    # Errors list is empty (warnings only), so report is "ready" from a YAML POV
    assert report.errors == []
    assert report.ready is True
    assert all(s.warning and "not reachable" in s.warning for s in report.sources)


def test_ai_enrichment_populates_suggestions(monkeypatch):
    """AI enrichment maps issue.missing_column -> suggestions[]."""
    svc = _service(
        silver_targets=["dev.slv_customer.customer"],
        dbx_available=True,
        describe_columns={"dev.slv_customer.customer": ["customer_id", "country"]},
    )
    ir = {
        "mart": {"name": "x"},
        "dimensions": [
            {
                "name": "dim_customer",
                "source_entity": "dev.slv_customer.customer",
                "business_key": ["customer_id"],
                "attributes": [{"name": "country_code"}],
            }
        ],
        "facts": [],
        "metrics": [],
    }
    report = svc.check(ir)
    assert len(report.column_issues) == 1

    # Stub create_message -> JSON mapping
    fake_block = SimpleNamespace(type="text", text='{"country_code": ["country", "cust_country"]}')
    fake_resp = SimpleNamespace(content=[fake_block])

    def fake_create_message(**kwargs):
        return fake_resp

    import app.services.ai_client_service as ai_mod
    monkeypatch.setattr(ai_mod, "create_message", fake_create_message)

    enriched = svc.enrich_with_ai_suggestions(report)
    assert enriched.column_issues[0].suggestions == ["country", "cust_country"]
