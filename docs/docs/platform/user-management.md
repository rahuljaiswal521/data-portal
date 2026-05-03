# User Management

How portal administrators create and manage user accounts.

---

## What you'll need

!!! info "Before you start"
    - An existing **admin** account (the very first admin is seeded from `PORTAL_ADMIN_USERNAME` / `PORTAL_ADMIN_PASSWORD` on the App Service at startup)
    - The username and display name of each teammate you want to onboard

!!! warning "There is no admin UI yet"
    User creation is currently performed via the **REST API** or a CLI script bundled with the backend container. A web-based user-management page is on the roadmap.

---

## How users are stored

The portal keeps user accounts in the same SQLite **`tenants`** table that the bronze framework already uses for API-key authentication. Each user is one row.

| Column | Meaning |
|--------|---------|
| `id` | Tenant ID — derived from the username (lowercased, non-alphanumerics → `_`) |
| `username` | Login username (case-sensitive on lookup) |
| `password_hash` | bcrypt hash of the password |
| `display_name` | Friendly name shown in the avatar dropdown |
| `role` | `admin` / `editor` / `viewer` / `user` |
| `enabled` | `1` = can log in; `0` = blocked |
| `last_login` | ISO-8601 timestamp of last successful login |
| `api_key_hash` | SHA-256 of the most recently issued API key (rotated on every login) |

In Azure, this database lives at `/data/app/tenants.db` on a mounted Azure File Share, so user accounts persist across container restarts and re-deploys.

---

## Three ways to create a user

=== "Admin API (recommended)"

    The simplest method — works from any machine that can reach the backend, requires no SSH or container access.

    ```bash
    # 1. Log in as admin to get a fresh API key
    API_KEY=$(curl -s -X POST https://ecran-data-platform.azurewebsites.net/api/v1/auth/login \
      -H "Content-Type: application/json" \
      -d '{"username":"admin","password":"YOUR_ADMIN_PASSWORD"}' \
      | python -c "import sys,json;print(json.load(sys.stdin)['api_key'])")

    # 2. Create the user
    curl -X POST https://ecran-data-platform.azurewebsites.net/api/v1/auth/admin/users \
      -H "X-API-Key: $API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "username":     "alice",
        "password":     "StrongPassword!23",
        "display_name": "Alice Smith",
        "role":         "admin"
      }'
    ```

    Response:

    ```json
    {
      "tenant_id":    "alice",
      "username":     "alice",
      "display_name": "Alice Smith",
      "role":         "admin",
      "created":      true
    }
    ```

    The endpoint is **idempotent** — calling it again with the same `username` rotates the password / display_name / role on the existing row and returns `"created": false`.

=== "CLI script (inside the container)"

    The backend image ships with `scripts/add_user.py` at `/app/scripts/`. Use this if you have shell access to the container.

    Single user:

    ```bash
    python -m scripts.add_user --username alice --display-name "Alice Smith" --role admin
    # If --password is omitted, a strong 16-char password is generated and printed once.
    ```

    Bulk from CSV:

    ```bash
    cat > users.csv <<EOF
    username,display_name,role
    alice,Alice Smith,admin
    bob,Bob Jones,admin
    EOF
    python -m scripts.add_user --bulk users.csv
    ```

    The script picks up `TENANT_DB_PATH` from the same settings the app uses, so it always writes to the correct database.

