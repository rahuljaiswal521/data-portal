# Authentication

How signing in to the Data Platform Portal works — login, logout, and the profile dropdown.

---

## What you'll need

!!! info "Before you start"
    - A username and password issued by a portal administrator
    - The portal URL: `https://ecran-data-platform-ui.azurewebsites.net` (production) or `http://localhost:3000` (local dev)

If you don't have credentials yet, ask your portal administrator. New users are created via the [User Management](user-management.md) page.

---

## Signing in

1. Go to the portal URL — you'll be redirected to **`/login`** if you don't have an active session
2. Enter your **username** and **password**
3. Click **Sign In**
4. You'll be redirected to the page you originally requested (or the Bronze Dashboard by default)

!!! tip "What happens behind the scenes"
    On a successful login the backend rotates your API key and returns a fresh one. The frontend stores it in `localStorage` under `bp_api_key` and sends it as the `X-API-Key` header on every subsequent request.

If your username or password is wrong you'll see **"Invalid username or password"** — the same message regardless of which one was wrong (this prevents username enumeration).

---

## The profile dropdown

Once signed in, the **avatar badge** in the top-right of the header shows the first letter of your display name on a circular accent background. Clicking it opens a small dropdown with:

| Field | What it shows |
|-------|---------------|
| **Display name** | Your full name as configured by the admin |
| **Role** | `admin`, `editor`, `viewer`, or `user` |
| **Sign out** | Ends your session |

---

## Signing out

Click the avatar badge → **Sign out**. The frontend:

1. Calls `POST /api/v1/auth/logout` (best-effort — stateless)
2. Clears `bp_api_key`, `bp_username`, `bp_display_name`, and `bp_role` from `localStorage`
3. Redirects to `/login`

!!! info "Session model"
    Logout is **stateless** — it doesn't invalidate the API key on the server. The key is implicitly invalidated on your *next* successful login, when a fresh key is minted and the old hash is overwritten. This mirrors the simplicity of Flask-Login while avoiding a session store.

---

## How passwords are stored

| Property | Value |
|----------|-------|
| Hashing algorithm | **bcrypt** (library: `bcrypt>=4.0.0`) |
| Salt | Random per user, stored alongside the hash |
| Maximum effective length | 72 bytes (bcrypt limit — anything longer is truncated) |
| Plaintext storage | **Never.** Passwords are hashed before they touch the database. |
| Password recovery | **Not possible.** Forgotten passwords must be reset by an admin. |

---

## API endpoints (for tooling / scripts)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/auth/login` | Username + password → returns fresh `api_key`, `tenant_id`, `username`, `display_name`, `role` |
| `POST` | `/api/v1/auth/logout` | Stateless ack (`{"success": true}`) |
| `GET` | `/api/v1/auth/me` | Returns profile for the current API key |

### Example: log in from `curl`

```bash
curl -X POST https://ecran-data-platform.azurewebsites.net/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"YourStrongPassword!"}'
```

Response:

```json
{
  "api_key": "bp_…",
  "tenant_id": "alice",
  "username": "alice",
  "display_name": "Alice Smith",
  "role": "admin"
}
```

Use the returned `api_key` as the `X-API-Key` header on subsequent requests.

---

## Roles

The portal currently distinguishes four role values, but **only `admin` is enforced today** — non-admin checks are advisory placeholders for future role-based access control.

| Role | Today | Future (planned) |
|------|-------|------------------|
| `admin` | Full access; only role allowed to create new users via the admin API | Same + manage tenants, secrets, env settings |
| `editor` | Same as `admin` (no enforcement yet) | Create / edit / run sources & entities; no user management |
| `viewer` | Same as `admin` (no enforcement yet) | Read-only access; no create / edit / delete / run |
| `user` | Default fallback role | Same as `viewer` |

See [User Management](user-management.md) for how to assign roles.

---

## Traditional approach vs. portal

| Task | Traditional approach | With the Portal |
|------|---------------------|-----------------|
| Set up team-wide auth | Wire OAuth / SAML, manage IdP integration, write middleware = days | Username + password, ships in the box = zero config |
| Onboard a new engineer | File a ticket with IT for IdP groups, wait 1-2 days | One `POST /auth/admin/users` call = under a minute |

!!! success "Time saved"
    Traditional approach: 2-3 days of plumbing for SSO, plus per-user IT tickets.
    With the portal: **bcrypt + API key rotation works out of the box — onboard a teammate in seconds**.

---

## Related

- [User Management](user-management.md) — how admins create accounts
- [Getting Started](getting-started.md) — first-login walkthrough and navigation
