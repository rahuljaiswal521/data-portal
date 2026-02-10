"""Enums mirroring bronze_framework.config.models."""

from enum import Enum


class SourceType(str, Enum):
    JDBC = "jdbc"
    FILE = "file"
    API = "api"
    STREAM = "stream"


class LoadType(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"


class SchemaEvolutionMode(str, Enum):
    MERGE = "merge"
    STRICT = "strict"
    RESCUE = "rescue"


class CdcMode(str, Enum):
    SCD2 = "scd2"
    UPSERT = "upsert"
    APPEND = "append"


class AuthType(str, Enum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    BEARER = "bearer"
    NONE = "none"


class PaginationType(str, Enum):
    OFFSET = "offset"
    CURSOR = "cursor"
    LINK_HEADER = "link_header"