=== "Direct SQL (last resort)"

    If both methods are unavailable (e.g. the backend isn't running), you can manipulate the SQLite database directly:

    ```python
    import bcrypt, sqlite3, secrets, hashlib
    db = sqlite3.connect("/data/app/tenants.db")
    db.row_factory = sqlite3.Row

    pwd_hash = bcrypt.hashpw(b"StrongPassword!23", bcrypt.gensalt()).decode()
    api_key  = f"bp_{secrets.token_urlsafe(32)}"
    api_hash = hashlib.sha256(api_key.encode()).hexdigest()

    db.execute(
      "INSERT INTO tenants (id, name, api_key_hash, username, password_hash, display_name, role) "
      "VALUES (?, ?, ?, ?, ?, ?, ?)",
      ("alice", "Alice Smith", api_hash, "alice", pwd_hash, "Alice Smith", "admin"),
    )
    db.commit()
    ```

    Avoid this unless absolutely necessary — it bypasses the application logic.

---

## The admin endpoint reference

`POST /api/v1/auth/admin/users`

### Authentication

- Requires the **`X-API-Key`** header
- Must resolve to a tenant with **`role = "admin"`**
- Missing key → `401 Missing X-API-Key header`
- Invalid key → `401 Invalid API key`
- Non-admin role → `403 Admin role required`

!!! warning "Strict auth"
    Unlike most other portal endpoints, this admin endpoint **does not** fall back to the `default` tenant when `RAG_REQUIRE_AUTH=False`. It always requires an explicit, valid API key. (This was a deliberate hardening after a bypass was found and patched during initial deployment.)

### Request body

```typescript
{
  username:     string;          // 1-100 chars, becomes tenant_id (lowercased + slugified)
  password:     string;          // 8-200 chars; bcrypt-hashed before storage
  display_name: string | null;   // optional; defaults to username
  role:         "admin" | "editor" | "viewer" | "user";  // defaults to "admin"
}
```

### Response (200 OK)

```typescript
{
  tenant_id:    string;
  username:     string;
  display_name: string | null;
  role:         string;
  created:      boolean;   // true if a new row was inserted; false if updated
}
```

---

## Resetting a password

The same endpoint also handles password resets — calling it with an existing `username` overwrites the password hash:

```bash
curl -X POST https://…/api/v1/auth/admin/users \
  -H "X-API-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"NewStrongPassword!","display_name":"Alice Smith","role":"admin"}'
```

The response will have `"created": false` to indicate it was an update rather than a new row.

---

## Disabling a user

There is no dedicated disable endpoint yet. Two practical workarounds:

1. **Rotate the password** to a long random string nobody knows (effectively prevents login)
2. **Direct SQL** — `UPDATE tenants SET enabled = 0 WHERE id = 'alice';` (the login query filters on `enabled = 1`, so the user can no longer authenticate)

A proper disable endpoint will arrive with the user-management UI.

---

## The first admin (seeded at startup)

When the backend starts, it reads two environment variables and ensures a default admin exists:

| Env var | Default | Notes |
|---------|---------|-------|
| `PORTAL_ADMIN_USERNAME` | `admin` | Username for the seeded admin |
| `PORTAL_ADMIN_PASSWORD` | _(unset)_ | If set, **and the default tenant has no credentials yet**, these are written on startup. After credentials exist, this variable is ignored — to change the password, use the admin API. |

In Azure, set both via:

```bash
az webapp config appsettings set \
  --resource-group ecran-rg \
  --name ecran-data-platform \
  --settings PORTAL_ADMIN_USERNAME=admin PORTAL_ADMIN_PASSWORD='YourStrongPassword!'
```

Then restart the backend. The startup log line `[AUTH] Seeded default admin: admin` confirms it took effect.

---

## Traditional approach vs. portal

| Task | Traditional approach | With the Portal |
|------|---------------------|-----------------|
| Onboard 5 teammates | File 5 IT tickets for AD groups, wait 1-2 days each, set up MFA enrolment links… | One bash loop calling `/auth/admin/users` 5 times = under a minute |
| Reset a forgotten password | Find the right SSO admin console, hunt for the user, generate a temporary password, email it… | One curl call rotating the password |
| Audit who has access | Cross-check AD group membership in three places | `SELECT id, username, role, last_login FROM tenants` |

!!! success "Time saved"
    Traditional approach: ~2-3 days from "we need to onboard the team" to "everyone can log in", per round.
    With the portal: **roughly 60 seconds for 5 users**, all stored in one transparent SQLite table.

---

## Security checklist

- [x] Passwords are bcrypt-hashed before storage (no plaintext)
- [x] API keys are stored as SHA-256 hashes (the plaintext is shown only once at login)
- [x] API keys are rotated on every successful login
- [x] Admin endpoint requires explicit valid `X-API-Key` (no fallback to default tenant)
- [x] Login uses constant-message error to prevent username enumeration
- [ ] Multi-factor authentication (planned)
- [ ] Per-role endpoint enforcement beyond admin (planned)
- [ ] Audit log of admin actions (planned)

---

## Related

- [Authentication](authentication.md) — how end-users log in and out
- [Getting Started](getting-started.md) — first-login walkthrough
