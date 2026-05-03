"""Pydantic response models for Silver entities."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SilverEntitySummary(BaseModel):
    name: str
    domain: str
    description: str
    enabled: bool
    tags: Dict[str, str]
    target_table: str
    scd_type: str
    business_keys: List[str]
    source_count: int
    bronze_tables: List[str]
    schedule: Optional[str] = None


class SilverEntityDetail(BaseModel):
    name: str
    domain: str
    description: str
    enabled: bool
    tags: Dict[str, str]
    sources: List[Dict[str, Any]]
    target: Dict[str, Any]
    schedule: Optional[Dict[str, Any]] = None
    raw_yaml: str


class SilverEntityListResponse(BaseModel):
    entities: List[SilverEntitySummary]
    total: int


class SilverEntityCreateResponse(BaseModel):
    name: str
    yaml_path: str
    git_commit: Optional[str] = None
    job_id: Optional[str] = None
    message: str


class SilverEntityDeleteResponse(BaseModel):
    name: str
    message: str


class SilverValidationResponse(BaseModel):
    valid: bool
    errors: List[str]
    yaml_preview: Optional[str] = None


class SilverRunRecord(BaseModel):
    entity_name: str
    domain: str
    target_table: str
    status: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    records_read: int = 0
    records_written: int = 0
    records_skipped: int = 0
    error_message: Optional[str] = None
    scd_type: str = ""
    bronze_sources: str = ""


class SilverRunHistoryResponse(BaseModel):
    entity_name: str
    runs: List[SilverRunRecord]
    total: int


class SilverDashboardStats(BaseModel):
    total_entities: int
    enabled_entities: int
    domains: List[str]
    entities_by_domain: Dict[str, int]
    entities_by_scd_type: Dict[str, int]
    recent_runs: int = 0
    recent_failures: int = 0


class SilverDiagramResponse(BaseModel):
    mermaid: str
    entity_count: int
    domains: List[str]
