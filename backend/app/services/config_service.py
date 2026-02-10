"""Service for reading, writing, and validating source YAML configs."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from jinja2 import Environment, FileSystemLoader

from app.config import settings
from app.models.enums import CdcMode, LoadType, SourceType
from app.models.requests import SourceCreateRequest, SourceUpdateRequest
from app.models.responses import SourceDetail, SourceSummary


class ConfigService:
    def __init__(self) -> None:
        template_dir = Path(__file__).parent.parent / "templates"
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            keep_trailing_newline=True,
        )
        self._template = self._jinja_env.get_template("source.yaml.j2")

    @property
    def sources_dir(self) -> Path:
        return settings.sources_dir

    def list_sources(
        self,
        source_type: Optional[str] = None,
        domain: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> List[SourceSummary]:
        sources: List[SourceSummary] = []
        if not self.sources_dir.exists():
            return sources

        for yaml_file in sorted(self.sources_dir.glob("*.yaml")):
            try:
                data = self._read_yaml(yaml_file)
            except Exception:
                continue

            if source_type and data.get("source_type") != source_type:
                continue
            if domain and data.get("tags", {}).get("domain") != domain:
                continue
            if enabled is not None and data.get("enabled", True) != enabled:
                continue

            target = data.get("target", {})
            cdc = target.get("cdc", {})
            schedule = data.get("schedule", {})

            sources.append(
                SourceSummary(
                    name=data.get("name", yaml_file.stem),
                    source_type=SourceType(data.get("source_type", "file")),
                    description=data.get("description", ""),
                    enabled=data.get("enabled", True),
                    tags=data.get("tags", {}),
                    target_table=f"{target.get('catalog', '')}.{target.get('schema', 'bronze')}.{target.get('table', '')}",
                    cdc_mode=CdcMode(cdc.get("mode", "append")),
                    load_type=LoadType(data.get("extract", {}).get("load_type", "full")),
                    schedule=schedule.get("cron_expression"),
                )
            )
        return sources

    def get_source(self, name: str) -> Optional[SourceDetail]:
        yaml_path = self._source_path(name)
        if not yaml_path.exists():
            return None

        data = self._read_yaml(yaml_path)
        raw_yaml = yaml_path.read_text(encoding="utf-8")

        return SourceDetail(
            name=data.get("name", name),
            source_type=SourceType(data.get("source_type", "file")),
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
            tags=data.get("tags", {}),
            connection=data.get("connection", {}),
            extract=data.get("extract", {}),
            target=data.get("target", {}),
            schedule=data.get("schedule"),
            raw_yaml=raw_yaml,
        )

    def source_exists(self, name: str) -> bool:
        return self._source_path(name).exists()

    def write_source(self, req: SourceCreateRequest) -> str:
        yaml_content = self.render_yaml(req)
        yaml_path = self._source_path(req.name)
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        yaml_path.write_text(yaml_content, encoding="utf-8")
        return str(yaml_path)

    def update_source(self, name: str, req: SourceUpdateRequest) -> str:
        yaml_path = self._source_path(name)
        data = self._read_yaml(yaml_path)

        if req.description is not None:
            data["description"] = req.description
        if req.enabled is not None:
            data["enabled"] = req.enabled
        if req.tags is not None:
            data["tags"] = req.tags
        if req.connection is not None:
            data["connection"] = req.connection.model_dump(exclude_none=True)
        if req.extract is not None:
            data["extract"] = req.extract.model_dump(exclude_none=True)
        if req.target is not None:
            target_dict = req.target.model_dump(exclude_none=True, by_alias=True)
            data["target"] = target_dict
        if req.schedule is not None:
            data["schedule"] = req.schedule.model_dump(exclude_none=True)

        # Re-render via template by building a full create request from merged data
        full_req = SourceCreateRequest(
            name=data["name"],
            source_type=SourceType(data["source_type"]),
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
            tags=data.get("tags", {}),
            **self._extract_nested(data),
        )
        yaml_content = self.render_yaml(full_req)
        yaml_path.write_text(yaml_content, encoding="utf-8")
        return str(yaml_path)

    def delete_source(self, name: str) -> bool:
        yaml_path = self._source_path(name)
        if yaml_path.exists():
            yaml_path.unlink()
            return True
        return False

    def render_yaml(self, req: SourceCreateRequest) -> str:
        ctx = req.model_dump(mode="json")
        return self._template.render(**ctx)

    def validate_config(self, req: SourceCreateRequest) -> tuple[bool, list[str]]:
        """Validate by round-tripping through the framework's ConfigLoader._parse_source."""
        errors: list[str] = []

        # Basic validation
        if not req.name:
            errors.append("Source name is required")
        if not req.target.table:
            errors.append("Target table name is required")
        if not req.target.catalog:
            errors.append("Target catalog is required")

        # Type-specific validation
        if req.source_type == SourceType.JDBC:
            if not req.extract.table and not req.extract.query:
                errors.append("JDBC source requires either 'table' or 'query'")
        elif req.source_type == SourceType.FILE:
            if not req.extract.path:
                errors.append("File source requires 'path'")
        elif req.source_type == SourceType.API:
            if not req.extract.base_url:
                errors.append("API source requires 'base_url'")
        elif req.source_type == SourceType.STREAM:
            if not req.extract.kafka_bootstrap_servers and not req.extract.event_hub_connection_string_key:
                errors.append("Stream source requires kafka_bootstrap_servers or event_hub_connection_string_key")

        # CDC validation
        if req.target.cdc.enabled:
            if req.target.cdc.mode in (CdcMode.SCD2, CdcMode.UPSERT):
                if not req.target.cdc.primary_keys:
                    errors.append(f"CDC mode '{req.target.cdc.mode}' requires primary_keys")

        if errors:
            return False, errors

        # Try round-trip through framework parser
        try:
            yaml_content = self.render_yaml(req)
            data = yaml.safe_load(yaml_content)
            framework_src = str(settings.framework_src_path)
            if framework_src not in sys.path:
                sys.path.insert(0, framework_src)
            from bronze_framework.config.loader import ConfigLoader
            loader = ConfigLoader.__new__(ConfigLoader)
            loader._parse_source(data)
        except Exception as e:
            errors.append(f"Framework validation failed: {str(e)}")
            return False, errors

        return True, []

    def _source_path(self, name: str) -> Path:
        # Try finding existing file with any prefix pattern
        for yaml_file in self.sources_dir.glob("*.yaml"):
            data = self._read_yaml(yaml_file)
            if data.get("name") == name:
                return yaml_file
        # Default: use source_type prefix from name pattern or just name
        return self.sources_dir / f"{name}.yaml"

    def _read_yaml(self, path: Path) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _extract_nested(self, data: dict) -> dict:
        """Extract connection/extract/target/schedule from raw dict for rebuilding request."""
        result: dict = {}
        if "connection" in data:
            result["connection"] = data["connection"]
        if "extract" in data:
            result["extract"] = data["extract"]
        if "target" in data:
            t = data["target"]
            if "schema" in t and "schema_name" not in t:
                t["schema_name"] = t.pop("schema")
            result["target"] = t
        if "schedule" in data:
            result["schedule"] = data["schedule"]
        return result
