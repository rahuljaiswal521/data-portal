"""Pydantic request models for Silver entity configuration."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SilverWatermarkRequest(BaseModel):
    column: str = "_effective_from"
    type: str = "timestamp"
    default_value: Optional[str] = None


class SilverColumnMappingRequest(BaseModel):
    source: str
    target: str
    transform: Optional[str] = None
    default_value: Optional[str] = None


class SilverTemporalConfigRequest(BaseModel):
    start_column: str
    end_column: str
    end_inclusive: bool = False


class SilverSourceMappingRequest(BaseModel):
    bronze_table: str
    priority: int = 1
    filter_condition: Optional[str] = None
    watermark: SilverWatermarkRequest = Field(default_factory=SilverWatermarkRequest)
    columns: List[SilverColumnMappingRequest] = Field(default_factory=list)
    temporal: Optional[SilverTemporalConfigRequest] = None


class SilverTargetRequest(BaseModel):
    catalog: str = ""
    schema_name: str = Field(default="", alias="schema")
    table: str = ""
    scd_type: str = "scd2"
    business_keys: List[str] = Field(default_factory=list)
    partition_by: List[str] = Field(default_factory=list)
    exclude_columns_from_hash: List[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class SilverScheduleRequest(BaseModel):
    cron_expression: Optional[str] = None
    timezone: str = "UTC"


class SilverEntityCreateRequest(BaseModel):
    name: str
    domain: str
    description: str = ""
    enabled: bool = True
    entity_type: str = "standard"
    tags: Dict[str, str] = Field(default_factory=dict)
    sources: List[SilverSourceMappingRequest] = Field(default_factory=list)
    target: SilverTargetRequest = Field(default_factory=SilverTargetRequest)
    schedule: Optional[SilverScheduleRequest] = None


class SilverEntityUpdateRequest(BaseModel):
    description: Optional[str] = None
    enabled: Optional[bool] = None
    tags: Optional[Dict[str, str]] = None
    sources: Optional[List[SilverSourceMappingRequest]] = None
    target: Optional[SilverTargetRequest] = None
    schedule: Optional[SilverScheduleRequest] = None
