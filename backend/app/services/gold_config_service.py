"""Read / write Gold mart YAML files on disk.

Each mart lives under `gold_framework/conf/marts/<mart>/` as:
    _mart.yaml       (required) — name, description, schema, common_schema, owner, schedule
    dim_*.yaml       — one dimension per file
    fact_*.yaml      — one fact per file
    metrics.yaml     — list of metric configs

This service deliberately matches the on-disk schema used by the
`gold_framework.config.loader` so a write-then-load round trip is lossless.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class GoldConfigError(ValueError):
    """Raised when a mart write/read fails for a structural reason."""


class GoldConfigService:
    """Filesystem-backed CRUD for Gold marts.

    Constructor takes the *marts root* directory — e.g. `gold_framework/conf/marts/`.
    """

    def __init__(self, marts_dir: Path) -> None:
        self.marts_dir = Path(marts_dir)
        self.marts_dir.mkdir(parents=True, exist_ok=True)

    # ── Listing / reading ────────────────────────────────────────────────────

    def list_marts(self) -> List[Dict[str, Any]]:
        """Return one summary dict per mart directory."""
        out: List[Dict[str, Any]] = []
        if not self.marts_dir.exists():
            return out
        for path in sorted(self.marts_dir.iterdir()):
            if not path.is_dir():
                continue
            meta_file = path / "_mart.yaml"
            if not meta_file.exists():
                continue
            meta = yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}
            n_dims = len(list(path.glob("dim_*.yaml")))
            n_facts = len(list(path.glob("fact_*.yaml")))
            n_metrics = 0
            metrics_file = path / "metrics.yaml"
            if metrics_file.exists():
                m = yaml.safe_load(metrics_file.read_text(encoding="utf-8")) or {}
                n_metrics = len(m.get("metrics") or [])
            out.append(
                {
                    "name": meta.get("name") or path.name,
                    "description": meta.get("description", ""),
                    "schema": meta.get("schema") or f"gld_{path.name}",
                    "owner": meta.get("owner", ""),
                    "n_dimensions": n_dims,
                    "n_facts": n_facts,
                    "n_metrics": n_metrics,
                }
            )
        return out

    def get_mart(self, name: str) -> Dict[str, Any]:
        """Read full mart back into a dict (mart, dimensions, facts, metrics)."""
        mart_dir = self.marts_dir / name
        meta_file = mart_dir / "_mart.yaml"
        if not meta_file.exists():
            raise FileNotFoundError(f"Mart '{name}' not found at {mart_dir}")

        mart = yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}
        dimensions: List[Dict[str, Any]] = []
        for f in sorted(mart_dir.glob("dim_*.yaml")):
            dimensions.append(yaml.safe_load(f.read_text(encoding="utf-8")) or {})
        facts: List[Dict[str, Any]] = []
        for f in sorted(mart_dir.glob("fact_*.yaml")):
            facts.append(yaml.safe_load(f.read_text(encoding="utf-8")) or {})
        metrics: List[Dict[str, Any]] = []
        metrics_file = mart_dir / "metrics.yaml"
        if metrics_file.exists():
            m = yaml.safe_load(metrics_file.read_text(encoding="utf-8")) or {}
            metrics = list(m.get("metrics") or [])

        return {
            "mart": mart,
            "dimensions": dimensions,
            "facts": facts,
            "metrics": metrics,
        }

    # ── Writing ──────────────────────────────────────────────────────────────

    def write_mart(self, ir: Dict[str, Any], *, overwrite: bool = False) -> Path:
        """Write a complete mart from an IR dict.

        IR shape (matches `gold_framework.ingest.MartIR.to_dict()`):
            { "mart": {...}, "dimensions": [...], "facts": [...], "metrics": [...] }
        """
        mart_meta = ir.get("mart") or {}
        name = (mart_meta.get("name") or "").strip()
        if not name:
            raise GoldConfigError("IR missing mart.name")

        mart_dir = self.marts_dir / name
        if mart_dir.exists() and not overwrite:
            raise GoldConfigError(f"Mart '{name}' already exists (use overwrite=true)")

        if mart_dir.exists() and overwrite:
            shutil.rmtree(mart_dir)
        mart_dir.mkdir(parents=True, exist_ok=False)

        # _mart.yaml
        (mart_dir / "_mart.yaml").write_text(
            yaml.safe_dump(mart_meta, sort_keys=False), encoding="utf-8"
        )

        # dim_*.yaml
        for d in ir.get("dimensions", []) or []:
            dim_name = (d.get("name") or "").strip()
            if not dim_name:
                raise GoldConfigError("Dimension is missing 'name'")
            (mart_dir / f"{dim_name}.yaml").write_text(
                yaml.safe_dump(d, sort_keys=False), encoding="utf-8"
            )

        # fact_*.yaml
        for f in ir.get("facts", []) or []:
            fact_name = (f.get("name") or "").strip()
            if not fact_name:
                raise GoldConfigError("Fact is missing 'name'")
            (mart_dir / f"{fact_name}.yaml").write_text(
                yaml.safe_dump(f, sort_keys=False), encoding="utf-8"
            )

        # metrics.yaml
        metrics = ir.get("metrics") or []
        if metrics:
            (mart_dir / "metrics.yaml").write_text(
                yaml.safe_dump({"metrics": metrics}, sort_keys=False), encoding="utf-8"
            )

        return mart_dir

    def delete_mart(self, name: str) -> None:
        mart_dir = self.marts_dir / name
        if not mart_dir.exists():
            raise FileNotFoundError(f"Mart '{name}' not found")
        shutil.rmtree(mart_dir)

    def diff_against_existing(self, ir: Dict[str, Any]) -> Dict[str, Any]:
        """Return a shallow diff comparing the IR to what's currently on disk.

        Returned shape:
            {
              "exists": bool,
              "added":   {"dimensions": [...], "facts": [...], "metrics": [...]},
              "removed": {"dimensions": [...], "facts": [...], "metrics": [...]},
              "changed": {"dimensions": [...], "facts": [...], "metrics": [...]}
            }
        """
        name = (ir.get("mart") or {}).get("name") or ""
        empty = {"dimensions": [], "facts": [], "metrics": []}
        result: Dict[str, Any] = {
            "exists": False,
            "added": dict(empty),
            "removed": dict(empty),
            "changed": dict(empty),
        }

        mart_dir = self.marts_dir / name
        if not mart_dir.exists():
            result["added"]["dimensions"] = [d["name"] for d in ir.get("dimensions", [])]
            result["added"]["facts"] = [f["name"] for f in ir.get("facts", [])]
            result["added"]["metrics"] = [m["name"] for m in ir.get("metrics", [])]
            return result

        result["exists"] = True
        existing = self.get_mart(name)

        def _by_name(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
            return {it.get("name", ""): it for it in items}

        for kind in ("dimensions", "facts", "metrics"):
            new = _by_name(ir.get(kind, []) or [])
            old = _by_name(existing.get(kind, []) or [])
            result["added"][kind] = sorted(set(new) - set(old))
            result["removed"][kind] = sorted(set(old) - set(new))
            result["changed"][kind] = sorted(
                k for k in set(new) & set(old) if new[k] != old[k]
            )

        return result
