#!/usr/bin/env python3
"""Run the file_crm_customers test suite sequentially (no background thread).

Tables must be clean (0 rows) before running.
Run: PYTHONUTF8=1 .venv/Scripts/python.exe ../run_suite_clean.py
"""
import sys, time
from datetime import datetime

sys.path.insert(0, "C:/Users/rahul/Demo/portal/backend")

from dotenv import load_dotenv
load_dotenv("C:/Users/rahul/Demo/portal/backend/.env")

from app.config import settings  # noqa: F401 — ensure settings loaded from .env
from app.services.config_service import ConfigService
from app.services.databricks_service import DatabricksService
from app.services.testing_service import TestingService

config_svc = ConfigService()
db_svc = DatabricksService()
svc = TestingService(config_svc, db_svc)

SOURCE = "file_crm_customers"
ENV = "dev"


def ts():
    return datetime.now().strftime("%H:%M:%S")


suite = svc.get_suite(SOURCE)
if not suite:
    print(f"ERROR: Suite not found for {SOURCE}")
    sys.exit(1)

print(f"[{ts()}] ========================================")
print(f"[{ts()}] Clean sequential run: {SOURCE}")
print(f"[{ts()}] {len(suite.test_cases)} test cases")
print(f"[{ts()}] ========================================")

# Ensure test job exists (upload test YAML + create/update Databricks job)
print(f"[{ts()}] Ensuring test job...")
try:
    svc._ensure_test_job(SOURCE, ENV)
    print(f"[{ts()}] Test job ready")
except Exception as e:
    print(f"[{ts()}] WARNING: Could not ensure test job: {e}")

passed = 0
failed = 0
results = []

for tc in suite.test_cases:
    print(f"\n[{ts()}] {'=' * 50}")
    print(f"[{ts()}] {tc.id}: {tc.name}")
    print(f"[{ts()}] Category: {tc.category}  |  Positive: {tc.positive}")
    print(f"[{ts()}] {'=' * 50}")

    try:
        tc_result = svc._run_test_case(tc, suite, ENV)
        results.append(tc_result)

        sym = "PASS" if tc_result.status == "PASSED" else "FAIL"
        print(f"[{ts()}] [{sym}] {tc.id} completed in {tc_result.duration_seconds:.0f}s")

        for ar in (tc_result.assertions or []):
            a_sym = "OK" if ar.passed else "XX"
            print(f"  [{a_sym}] {ar.description}: expected={ar.expected}, actual={ar.actual}")

        if tc_result.error:
            print(f"  ERROR: {tc_result.error}")

        if tc_result.status == "PASSED":
            passed += 1
        else:
            failed += 1

    except Exception as e:
        print(f"[{ts()}] EXCEPTION in {tc.id}: {e}")
        failed += 1
        results.append(None)

print(f"\n[{ts()}] ========================================")
print(f"[{ts()}] FINAL SUMMARY")
print(f"[{ts()}] ========================================")
print(f"  Total:  {len(results)}")
print(f"  PASSED: {passed}")
print(f"  FAILED: {failed}")
print()
for r in results:
    if r:
        sym = "PASS" if r.status == "PASSED" else "FAIL"
        dur = f"{r.duration_seconds:.0f}s" if r.duration_seconds else "?"
        print(f"  [{sym}] {r.id}  ({dur})  {r.name}")
    else:
        print("  [FAIL] ??? (exception)")
print(f"[{ts()}] ========================================")
overall = "ALL PASSED" if failed == 0 else f"{failed} FAILED"
print(f"[{ts()}] RESULT: {overall}")
