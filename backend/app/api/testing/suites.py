"""API endpoints for Bronze test suites."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from app.api.common.auth import get_current_tenant
from app.dependencies import get_tc_generator_service, get_tenant_service, get_testing_service
from app.models.testing import (
    GenerateSuiteResponse,
    RunSuiteResponse,
    TcConfirmRequest,
    TcConfirmResponse,
    TcGeneratePreview,
    TcGenerateRequest,
    TestCaseResult,
    TestRunListResponse,
    TestRunResult,
    TestSuite,
    TestSuiteListResponse,
)
from app.services.tc_generator_service import TcGeneratorService
from app.services.tenant_service import TenantService
from app.services.testing_service import TestingService

router = APIRouter()


@router.get("", response_model=TestSuiteListResponse, tags=["testing"])
def list_suites(svc: TestingService = Depends(get_testing_service)):
    return svc.list_suites()


@router.get("/{source_name}", response_model=TestSuite, tags=["testing"])
def get_suite(
    source_name: str,
    svc: TestingService = Depends(get_testing_service),
):
    suite = svc.get_suite(source_name)
    if not suite:
        raise HTTPException(
            status_code=404,
            detail=f"No test suite found for '{source_name}'",
        )
    return suite


@router.post(
    "/{source_name}/generate",
    response_model=GenerateSuiteResponse,
    tags=["testing"],
)
def generate_suite(
    source_name: str,
    svc: TestingService = Depends(get_testing_service),
):
    return svc.generate_suite(source_name)


@router.post(
    "/{source_name}/cancel",
    tags=["testing"],
)
def cancel_suite(
    source_name: str,
    svc: TestingService = Depends(get_testing_service),
):
    """Cancel the currently running suite for this source.

    Stops after the current test case finishes (in-flight Databricks jobs
    are not interrupted). Returns 404 if no suite is running.
    """
    cancelled = svc.cancel_suite(source_name)
    if not cancelled:
        raise HTTPException(
            status_code=404,
            detail=f"No running suite found for '{source_name}'",
        )
    return {"message": f"Cancellation requested for '{source_name}'"}


@router.post(
    "/{source_name}/run",
    response_model=RunSuiteResponse,
    status_code=202,
    tags=["testing"],
)
def run_suite(
    source_name: str,
    svc: TestingService = Depends(get_testing_service),
):
    try:
        return svc.run_suite(source_name)
    except ValueError as e:
        msg = str(e)
        status = 409 if "already in progress" in msg else 404
        raise HTTPException(status_code=status, detail=msg)


@router.post(
    "/{source_name}/run-tc/{tc_id}",
    response_model=TestCaseResult,
    tags=["testing"],
)
def run_single_tc(
    source_name: str,
    tc_id: str,
    svc: TestingService = Depends(get_testing_service),
):
    """Run a single test case synchronously (blocks until Databricks job completes).

    Used by the agentic test loop to execute one TC at a time and receive a
    structured result for diagnosis.
    """
    try:
        return svc.run_single_tc(source_name, tc_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/{source_name}/results/latest",
    response_model=TestRunResult,
    tags=["testing"],
)
def get_latest_result(
    source_name: str,
    svc: TestingService = Depends(get_testing_service),
):
    result = svc.get_latest_result(source_name)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No results found for '{source_name}'",
        )
    return result


@router.get(
    "/{source_name}/results/latest/report",
    response_class=HTMLResponse,
    tags=["testing"],
)
def get_latest_report(
    source_name: str,
    svc: TestingService = Depends(get_testing_service),
):
    """Return the latest test run as a self-contained HTML stakeholder report."""
    result = svc.get_latest_result(source_name)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No results found for '{source_name}'",
        )
    return HTMLResponse(
        content=svc._generate_html_report(result),
        headers={
            "Content-Disposition": f'attachment; filename="{source_name}_test_report.html"'
        },
    )


@router.get(
    "/{source_name}/results",
    response_model=TestRunListResponse,
    tags=["testing"],
)
def get_results(
    source_name: str,
    svc: TestingService = Depends(get_testing_service),
):
    return svc.get_results(source_name)


# ── AI test case generator endpoints ──────────────────────────────────────────

@router.post(
    "/{source_name}/ai-generate",
    response_model=TcGeneratePreview,
    tags=["testing"],
)
def ai_generate_tc(
    source_name: str,
    body: TcGenerateRequest,
    tenant_id: str = Depends(get_current_tenant),
    gen_svc: TcGeneratorService = Depends(get_tc_generator_service),
    test_svc: TestingService = Depends(get_testing_service),
):
    """Use AI to generate a test case preview from a natural-language description.

    Nothing is written to disk — returns a preview for the user to review.
    """
    suite = test_svc.get_suite(source_name)
    if not suite:
        raise HTTPException(status_code=404, detail=f"No test suite found for '{source_name}'")
    try:
        return gen_svc.generate_preview(source_name, body.prompt, tenant_id=tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        # Raised by generate_preview when no API key is configured for the selected provider
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {e}")


@router.post(
    "/{source_name}/ai-confirm",
    response_model=TcConfirmResponse,
    tags=["testing"],
)
def ai_confirm_tc(
    source_name: str,
    body: TcConfirmRequest,
    gen_svc: TcGeneratorService = Depends(get_tc_generator_service),
):
    """Confirm the AI-generated test case: write to suite YAML + data file + run it.

    The full preview payload is echoed back as the request body. Returns the
    TestCaseResult from the first execution.
    """
    try:
        return gen_svc.confirm_and_run(source_name, body)
    except ValueError as e:
        msg = str(e)
        status = 409 if "already exists" in msg else 404
        raise HTTPException(status_code=status, detail=msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add/run test case: {e}")
