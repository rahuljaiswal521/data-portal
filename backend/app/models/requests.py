"""Pydantic request models mirroring bronze_framework.config.models."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.enums import (
    AuthType,
    CdcMode,
    LoadType,
    PaginationType,
    SchemaEvolutionMode,
    SourceType,
)


class ConnectionRequest(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    driver: Optional[str] = None
    url: Optional[str] = None
    secret_scope: Optional[str] = None
    secret_key_user: Optional[str] = None
    secret_key_password: Optional[str] = None
    properties: Dict[str, str] = Field(default_factory=dict)


class WatermarkRequest(BaseModel):
    column: str
    type: str = "timestamp"
    default_value: Optional[str] = None


class PaginationRequest(BaseModel):
    type: PaginationType = PaginationType.OFFSET
    page_size: int = 100
    max_pages: Optional[int] = None
    offset_param: str = "offset"
    limit_param: str = "limit"
    cursor_param: str = "cursor"
    cursor_response_path: Optional[str] = None
    data_response_path: str = "data"


class AuthRequest(BaseModel):
    type: AuthType = AuthType.NONE
    secret_scope: Optional[str] = None
    secret_key_token: Optional[str] = None
    secret_key_client_id: Optional[str] = None
    secret_key_client_secret: Optional[str] = None
    token_url: Optional[str] = None
    header_name: str = "Authorization"
    header_prefix: str = "Bearer"


class ExtractRequest(BaseModel):
    load_type: LoadType = LoadType.FULL
    watermark: Optional[WatermarkRequest] = None
    # JDBC
    query: Optional[str] = None
    table: Optional[str] = None
    partition_column: Optional[str] = None
    num_partitions: int = 1
    fetch_size: int = 10000
    # File
    path: Optional[str] = None
    format: str = "parquet"
    format_options: Dict[str, str] = Field(default_factory=dict)
    auto_loader: bool = False
    checkpoint_path: Optional[str] = None
    # API
    base_url: Optional[str] = None
    endpoint: Optional[str] = None
    method: str = "GET"
    headers: Dict[str, str] = Field(default_factory=dict)
    params: Dict[str, str] = Field(default_factory=dict)
    auth: Optional[AuthRequest] = None
    pagination: Optional[PaginationRequest] = None
    max_retries: int = 3
    retry_backoff_factor: float = 2.0
    timeout_seconds: int = 30
    response_root_path: str = "data"
    # Stream
    kafka_bootstrap_servers: Optional[str] = None
    kafka_topic: Optional[str] = None
    kafka_consumer_group: Optional[str] = None
    kafka_options: Dict[str, str] = Field(default_factory=dict)
    event_hub_connection_string_key: Optional[str] = None
    event_hub_consumer_group: str = "$Default"
    starting_offsets: str = "earliest"


class MetadataColumnRequest(BaseModel):
    name: str
    expression: str


class SchemaEvolutionRequest(BaseModel):
    mode: SchemaEvolutionMode = SchemaEvolutionMode.MERGE
    rescued_data_column: str = "_rescued_data"


class QualityRequest(BaseModel):
    enabled: bool = True
    dead_letter_table_suffix: str = "dead_letter"
    quarantine_threshold_pct: float = 10.0


class CdcRequest(BaseModel):
    enabled: bool = False
    mode: CdcMode = CdcMode.APPEND
    primary_keys: List[str] = Field(default_factory=list)
    sequence_column: Optional[str] = None
    exclude_columns_from_hash: List[str] = Field(default_factory=list)
    delete_condition_column: Optional[str] = None
    delete_condition_value: Optional[str] = None


class LandingRequest(BaseModel):
    path: Optional[str] = None
    archive_path: Optional[str] = None
    retention_days: int = 10
    cleanup_enabled: bool = True


class TargetRequest(BaseModel):
    catalog: str = ""
    schema_name: str = Field(default="bronze", alias="schema")
    table: str = ""
    partition_by: List[str] = Field(default_factory=list)
    z_order_by: List[str] = Field(default_factory=list)
    table_properties: Dict[str, str] = Field(default_factory=dict)
    metadata_columns: List[MetadataColumnRequest] = Field(default_factory=list)
    schema_evolution: SchemaEvolutionRequest = Field(default_factory=SchemaEvolutionRequest)
    quality: QualityRequest = Field(default_factory=QualityRequest)
    cdc: CdcRequest = Field(default_factory=CdcRequest)
    landing: LandingRequest = Field(default_factory=LandingRequest)

    model_config = {"populate_by_name": True}


class ScheduleRequest(BaseModel):
    cron_expression: Optional[str] = None
    timezone: str = "UTC"
    pause_status: str = "UNPAUSED"


class SourceCreateRequest(BaseModel):
    name: str
    source_type: SourceType
    description: str = ""
    enabled: bool = True
    tags: Dict[str, str] = Field(default_factory=dict)
    connection: ConnectionRequest = Field(default_factory=ConnectionRequest)
    extract: ExtractRequest = Field(default_factory=ExtractRequest)
    target: TargetRequest = Field(default_factory=TargetRequest)
    schedule: Optional[ScheduleRequest] = None


class SourceUpdateRequest(BaseModel):
    description: Optional[str] = None
    enabled: Optional[bool] = None
    tags: Optional[Dict[str, str]] = None
    connection: Optional[ConnectionRequest] = None
    extract: Optional[ExtractRequest] = None
    target: Optional[TargetRequest] = None
    schedule: Optional[ScheduleRequest] = None
