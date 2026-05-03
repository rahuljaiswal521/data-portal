"""Glue service: parse a business-rules upload, produce IR, optionally commit YAMLs.

Wraps `gold_framework.ingest.parse_business_rules` so the API layer does not
need to know about the framework's internals.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional


# Add gold_framework to sys.path lazily so the parser is importable from the
# backend without requiring an editable install.
def _ensure_gold_on_path(gold_framework_src: Path) -> None:
    p = str(gold_framework_src)
    if p not in sys.path:
        sys.path.insert(0, p)


class GoldIngestError(ValueError):
    pass


class GoldIngestService:
    """Parses business-rules uploads and (optionally) commits them as YAML.

    Stateless; takes its dependencies (config service + paths) by constructor.
    """

    def __init__(
        self,
        gold_framework_src: Path,
        gold_config_service,
    ) -> None:
        self._src = Path(gold_framework_src)
        self._cfg = gold_config_service
        _ensure_gold_on_path(self._src)

    # ── Public API ───────────────────────────────────────────────────────────

    def preview(
        self,
        *,
        upload_bytes: bytes,
        filename: str,
        default_mart_name: str = "new_mart",
    ) -> Dict[str, Any]:
        """Parse upload to IR + diff vs existing mart on disk.

        Returns:
            {
              "ir": {...},                # full intermediate representation
              "diff": {...},              # vs current on-disk mart (if any)
              "warnings": [...],
              "summary": {n_dims, n_facts, n_metrics}
            }
        """
        ir = self._parse(upload_bytes, filename, default_mart_name)
        ir_dict = ir.to_dict()
        diff = self._cfg.diff_against_existing(ir_dict)
        return {
            "ir": ir_dict,
            "diff": diff,
            "warnings": ir_dict.get("warnings", []),
            "summary": {
                "n_dimensions": len(ir_dict["dimensions"]),
                "n_facts": len(ir_dict["facts"]),
                "n_metrics": len(ir_dict["metrics"]),
            },
        }

    def commit(
        self,
        *,
        ir: Dict[str, Any],
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """Persist a previously-previewed IR to disk as YAML files."""
        if not ir or not ir.get("mart", {}).get("name"):
            raise GoldIngestError("IR is missing mart.name — cannot commit")

        mart_dir = self._cfg.write_mart(ir, overwrite=overwrite)
        return {
            "mart_name": ir["mart"]["name"],
            "mart_dir": str(mart_dir),
            "n_dimensions": len(ir.get("dimensions", []) or []),
            "n_facts": len(ir.get("facts", []) or []),
            "n_metrics": len(ir.get("metrics", []) or []),
        }

    def parse_and_commit(
        self,
        *,
        upload_bytes: bytes,
        filename: str,
        default_mart_name: str = "new_mart",
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        ir = self._parse(upload_bytes, filename, default_mart_name)
        return self.commit(ir=ir.to_dict(), overwrite=overwrite)

    # ── Internal ─────────────────────────────────────────────────────────────

    def _parse(self, data: bytes, filename: str, default_mart_name: str):
        # Import lazily so import errors surface at call time, not module load
        try:
            from gold_framework.ingest import parse_business_rules  # type: ignore
        except ImportError as e:
            raise GoldIngestError(
                f"gold_framework is not importable: {e}. "
                "Check settings.gold_framework_src_path."
            ) from e

        if not filename.lower().endswith((".xlsx", ".xlsm", ".json")):
            raise GoldIngestError(
                "Upload must be an .xlsx or .json file"
            )

        return parse_business_rules(
            data, default_mart_name=default_mart_name, filename=filename
        )
