"""Pydantic response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.models.enums import CdcMode, LoadType, SchemaEvolutionMode, SourceType


class SourceSummary(BaseModel):
    name: str
    source_type: SourceType
    description: str
    enabled: bool
    tags: Dict[str, str]
    target_table: str
    cdc_mode: CdcMode
    load_type: LoadType
    schedule: Optional[str] = None


class SourceDetail(BaseModel):
    name: str
    source_type: SourceType
    description: str
    enabled: bool
    tags: Dict[str, str]
    connection: Dict[str, Any]
    extract: Dict[str, Any]
    target: Dict[str, Any]
    schedule: Optional[Dict[str, Any]] = None
    raw_yaml: str


class SourceListResponse(BaseModel):
    sources: List[SourceSummary]
    total: int


class SourceCreateResponse(BaseModel):
    name: str
    yaml_path: str
    git_commit: Optional[str] = None
    job_id: Optional[str] = None
    message: str


class SourceDeleteResponse(BaseModel):
    name: str
    message: str


class ValidationResponse(BaseModel):
    valid: bool
    errors: List[str]
    yaml_preview: Optional[str] = None


class RunRecord(BaseModel):
    source_name: str
    environment: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    status: str
    records_read: int = 0
    records_written: int = 0
    records_quarantined: int = 0
    error: Optional[str] = None


class RunHistoryResponse(BaseModel):
    source_name: str
    runs: List[RunRecord]
    total: int


class DeadLetterResponse(BaseModel):
    source_name: str
    total_count: int
    recent_records: List[Dict[str, Any]]


class DashboardStats(BaseModel):
    total_sources: int
    enabled_sources: int
    disabled_sources: int
    sources_by_type: Dict[str, int]
    recent_runs: int = 0
    recent_failures: int = 0


class EnvironmentInfo(BaseModel):
    name: str
    variables: Dict[str, str]


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    framework_root: str
    sources_dir_exists: bool
    databricks_configured: bool
