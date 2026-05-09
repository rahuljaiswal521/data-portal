"""Tenant management using SQLite."""

import hashlib
import logging
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import bcrypt

from app.config import settings

logger = logging.getLogger(__name__)

# bcrypt caps passwords at 72 bytes; longer inputs are truncated to match
# historical behaviour and avoid ValueError in bcrypt 4.x.
_BCRYPT_MAX_BYTES = 72


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
                    enabled INTEGER DEFAULT 1,
                    anthropic_api_key TEXT
                )
            """)
            # Migrate: add columns if upgrading from older schema
            for col in (
                "anthropic_api_key TEXT",
                "openai_api_key TEXT",
                "gemini_api_key TEXT",
                "selected_model TEXT",
                "username TEXT",
                "password_hash TEXT",
                "display_name TEXT",
                "role TEXT DEFAULT 'user'",
                "last_login TEXT",
                "databricks_host TEXT",
                "databricks_token TEXT",
                "databricks_warehouse_id TEXT",
            ):
                try:
                    conn.execute(f"ALTER TABLE tenants ADD COLUMN {col}")
                except Exception:
                    pass  # Column already exists
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

    def set_anthropic_api_key(self, tenant_id: str, api_key: str) -> None:
        """Store the tenant's own Anthropic API key (plaintext — stored server-side)."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tenants SET anthropic_api_key = ? WHERE id = ?",
                (api_key, tenant_id),
            )

    def clear_anthropic_api_key(self, tenant_id: str) -> None:
        """Remove the tenant's Anthropic API key (falls back to server key)."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tenants SET anthropic_api_key = NULL WHERE id = ?",
                (tenant_id,),
            )

    def get_anthropic_api_key(self, tenant_id: str) -> Optional[str]:
        """Return the tenant's own Anthropic API key, or None if not set."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT anthropic_api_key FROM tenants WHERE id = ?",
                (tenant_id,),
            ).fetchone()
        if row:
            return row["anthropic_api_key"]
        return None

    # ── OpenAI ────────────────────────────────────────────────────────────────

    def set_openai_api_key(self, tenant_id: str, api_key: str) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tenants SET openai_api_key = ? WHERE id = ?",
                (api_key, tenant_id),
            )

    def clear_openai_api_key(self, tenant_id: str) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tenants SET openai_api_key = NULL WHERE id = ?",
                (tenant_id,),
            )

    def get_openai_api_key(self, tenant_id: str) -> Optional[str]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT openai_api_key FROM tenants WHERE id = ?",
                (tenant_id,),
            ).fetchone()
        return row["openai_api_key"] if row else None

    # ── Gemini ────────────────────────────────────────────────────────────────

    def set_gemini_api_key(self, tenant_id: str, api_key: str) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tenants SET gemini_api_key = ? WHERE id = ?",
                (api_key, tenant_id),
            )

    def clear_gemini_api_key(self, tenant_id: str) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tenants SET gemini_api_key = NULL WHERE id = ?",
                (tenant_id,),
            )

    def get_gemini_api_key(self, tenant_id: str) -> Optional[str]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT gemini_api_key FROM tenants WHERE id = ?",
                (tenant_id,),
            ).fetchone()
        return row["gemini_api_key"] if row else None

    # ── Databricks credentials ────────────────────────────────────────────────

    def set_databricks_credentials(
        self,
        tenant_id: str,
        host: str,
        token: str,
        warehouse_id: str,
    ) -> None:
        """Store the tenant's Databricks workspace credentials.

        All three fields are stored together — clearing any one is treated as
        clearing all. Stored server-side; the token is never returned to the
        client (only a host preview is exposed).
        """
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tenants SET databricks_host = ?, databricks_token = ?, "
                "databricks_warehouse_id = ? WHERE id = ?",
                (host, token, warehouse_id, tenant_id),
            )

    def clear_databricks_credentials(self, tenant_id: str) -> None:
        """Remove the tenant's Databricks credentials (all three fields)."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tenants SET databricks_host = NULL, databricks_token = NULL, "
                "databricks_warehouse_id = NULL WHERE id = ?",
                (tenant_id,),
            )

    def get_databricks_credentials(self, tenant_id: str) -> Optional[dict]:
        """Return {host, token, warehouse_id} or None if any field is missing."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT databricks_host, databricks_token, databricks_warehouse_id "
                "FROM tenants WHERE id = ?",
                (tenant_id,),
            ).fetchone()
        if not row:
            return None
        host = row["databricks_host"]
        token = row["databricks_token"]
        warehouse_id = row["databricks_warehouse_id"]
        if not host or not token or not warehouse_id:
            return None
        return {"host": host, "token": token, "warehouse_id": warehouse_id}

    # ── Selected model ────────────────────────────────────────────────────────

    def set_selected_model(self, tenant_id: str, model_id: str) -> None:
        """Persist the tenant's active AI model ID (e.g. 'claude-sonnet-4-5-20250929')."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tenants SET selected_model = ? WHERE id = ?",
                (model_id, tenant_id),
            )

    def clear_selected_model(self, tenant_id: str) -> None:
        """Reset the tenant's active model to the system default."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tenants SET selected_model = NULL WHERE id = ?",
                (tenant_id,),
            )

    def get_selected_model(self, tenant_id: str) -> Optional[str]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT selected_model FROM tenants WHERE id = ?",
                (tenant_id,),
            ).fetchone()
        return row["selected_model"] if row else None

    # ── User credentials (username + password) ────────────────────────────────

    @staticmethod
    def _encode_password(password: str) -> bytes:
        data = password.encode("utf-8")
        if len(data) > _BCRYPT_MAX_BYTES:
            data = data[:_BCRYPT_MAX_BYTES]
        return data

    @staticmethod
    def hash_password(password: str) -> str:
        hashed = bcrypt.hashpw(TenantService._encode_password(password), bcrypt.gensalt())
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        if not password_hash:
            return False
        try:
            return bcrypt.checkpw(
                TenantService._encode_password(password),
                password_hash.encode("utf-8"),
            )
        except Exception:
            return False

    def set_credentials(
        self,
        tenant_id: str,
        username: str,
        password: str,
        display_name: Optional[str] = None,
        role: str = "user",
    ) -> None:
        """Set or rotate a tenant's login credentials. Password is bcrypt-hashed."""
        password_hash = self.hash_password(password)
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tenants SET username = ?, password_hash = ?, "
                "display_name = COALESCE(?, display_name), role = ? WHERE id = ?",
                (username, password_hash, display_name, role, tenant_id),
            )

    def verify_credentials(self, username: str, password: str) -> Optional[str]:
        """Look up a user by username and verify the password. Returns tenant_id or None."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id, password_hash FROM tenants "
                "WHERE username = ? AND enabled = 1",
                (username,),
            ).fetchone()
        if not row:
            return None
        if not self.verify_password(password, row["password_hash"]):
            return None
        return row["id"]

    def update_last_login(self, tenant_id: str) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tenants SET last_login = ? WHERE id = ?",
                (datetime.utcnow().isoformat(timespec="seconds"), tenant_id),
            )

    def get_user_profile(self, tenant_id: str) -> Optional[dict]:
        """Return {tenant_id, username, display_name, role, last_login} or None."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id, username, display_name, role, last_login "
                "FROM tenants WHERE id = ?",
                (tenant_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "tenant_id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"] or row["username"],
            "role": row["role"] or "user",
            "last_login": row["last_login"],
        }

    def get_api_key_for_tenant(self, tenant_id: str) -> Optional[str]:
        """Rotate and return a fresh API key for the tenant.

        We cannot recover the stored key (only its hash), so on each successful
        login we mint a new API key, persist its hash, and return the plaintext
        so the frontend can use it as X-API-Key on subsequent requests.
        """
        api_key = f"bp_{secrets.token_urlsafe(32)}"
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tenants SET api_key_hash = ? WHERE id = ?",
                (api_key_hash, tenant_id),
            )
        return api_key

    def ensure_default_admin(
        self,
        username: str = "admin",
        password: Optional[str] = None,
    ) -> Optional[str]:
        """On first run, seed credentials for the default tenant.

        If the default tenant already has a username set, do nothing.
        If a password is provided, use it; otherwise generate a random one and log it
        (mirrors the ecran seed-admin pattern).

        Returns the generated password if one was generated, else None.
        """
        self.ensure_default_tenant()
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT username FROM tenants WHERE id = 'default'"
            ).fetchone()
        if row and row["username"]:
            return None  # Already seeded

        generated: Optional[str] = None
        if not password:
            password = secrets.token_urlsafe(12)
            generated = password

        self.set_credentials(
            "default",
            username=username,
            password=password,
            display_name="Administrator",
            role="admin",
        )
        if generated:
            logger.warning(
                "[AUTH] Seeded default admin user '%s' with generated password: %s",
                username,
                generated,
            )
            logger.warning("[AUTH] Set PORTAL_ADMIN_PASSWORD in .env to skip auto-generation.")
        else:
            logger.info("[AUTH] Seeded default admin user '%s' (password from env).", username)
        return generated
