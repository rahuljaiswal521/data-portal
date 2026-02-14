"""Tenant management using SQLite."""

import hashlib
import logging
import secrets
import sqlite3
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class TenantService:
    def __init__(self) -> None:
        db_path = Path(settings.tenant_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(db_path)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tenants (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    api_key_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT DEFAULT (datetime('now')),
                    enabled INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    session_id TEXT,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
                )
            """)

    def create_tenant(self, tenant_id: str, name: str) -> str:
        """Create a tenant and return the plaintext API key (shown once)."""
        api_key = f"bp_{secrets.token_urlsafe(32)}"
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO tenants (id, name, api_key_hash) VALUES (?, ?, ?)",
                (tenant_id, name, api_key_hash),
            )
        logger.info("Created tenant: %s (%s)", tenant_id, name)
        return api_key

    def ensure_default_tenant(self) -> str:
        """Ensure a 'default' tenant exists; return its id."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM tenants WHERE id = 'default'"
            ).fetchone()
        if row:
            return "default"
        self.create_tenant("default", "Default Local Tenant")
        return "default"

    def validate_api_key(self, api_key: str) -> Optional[str]:
        """Validate an API key, return tenant_id or None."""
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM tenants WHERE api_key_hash = ? AND enabled = 1",
                (api_key_hash,),
            ).fetchone()
        return row["id"] if row else None

    def get_tenant(self, tenant_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id, name, created_at, enabled FROM tenants WHERE id = ?",
                (tenant_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_tenants(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, name, created_at, enabled FROM tenants"
            ).fetchall()
        return [dict(r) for r in rows]

    def save_chat_message(
        self, tenant_id: str, role: str, content: str, session_id: str
    ) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO chat_history (tenant_id, role, content, session_id) "
                "VALUES (?, ?, ?, ?)",
                (tenant_id, role, content, session_id),
            )

    def get_chat_history(
        self, tenant_id: str, session_id: str, limit: int = 20
    ) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM chat_history "
                "WHERE tenant_id = ? AND session_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (tenant_id, session_id, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]
