"""Tests for the username+password auth flow.

Two layers:
1. TenantService unit tests for hash/verify/credentials/profile/api-key rotation/seeding.
2. HTTP endpoint tests for POST /auth/login, POST /auth/logout, GET /auth/me.

Uses the shared `client` and `mock_tenant` fixtures from conftest.py — those
already redirect tenant_db_path to a tmp file and disable rag_require_auth.
"""

from app.services.tenant_service import TenantService


# ════════════════════════════════════════════════════════════════════════
# 1. TenantService — password hashing primitives
# ════════════════════════════════════════════════════════════════════════


class TestPasswordHashing:
    def test_hash_then_verify_roundtrip(self):
        h = TenantService.hash_password("hunter2")
        assert TenantService.verify_password("hunter2", h) is True

    def test_verify_wrong_password_returns_false(self):
        h = TenantService.hash_password("right")
        assert TenantService.verify_password("wrong", h) is False

    def test_verify_with_empty_hash_returns_false(self):
        assert TenantService.verify_password("anything", "") is False

    def test_verify_with_none_hash_returns_false(self):
        assert TenantService.verify_password("anything", None) is False

    def test_verify_with_garbage_hash_returns_false(self):
        # bcrypt raises on bad input — verify_password must swallow it.
        assert TenantService.verify_password("anything", "not-a-bcrypt-hash") is False

    def test_long_password_is_truncated_consistently(self):
        # bcrypt only looks at the first 72 bytes. Hashing a 200-byte password
        # then verifying with that same prefix should still succeed.
        long_pw = "a" * 200
        h = TenantService.hash_password(long_pw)
        # Same prefix verifies
        assert TenantService.verify_password("a" * 72, h) is True
        # Strings differing only after byte 72 should also verify (truncation)
        assert TenantService.verify_password("a" * 100, h) is True


# ════════════════════════════════════════════════════════════════════════
# 2. TenantService — credentials, login flow, profile
# ════════════════════════════════════════════════════════════════════════


class TestSetCredentials:
    def test_set_credentials_persists_username_and_password(self, mock_tenant):
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_credentials(
            "default", "alice", "secret123", display_name="Alice", role="admin"
        )

        prof = mock_tenant.get_user_profile("default")
        assert prof["username"] == "alice"
        assert prof["display_name"] == "Alice"
        assert prof["role"] == "admin"

    def test_set_credentials_with_display_name_none_keeps_existing(self, mock_tenant):
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_credentials(
            "default", "alice", "p1", display_name="Alice", role="user"
        )
        # Now update with display_name=None — should NOT overwrite via COALESCE
        mock_tenant.set_credentials(
            "default", "alice", "p2", display_name=None, role="user"
        )
        prof = mock_tenant.get_user_profile("default")
        assert prof["display_name"] == "Alice"

    def test_set_credentials_changes_password(self, mock_tenant):
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_credentials("default", "alice", "old_pw")
        assert mock_tenant.verify_credentials("alice", "old_pw") == "default"
        mock_tenant.set_credentials("default", "alice", "new_pw")
        assert mock_tenant.verify_credentials("alice", "old_pw") is None
        assert mock_tenant.verify_credentials("alice", "new_pw") == "default"


class TestVerifyCredentials:
    def test_returns_tenant_id_on_correct_creds(self, mock_tenant):
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_credentials("default", "alice", "pw")
        assert mock_tenant.verify_credentials("alice", "pw") == "default"

    def test_returns_none_on_wrong_password(self, mock_tenant):
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_credentials("default", "alice", "pw")
        assert mock_tenant.verify_credentials("alice", "WRONG") is None

    def test_returns_none_on_unknown_username(self, mock_tenant):
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_credentials("default", "alice", "pw")
        assert mock_tenant.verify_credentials("ghost", "pw") is None

    def test_returns_none_when_tenant_disabled(self, mock_tenant):
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_credentials("default", "alice", "pw")
        # Manually disable
        with mock_tenant._get_conn() as conn:
            conn.execute("UPDATE tenants SET enabled = 0 WHERE id = 'default'")
        assert mock_tenant.verify_credentials("alice", "pw") is None


class TestUpdateLastLogin:
    def test_update_last_login_writes_timestamp(self, mock_tenant):
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_credentials("default", "alice", "pw")
        assert mock_tenant.get_user_profile("default")["last_login"] is None
        mock_tenant.update_last_login("default")
        ts = mock_tenant.get_user_profile("default")["last_login"]
        assert ts is not None
        # ISO-format with 'T' separator
        assert "T" in ts

    def test_update_last_login_repeats(self, mock_tenant):
        import time
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_credentials("default", "alice", "pw")
        mock_tenant.update_last_login("default")
        first = mock_tenant.get_user_profile("default")["last_login"]
        time.sleep(1.1)  # Resolution is seconds
        mock_tenant.update_last_login("default")
        second = mock_tenant.get_user_profile("default")["last_login"]
        assert second >= first


