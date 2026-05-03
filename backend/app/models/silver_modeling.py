"""Pydantic models for Silver AI-assisted modeling endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Request Models ─────────────────────────────────────────────────────

class ProfileTableRequest(BaseModel):
    catalog: str
    schema_name: str = Field(alias="schema")
    table: str

    model_config = {"populate_by_name": True}


class BronzeTableInput(BaseModel):
    full_table_name: str = Field(description="Three-part name: catalog.schema.table")
    column_definitions: Optional[str] = Field(
        default=None,
        description="Free-text column definitions provided by the user",
    )


class SuggestModelRequest(BaseModel):
    tables: List[BronzeTableInput]
    domain_hint: Optional[str] = None
    entity_name_hint: Optional[str] = None


# ── Response Models ────────────────────────────────────────────────────

class ColumnInfo(BaseModel):
    name: str
    type: str
    comment: Optional[str] = None


class ColumnProfileStats(BaseModel):
    column: str
    distinct_count: int = 0
    null_count: int = 0


class TableProfileResponse(BaseModel):
    table: str
    row_count: int = 0
    columns: List[ColumnInfo] = []
    profiling: List[ColumnProfileStats] = []
    sample_data: List[Dict[str, Any]] = []
    has_scd2_columns: bool = False
    error: Optional[str] = None


class SuggestedColumnMapping(BaseModel):
    source: str
    target: str
    transform: Optional[str] = None
    default_value: Optional[str] = None
    reasoning: Optional[str] = None


class SuggestedSource(BaseModel):
    bronze_table: str
    priority: int = 1
    filter_condition: Optional[str] = None
    watermark: Optional[Dict[str, str]] = None
    columns: List[SuggestedColumnMapping] = []
    temporal: Optional[Dict[str, Any]] = None


class SuggestedTarget(BaseModel):
    catalog: str = "${catalog}"
    schema_name: str
    table: str
    scd_type: str = "scd2"
    business_keys: List[str] = []
    partition_by: List[str] = []
    exclude_columns_from_hash: List[str] = []


# ── Enterprise Model Request / Response ───────────────────────────────

class EnterpriseModelRequest(BaseModel):
    tables: List[str]           # ["dev.bronze.crm_customers", ...]
    catalog: str = "dev"


class EntitySuggestion(BaseModel):
    name: str
    description: str
    entity_type: str = "standard"   # standard | temporal_join
    scd_type: str = "scd2"          # scd2 | append
    business_keys: List[str] = []
    source_tables: List[str] = []   # which bronze tables feed this entity
    reasoning: str = ""


class DomainSuggestion(BaseModel):
    domain: str                     # customer, policy, finance, etc.
    schema: str                     # slv_customer, slv_policy, etc.
    reasoning: str = ""
    entities: List[EntitySuggestion] = []


class EnterpriseModelResponse(BaseModel):
    domains: List[DomainSuggestion] = []
    ungrouped_tables: List[str] = []
    overall_reasoning: str = ""
    error: Optional[str] = None


# ── Per-entity model suggestion ────────────────────────────────────────

class SuggestModelResponse(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    description: Optional[str] = None
    entity_type: str = "standard"
    sources: List[SuggestedSource] = []
    target: Optional[SuggestedTarget] = None
    reasoning: Optional[str] = None
    warnings: List[str] = []
    error: Optional[str] = None
