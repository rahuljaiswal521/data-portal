"""AI-powered test case generator for Bronze pipelines.

Given a natural-language description, uses Claude to produce:
- A structured TestCase definition with SQL assertions
- NDJSON test data records that properly exercise the assertion
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from app.config import settings
from app.models.testing import AssertionSpec, TestCase, TcConfirmRequest, TcGeneratePreview
from app.services import ai_client_service
from app.services.config_service import ConfigService
from app.services.testing_service import TESTING_ROOT, TestingService

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a data quality test case generator for a Bronze data ingestion pipeline.

Given a source schema, existing test suite, and a user's natural-language requirement,
generate a single structured test case with appropriate test data.

RULES:
1. Respond with EXACTLY one JSON object inside a ```json ... ``` fence. No other text.
2. The JSON must match this exact schema:
   {
     "tc_id": "<provided next ID>",
     "name": "<concise test name>",
     "category": "data_quality",
     "positive": <true if testing valid data should pass | false if testing bad data should be rejected>,
     "setup": ["truncate_test_table"],
     "teardown": [],
     "assertions": [
       {
         "type": "row_count",
         "sql": "SELECT COUNT(*) FROM <catalog>.<test_schema>.<target_table> WHERE ...",
         "expected": <integer>,
         "description": "<what this checks>"
       }
     ],
     "data_file_name": "<tc_id_lower>_<short_slug>.json",
     "data_records": [ <list of JSON objects, 3-8 records> ],
     "explanation": "<2-3 sentence explanation of what the TC tests and why the data was chosen>"
   }
3. Use the EXACT catalog, test_schema and target_table provided — never guess.
4. data_records must be valid JSON objects with realistic values matching the schema.
   Every record must include all primary key fields with UNIQUE values.
5. For NEGATIVE tests (positive=false): include records that violate the constraint
   so the assertion catches them (e.g. SELECT COUNT(*) WHERE bad_condition expected: 0,
   but after ingestion the pipeline should quarantine them — so expected is still 0 in main table).
6. Keep assertions minimal and targeted — 1-3 assertions per TC.
7. assertion type must be one of: row_count, row_count_gte, scalar_equals
"""