class TestGetUserProfile:
    def test_returns_expected_dict_shape(self, mock_tenant):
        mock_tenant.ensure_default_tenant()
        mock_tenant.set_credentials(
            "default", "alice", "pw", display_name="Alice", role="admin"
        )
        prof = mock_tenant.get_user_profile("default")
        assert set(prof.keys()) == {
            "tenant_id", "username", "display_name", "role", "last_login"
        }
        assert prof["tenant_id"] == "default"
        assert prof["username"] == "alice"
        assert prof["display_name"] == "Alice"
        assert prof["role"] == "admin"

    def test_display_name_falls_back_to_username(self, mock_tenant):
        mock_tenant.ensure_default_tenant()
        # COALESCE keeps display_name NULL when none ever set.
        mock_tenant.set_credentials("default", "alice", "pw", display_name=None)
        prof = mock_tenant.get_user_profile("default")
        assert prof["display_name"] == "alice"

    def test_role_defaults_to_user(self, mock_tenant):
        mock_tenant.ensure_default_tenant()
        # New tenant created via ensure_default_tenant has no role set explicitly,
        # but the schema default 'user' should apply at read time.
        prof = mock_tenant.get_user_profile("default")
        assert prof["role"] == "user"

    def test_returns_none_for_unknown_tenant(self, mock_tenant):
        assert mock_tenant.get_user_profile("does-not-exist") is None


# ════════════════════════════════════════════════════════════════════════
# 3. TenantService — API key rotation
# ════════════════════════════════════════════════════════════════════════


class TestApiKeyRotation:
    def test_get_api_key_returns_bp_prefixed_token(self, mock_tenant):
        mock_tenant.ensure_default_tenant()
        key = mock_tenant.get_api_key_for_tenant("default")
        assert key is not None
        assert key.startswith("bp_")
        assert len(key) > 10

    def test_old_key_invalidated_after_rotation(self, mock_tenant):
        mock_tenant.ensure_default_tenant()
        # The default tenant was seeded with an unknown key — mint one we can track.
        first = mock_tenant.get_api_key_for_tenant("default")
        assert mock_tenant.validate_api_key(first) == "default"

        second = mock_tenant.get_api_key_for_tenant("default")
        assert mock_tenant.validate_api_key(second) == "default"
        # Old key now rejected
        assert mock_tenant.validate_api_key(first) is None

    def test_rotation_yields_distinct_keys(self, mock_tenant):
        mock_tenant.ensure_default_tenant()
        a = mock_tenant.get_api_key_for_tenant("default")
        b = mock_tenant.get_api_key_for_tenant("default")
        assert a != b


# ════════════════════════════════════════════════════════════════════════
# 4. TenantService — ensure_default_admin seeding
# ════════════════════════════════════════════════════════════════════════


class TestEnsureDefaultAdmin:
    def test_seeds_with_explicit_password(self, mock_tenant):
        result = mock_tenant.ensure_default_admin("admin", "supplied_pw")
        # Returns None when password is supplied (no need to surface it).
        assert result is None
        assert mock_tenant.verify_credentials("admin", "supplied_pw") == "default"

    def test_seeds_with_generated_password_when_none(self, mock_tenant):
        result = mock_tenant.ensure_default_admin("admin", None)
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
        assert mock_tenant.verify_credentials("admin", result) == "default"

    def test_seeds_admin_role_and_administrator_display_name(self, mock_tenant):
        mock_tenant.ensure_default_admin("admin", "pw")
        prof = mock_tenant.get_user_profile("default")
        assert prof["role"] == "admin"
        assert prof["display_name"] == "Administrator"

    def test_does_nothing_if_already_seeded(self, mock_tenant):
        mock_tenant.ensure_default_admin("admin", "pw1")
        # Second call must not change credentials and must return None.
        result = mock_tenant.ensure_default_admin("admin", "pw2")
        assert result is None
        # Original password still works
        assert mock_tenant.verify_credentials("admin", "pw1") == "default"
        assert mock_tenant.verify_credentials("admin", "pw2") is None


# ════════════════════════════════════════════════════════════════════════
# 5. HTTP endpoints — POST /auth/login
# ════════════════════════════════════════════════════════════════════════


