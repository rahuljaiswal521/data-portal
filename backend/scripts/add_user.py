"""Admin CLI: add or update a portal user.

Usage (from portal/backend, with .venv active):
    python -m scripts.add_user --username alice --display-name "Alice Smith"
    python -m scripts.add_user --username alice --display-name "Alice Smith" --password "MyPass!" --role admin
    python -m scripts.add_user --bulk users.csv

CSV format (header required):
    username,display_name,role
    alice,Alice Smith,admin
    bob,Bob Jones,admin

If --password is omitted a 16-char strong password is generated and printed once.
The tenant_id is derived from the username (lowercased, non-alnum -> '_').

Designed to run inside the Azure backend container too — it picks up
TENANT_DB_PATH from the same settings the app uses, so it writes to the
mounted /data/app/tenants.db file share.
"""
from __future__ import annotations

import argparse
import csv
import re
import secrets
import string
import sys
from pathlib import Path

# Allow running as `python scripts/add_user.py` from portal/backend
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.tenant_service import TenantService  # noqa: E402


_PWD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*-_=+"


def generate_password(length: int = 16) -> str:
    """Cryptographically-strong password with mixed character classes."""
    while True:
        pwd = "".join(secrets.choice(_PWD_ALPHABET) for _ in range(length))
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in "!@#$%^&*-_=+" for c in pwd)
        ):
            return pwd


def slugify_tenant_id(username: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", username.lower()).strip("_")
    return slug or "user"


def upsert_user(
    svc: TenantService,
    *,
    username: str,
    display_name: str,
    role: str,
    password: str | None,
) -> tuple[str, str, bool]:
    """Create-or-update a user. Returns (tenant_id, password, created)."""
    tenant_id = slugify_tenant_id(username)
    pwd = password or generate_password()

    existing = svc.get_tenant(tenant_id)
    created = existing is None
    if created:
        # Mint a tenant row (api_key is rotated on login, so we discard it)
        svc.create_tenant(tenant_id, display_name or username)

    svc.set_credentials(
        tenant_id=tenant_id,
        username=username,
        password=pwd,
        display_name=display_name or username,
        role=role,
    )
    return tenant_id, pwd, created


def _print_row(tenant_id: str, username: str, password: str, role: str, created: bool) -> None:
    action = "CREATED" if created else "UPDATED"
    print(f"  [{action}] tenant_id={tenant_id}  username={username}  role={role}")
    print(f"           password: {password}")


def main() -> int:
    p = argparse.ArgumentParser(description="Add or update a portal user.")
    p.add_argument("--username")
    p.add_argument("--display-name", default=None)
    p.add_argument("--password", default=None,
                   help="If omitted, a strong 16-char password is generated.")
    p.add_argument("--role", default="admin", choices=["admin", "editor", "viewer", "user"])
    p.add_argument("--bulk", help="CSV file: username,display_name,role")
    args = p.parse_args()

    svc = TenantService()

    if args.bulk:
        path = Path(args.bulk)
        if not path.exists():
            print(f"ERROR: CSV not found: {path}", file=sys.stderr)
            return 2
        print(f"Bulk-creating users from {path}")
        print("-" * 70)
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                username = (row.get("username") or "").strip()
                if not username:
                    continue
                display_name = (row.get("display_name") or "").strip() or username
                role = (row.get("role") or "admin").strip() or "admin"
                tenant_id, pwd, created = upsert_user(
                    svc,
                    username=username,
                    display_name=display_name,
                    role=role,
                    password=None,  # always generate for bulk
                )
                _print_row(tenant_id, username, pwd, role, created)
                count += 1
        print("-" * 70)
        print(f"Done: {count} user(s).  Save these passwords NOW — they are not stored in plaintext.")
        return 0

    if not args.username:
        p.error("--username is required (or use --bulk users.csv)")

    tenant_id, pwd, created = upsert_user(
        svc,
        username=args.username,
        display_name=args.display_name or args.username,
        role=args.role,
        password=args.password,
    )
    print("-" * 70)
    _print_row(tenant_id, args.username, pwd, args.role, created)
    print("-" * 70)
    if not args.password:
        print("Save this password NOW — it is hashed in the DB and cannot be recovered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
