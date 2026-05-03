"""Service for reading, writing, and validating Silver entity YAML configs."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from jinja2 import Environment, FileSystemLoader

from app.config import settings
from app.models.silver_requests import SilverEntityCreateRequest, SilverEntityUpdateRequest
from app.models.silver_responses import SilverEntityDetail, SilverEntitySummary


class SilverConfigService:
    def __init__(self) -> None:
        template_dir = Path(__file__).parent.parent / "templates"
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            keep_trailing_newline=True,
        )
        self._template = self._jinja_env.get_template("silver_entity.yaml.j2")

    @property
    def entities_dir(self) -> Path:
        return settings.silver_entities_dir

    def list_entities(
        self,
        domain: Optional[str] = None,
        enabled: Optional[bool] = None,
        scd_type: Optional[str] = None,
    ) -> List[SilverEntitySummary]:
        entities: List[SilverEntitySummary] = []
        if not self.entities_dir.exists():
            return entities

        for yaml_file in sorted(self.entities_dir.glob("*.yaml")):
            try:
                data = self._read_yaml(yaml_file)
            except Exception:
                continue

            if domain and data.get("domain") != domain:
                continue
            if enabled is not None and data.get("enabled", True) != enabled:
                continue

            target = data.get("target", {})
            entity_scd_type = target.get("scd_type", "scd2")
            if scd_type and entity_scd_type != scd_type:
                continue

            sources = data.get("sources", [])
            bronze_tables = [s.get("bronze_table", "") for s in sources]
            schedule = data.get("schedule", {})

            entities.append(
                SilverEntitySummary(
                    name=data.get("name", yaml_file.stem),
                    domain=data.get("domain", ""),
                    description=data.get("description", ""),
                    enabled=data.get("enabled", True),
                    tags=data.get("tags", {}),
                    target_table=f"{target.get('catalog', '')}.{target.get('schema', '')}.{target.get('table', '')}",
                    scd_type=entity_scd_type,
                    business_keys=[k for k in target.get("business_keys", []) if k],
                    source_count=len(sources),
                    bronze_tables=bronze_tables,
                    schedule=schedule.get("cron_expression") if schedule else None,
                )
            )
        return entities

    def get_entity(self, name: str) -> Optional[SilverEntityDetail]:
        yaml_path = self._entity_path(name)
        if not yaml_path.exists():
            return None

        data = self._read_yaml(yaml_path)
        raw_yaml = yaml_path.read_text(encoding="utf-8")

        return SilverEntityDetail(
            name=data.get("name", name),
            domain=data.get("domain", ""),
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
            tags=data.get("tags", {}),
            sources=data.get("sources", []),
            target=data.get("target", {}),
            schedule=data.get("schedule"),
            raw_yaml=raw_yaml,
        )

    def entity_exists(self, name: str) -> bool:
        return self._entity_path(name).exists()

    def write_entity(self, req: SilverEntityCreateRequest) -> str:
        yaml_content = self.render_yaml(req)
        yaml_path = self.entities_dir / f"{req.name}.yaml"
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        yaml_path.write_text(yaml_content, encoding="utf-8")
        return str(yaml_path)

    def update_entity(self, name: str, req: SilverEntityUpdateRequest) -> str:
        yaml_path = self._entity_path(name)
        data = self._read_yaml(yaml_path)

        if req.description is not None:
            data["description"] = req.description
        if req.enabled is not None:
            data["enabled"] = req.enabled
        if req.tags is not None:
            data["tags"] = req.tags
        if req.sources is not None:
            data["sources"] = [s.model_dump(exclude_none=True) for s in req.sources]
        if req.target is not None:
            target_dict = req.target.model_dump(exclude_none=True, by_alias=True)
            data["target"] = target_dict
        if req.schedule is not None:
            data["schedule"] = req.schedule.model_dump(exclude_none=True)

        # Rebuild full request from merged data and re-render
        full_req = SilverEntityCreateRequest(
            name=data["name"],
            domain=data["domain"],
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
            tags=data.get("tags", {}),
            **self._extract_nested(data),
        )
        yaml_content = self.render_yaml(full_req)
        yaml_path.write_text(yaml_content, encoding="utf-8")
        return str(yaml_path)

    def delete_entity(self, name: str) -> bool:
        yaml_path = self._entity_path(name)
        if yaml_path.exists():
            yaml_path.unlink()
            return True
        return False

    def render_yaml(self, req: SilverEntityCreateRequest) -> str:
        ctx = req.model_dump(mode="json")
        return self._template.render(**ctx)

    def validate_config(self, req: SilverEntityCreateRequest) -> tuple[bool, list[str]]:
        """Validate Silver entity configuration."""
        errors: list[str] = []

        if not req.name:
            errors.append("Entity name is required")
        if not req.domain:
            errors.append("Domain is required")
        if not req.target.table:
            errors.append("Target table name is required")
        if not req.target.catalog:
            errors.append("Target catalog is required")
        if not req.target.schema_name:
            errors.append("Target schema is required")

        if req.target.scd_type == "scd2" and not req.target.business_keys:
            errors.append("SCD2 entities require at least one business key")

        if not req.sources:
            errors.append("At least one source mapping is required")

        for i, source in enumerate(req.sources):
            if not source.bronze_table:
                errors.append(f"Source {i+1}: bronze_table is required")
            if not source.columns:
                errors.append(f"Source {i+1}: at least one column mapping is required")

        # Temporal join validation
        if req.entity_type == "temporal_join":
            for i, source in enumerate(req.sources):
                if not source.temporal:
                    errors.append(
                        f"Source {i+1}: temporal config is required for temporal_join entities"
                    )
                else:
                    target_cols = {c.target for c in source.columns}
                    if source.temporal.start_column not in target_cols:
                        errors.append(
                            f"Source {i+1}: temporal start_column "
                            f"'{source.temporal.start_column}' must exist in column mappings"
                        )
                    if source.temporal.end_column not in target_cols:
                        errors.append(
                            f"Source {i+1}: temporal end_column "
                            f"'{source.temporal.end_column}' must exist in column mappings"
                        )

        if errors:
            return False, errors

        # Round-trip through framework parser
        try:
            yaml_content = self.render_yaml(req)
            data = yaml.safe_load(yaml_content)
            silver_src = str(settings.silver_framework_src_path)
            if silver_src not in sys.path:
                sys.path.insert(0, silver_src)
            from silver_framework.config.loader import ConfigLoader
            loader = ConfigLoader.__new__(ConfigLoader)
            loader._parse_entity(data)
        except Exception as e:
            errors.append(f"Framework validation failed: {str(e)}")
            return False, errors

        return True, []

    def _entity_path(self, name: str) -> Path:
        for yaml_file in self.entities_dir.glob("*.yaml"):
            data = self._read_yaml(yaml_file)
            if data.get("name") == name:
                return yaml_file
        return self.entities_dir / f"{name}.yaml"

    def _read_yaml(self, path: Path) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _extract_nested(self, data: dict) -> dict:
        result: dict = {}
        if "sources" in data:
            result["sources"] = data["sources"]
        if "target" in data:
            t = data["target"]
            if "schema" in t and "schema_name" not in t:
                t["schema_name"] = t.pop("schema")
            result["target"] = t
        if "schedule" in data:
            result["schedule"] = data["schedule"]
        return result