def _seed_admin(mock_tenant, username="admin", password="pw"):
    """Seed credentials directly via set_credentials.

    NOTE: We can't use ensure_default_admin here because the FastAPI lifespan
    has already run during the `client` fixture's TestClient context entry —
    that call seeds 'admin' with a generated password and would no-op our seed.
    set_credentials always overwrites, so it's the right primitive for tests.
    """
    mock_tenant.ensure_default_tenant()
    mock_tenant.set_credentials(
        "default",
        username=username,
        password=password,
        display_name="Administrator",
        role="admin",
    )


class TestLoginEndpoint:
    def test_login_happy_path_returns_full_response(self, client, mock_tenant):
        _seed_admin(mock_tenant, "admin", "secret")
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "secret"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["api_key"].startswith("bp_")
        assert body["tenant_id"] == "default"
        assert body["username"] == "admin"
        assert body["display_name"] == "Administrator"
        assert body["role"] == "admin"

    def test_login_updates_last_login(self, client, mock_tenant):
        _seed_admin(mock_tenant, "admin", "secret")
        # Pre-condition: last_login is None
        assert mock_tenant.get_user_profile("default")["last_login"] is None

        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "secret"},
        )
        assert resp.status_code == 200
        api_key = resp.json()["api_key"]

        # Verify via /auth/me
        me = client.get("/api/v1/auth/me", headers={"X-API-Key": api_key})
        assert me.status_code == 200
        assert me.json()["last_login"] is not None

    def test_login_wrong_password_returns_401(self, client, mock_tenant):
        _seed_admin(mock_tenant, "admin", "secret")
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "WRONG"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid username or password"

    def test_login_unknown_username_returns_same_message(self, client, mock_tenant):
        _seed_admin(mock_tenant, "admin", "secret")
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "ghost", "password": "anything"},
        )
        assert resp.status_code == 401
        # Same message — no enumeration leak
        assert resp.json()["detail"] == "Invalid username or password"

    def test_login_missing_username_returns_422(self, client):
        resp = client.post("/api/v1/auth/login", json={"password": "x"})
        assert resp.status_code == 422

    def test_login_missing_password_returns_422(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "admin"})
        assert resp.status_code == 422

    def test_login_empty_body_returns_422(self, client):
        resp = client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422

    def test_login_rotates_api_key_each_time(self, client, mock_tenant):
        _seed_admin(mock_tenant, "admin", "secret")
        first = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "secret"},
        ).json()["api_key"]
        second = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "secret"},
        ).json()["api_key"]
        assert first != second

        # The previous key is now invalid for /auth/me (lookups go via tenant_id).
        # Validate via the tenant service directly.
        assert mock_tenant.validate_api_key(first) is None
        assert mock_tenant.validate_api_key(second) == "default"

    def test_login_disabled_tenant_returns_401(self, client, mock_tenant):
        _seed_admin(mock_tenant, "admin", "secret")
        with mock_tenant._get_conn() as conn:
            conn.execute("UPDATE tenants SET enabled = 0 WHERE id = 'default'")

        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "secret"},
        )
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════════
# 6. HTTP endpoints — GET /auth/me
# ════════════════════════════════════════════════════════════════════════


class TestMeEndpoint:
    def test_me_with_valid_api_key_returns_profile(self, client, mock_tenant):
        _seed_admin(mock_tenant, "admin", "secret")
        api_key = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "secret"},
        ).json()["api_key"]

        resp = client.get("/api/v1/auth/me", headers={"X-API-Key": api_key})
        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant_id"] == "default"
        assert body["username"] == "admin"
        assert body["display_name"] == "Administrator"
        assert body["role"] == "admin"

    def test_me_without_api_key_in_local_dev_uses_default(self, client, mock_tenant):
        # rag_require_auth=False (set in conftest isolate_settings) — no header
        # falls back to default tenant. Profile may be empty/null fields, but call
        # must succeed.
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "default"

    def test_me_with_invalid_api_key_in_local_dev_falls_back_to_default(
        self, client, mock_tenant
    ):
        resp = client.get(
            "/api/v1/auth/me", headers={"X-API-Key": "bp_invalid_key"}
        )
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "default"


# ════════════════════════════════════════════════════════════════════════
# 7. HTTP endpoints — POST /auth/logout
# ════════════════════════════════════════════════════════════════════════


class TestLogoutEndpoint:
    def test_logout_returns_success_true(self, client):
        resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
        assert resp.json() == {"success": True}

    def test_logout_without_auth_still_works(self, client):
        # Stateless — no auth required.
        resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 200

    def test_logout_with_invalid_key_still_returns_200(self, client):
        resp = client.post(
            "/api/v1/auth/logout", headers={"X-API-Key": "garbage"}
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
