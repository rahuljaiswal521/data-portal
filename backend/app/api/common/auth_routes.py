"""Username/password authentication routes.

Endpoints:
- POST /auth/login  — exchange username+password for a fresh X-API-Key
- POST /auth/logout — client-side stateless logout (API key is rotated on next login)
- GET  /auth/me     — return profile for the tenant tied to the current API key
"""

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.api.common.auth import get_current_tenant
from app.dependencies import get_tenant_service
from app.models.auth import (
    CreateUserRequest,
    CreateUserResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    MeResponse,
)
from app.services.tenant_service import TenantService

logger = logging.getLogger(__name__)

router = APIRouter()

# Strict header reader — does NOT use the lenient get_current_tenant() fallback,
# which would resolve missing/invalid keys to the 'default' tenant when
# rag_require_auth=False. Admin endpoints must always require a real key.
_strict_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@router.post("/auth/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    tenant_svc: TenantService = Depends(get_tenant_service),
) -> LoginResponse:
    tenant_id = tenant_svc.verify_credentials(body.username, body.password)
    if not tenant_id:
        # Constant-ish message to avoid username enumeration.
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Mint a fresh API key (hash-only storage means we can't recover the old one).
    api_key = tenant_svc.get_api_key_for_tenant(tenant_id)
    if not api_key:
        logger.error("Failed to rotate API key for tenant %s", tenant_id)
        raise HTTPException(status_code=500, detail="Unable to issue API key")

    tenant_svc.update_last_login(tenant_id)
    profile = tenant_svc.get_user_profile(tenant_id) or {}
    logger.info("[AUTH] Login success: tenant=%s user=%s", tenant_id, body.username)

    return LoginResponse(
        api_key=api_key,
        tenant_id=tenant_id,
        username=profile.get("username") or body.username,
        display_name=profile.get("display_name"),
        role=profile.get("role") or "user",
    )


@router.post("/auth/logout", response_model=LogoutResponse)
def logout() -> LogoutResponse:
    """Stateless logout. The frontend discards its stored API key; the key itself
    remains valid until the next successful login rotates it. This mirrors the
    simplicity of the Flask-Login pattern without introducing a session store."""
    return LogoutResponse(success=True)


def _slugify_tenant_id(username: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", username.lower()).strip("_")
    return slug or "user"


def _require_admin(
    api_key: Optional[str] = Security(_strict_api_key_header),
    tenant_svc: TenantService = Depends(get_tenant_service),
) -> str:
    """Dependency: require a valid API key whose tenant has role='admin'.

    Bypasses the lenient get_current_tenant() fallback so admin endpoints stay
    locked even when rag_require_auth=False (current Azure default).
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    tenant_id = tenant_svc.validate_api_key(api_key)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Invalid API key")
    profile = tenant_svc.get_user_profile(tenant_id)
    if not profile or profile.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return tenant_id


@router.post("/auth/admin/users", response_model=CreateUserResponse)
def create_user(
    body: CreateUserRequest,
    _admin_id: str = Depends(_require_admin),
    tenant_svc: TenantService = Depends(get_tenant_service),
) -> CreateUserResponse:
    """Create or update a portal user. Admin-only.

    Idempotent: if a tenant row with the derived id already exists, this
    rotates the password / display_name / role on that row instead of failing.
    """
    tenant_id = _slugify_tenant_id(body.username)
    existing = tenant_svc.get_tenant(tenant_id)
    created = existing is None
    if created:
        # Mint a tenant row; the auto-generated API key is unused (rotated on login).
        tenant_svc.create_tenant(tenant_id, body.display_name or body.username)

    tenant_svc.set_credentials(
        tenant_id=tenant_id,
        username=body.username,
        password=body.password,
        display_name=body.display_name or body.username,
        role=body.role,
    )
    logger.info(
        "[AUTH] %s user via admin API: tenant=%s username=%s role=%s",
        "Created" if created else "Updated",
        tenant_id,
        body.username,
        body.role,
    )
    return CreateUserResponse(
        tenant_id=tenant_id,
        username=body.username,
        display_name=body.display_name or body.username,
        role=body.role,
        created=created,
    )


@router.get("/auth/me", response_model=MeResponse)
def me(
    tenant_id: str = Depends(get_current_tenant),
    tenant_svc: TenantService = Depends(get_tenant_service),
) -> MeResponse:
    profile = tenant_svc.get_user_profile(tenant_id)
    if not profile:
        # Tenant resolved but no user row — shouldn't happen, but degrade gracefully.
        return MeResponse(tenant_id=tenant_id)
    return MeResponse(**profile)
