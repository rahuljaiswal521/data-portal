"""Tenant API key authentication dependency."""

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings
from app.dependencies import get_tenant_service
from app.services.tenant_service import TenantService

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_tenant(
    api_key: str = Security(api_key_header),
    tenant_svc: TenantService = Depends(get_tenant_service),
) -> str:
    """Validate API key and return tenant_id.

    When rag_require_auth is False (default for local dev),
    unauthenticated requests use the 'default' tenant.
    """
    if api_key:
        tenant_id = tenant_svc.validate_api_key(api_key)
        if tenant_id:
            return tenant_id
        raise HTTPException(status_code=401, detail="Invalid API key")

    # No key provided
    if not settings.rag_require_auth:
        return tenant_svc.ensure_default_tenant()

    raise HTTPException(status_code=401, detail="Missing X-API-Key header")