class TcGeneratorService:
    def __init__(
        self,
        config_svc: ConfigService,
        testing_svc: TestingService,
        tenant_service=None,
    ) -> None:
        self._config = config_svc
        self._testing = testing_svc
        self._tenants = tenant_service

    @property
    def available(self) -> bool:
        # Available if *any* server-side key is set; per-tenant keys are checked
        # lazily in generate_preview().
        return settings.anthropic_api_key is not None

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_preview(
        self,
        source_name: str,
        prompt: str,
        api_key: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> TcGeneratePreview:
        """Call the selected AI model to generate a TC preview. Nothing is written to disk."""
        ctx = self._build_context(source_name)
        user_message = self._build_user_message(ctx, prompt)

        try:
            response = ai_client_service.create_message(
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
                max_tokens=2048,
                tenant_service=self._tenants,
                tenant_id=tenant_id,
                api_key=api_key,
            )
        except ai_client_service.NoApiKeyError as e:
            raise RuntimeError(str(e))

        # Normalized response: extract the first text block
        raw = ""
        for block in response.content:
            if getattr(block, "type", None) == "text" and getattr(block, "text", None):
                raw += block.text
        if not raw:
            raise RuntimeError("AI returned no text response")
        data = self._extract_json(raw)

        # Validate and normalise
        data["tc_id"] = ctx["next_tc_id"]  # enforce server-computed ID
        data_file_name = data.get("data_file_name") or f"{ctx['next_tc_id'].lower()}_custom.json"
        data["data_file_name"] = data_file_name

        assertions = [
            AssertionSpec(
                type=a["type"],
                sql=a["sql"],
                expected=a["expected"],
                description=a["description"],
            )
            for a in data.get("assertions", [])
        ]

        return TcGeneratePreview(
            tc_id=data["tc_id"],
            name=data.get("name", "AI-generated test case"),
            category=data.get("category", "data_quality"),
            positive=bool(data.get("positive", True)),
            setup=data.get("setup", ["truncate_test_table"]),
            teardown=data.get("teardown", []),
            assertions=assertions,
            data_file_name=data_file_name,
            data_records=data.get("data_records", []),
            explanation=data.get("explanation", ""),
        )

    def confirm_and_run(self, source_name: str, req: TcConfirmRequest):
        """Write TC to suite YAML + data file, then run it synchronously."""
        from app.models.testing import TcConfirmResponse

        suite = self._testing.get_suite(source_name)
        if not suite:
            raise ValueError(f"No test suite found for '{source_name}'")

        # Guard against duplicate TC IDs
        existing_ids = {tc.id for tc in suite.test_cases}
        if req.tc_id in existing_ids:
            raise ValueError(f"Test case '{req.tc_id}' already exists in suite '{source_name}'")

        # 1. Write NDJSON data file
        data_dir = TESTING_ROOT / "data" / source_name
        data_dir.mkdir(parents=True, exist_ok=True)
        data_file_path = data_dir / req.data_file_name
        with open(data_file_path, "w", encoding="utf-8") as f:
            for record in req.data_records:
                f.write(json.dumps(record) + "\n")

        # 2. Build TestCase and append to suite YAML
        new_tc = TestCase(
            id=req.tc_id,
            name=req.name,
            category=req.category,
            positive=req.positive,
            data_file=req.data_file_name,
            setup=req.setup,
            teardown=req.teardown,
            assertions=req.assertions,
        )

        suite_path = TESTING_ROOT / "suites" / f"{source_name}.yaml"
        with open(suite_path, "r", encoding="utf-8") as f:
            suite_dict = yaml.safe_load(f)

        suite_dict["test_cases"].append(new_tc.model_dump())
        with open(suite_path, "w", encoding="utf-8") as f:
            yaml.dump(suite_dict, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        # 3. Run the new TC synchronously
        tc_result = self._testing.run_single_tc(source_name, req.tc_id)

        return TcConfirmResponse(
            tc_id=req.tc_id,
            data_file=req.data_file_name,
            message=f"Test case {req.tc_id} added to suite and executed.",
            result=tc_result,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_context(self, source_name: str) -> Dict[str, Any]:
        """Collect all context the AI needs: schema, existing TCs, next ID."""
        source = self._config.get_source(source_name)
        suite = self._testing.get_suite(source_name)

        # Extract columns from existing test data files (most reliable schema source)
        columns = self._infer_columns(source_name, suite)

        # Primary keys
        pks: List[str] = []
        if source:
            try:
                pks = source.get("cdc", {}).get("primary_keys", []) or []
            except Exception:
                pass
        if not pks and suite:
            pks = suite.primary_keys

        # Target table info
        test_catalog = suite.test_catalog if suite else "dev"
        test_schema = suite.test_schema if suite else "bronze_test"
        target_table = suite.target_table if suite else source_name

        # Next TC ID
        existing_ids: List[str] = []
        if suite:
            existing_ids = [tc.id for tc in suite.test_cases]
        next_num = self._next_tc_number(existing_ids)
        next_tc_id = f"TC{next_num:03d}"

        return {
            "source_name": source_name,
            "columns": columns,
            "primary_keys": pks,
            "test_catalog": test_catalog,
            "test_schema": test_schema,
            "target_table": target_table,
            "existing_tcs": existing_ids,
            "next_tc_id": next_tc_id,
        }

    def _build_user_message(self, ctx: Dict[str, Any], prompt: str) -> str:
        return f"""SOURCE: {ctx['source_name']}
TARGET TABLE: {ctx['test_catalog']}.{ctx['test_schema']}.{ctx['target_table']}
PRIMARY KEYS: {', '.join(ctx['primary_keys']) or 'unknown'}
COLUMNS: {', '.join(ctx['columns']) or 'unknown'}

EXISTING TEST CASE IDs (already taken): {', '.join(ctx['existing_tcs']) or 'none'}
NEXT AVAILABLE TC ID: {ctx['next_tc_id']}

USER REQUIREMENT:
{prompt}

Generate the test case JSON now."""

    def _infer_columns(self, source_name: str, suite) -> List[str]:
        """Read column names from the first available test data file."""
        data_dir = TESTING_ROOT / "data" / source_name
        if not data_dir.exists():
            return []
        for json_file in sorted(data_dir.glob("*.json")):
            try:
                first_line = json_file.read_text(encoding="utf-8").strip().splitlines()[0]
                record = json.loads(first_line)
                return list(record.keys())
            except Exception:
                continue
        return []

    def _next_tc_number(self, existing_ids: List[str]) -> int:
        """Return the next sequential TC number after the highest existing one."""
        nums = []
        for tid in existing_ids:
            m = re.match(r"TC(\d+)$", tid, re.IGNORECASE)
            if m:
                nums.append(int(m.group(1)))
        return (max(nums) + 1) if nums else 1

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from a ```json...``` fence, or parse the whole text."""
        fence = re.search(r"```json\s*([\s\S]+?)\s*```", text)
        if fence:
            return json.loads(fence.group(1))
        # Fallback: find first { ... } block
        brace = re.search(r"\{[\s\S]+\}", text)
        if brace:
            return json.loads(brace.group(0))
        raise ValueError(f"No JSON found in AI response: {text[:200]}")
