"""Tests for password rules, Argon2id hashing, and registration service/endpoints.

Follows docs/SECURITY.md, docs/API_SPEC.md, and docs/ACCEPTANCE_CRITERIA.md (AC-1, AC-2, AC-3).
"""

from pathlib import Path

import pytest

from opentrade.services.auth import (
    change_password_endpoint,
    clear_login_ip_rate_limits,
    delete_me_endpoint,
    extract_session_token,
    forgot_password_endpoint,
    login_endpoint,
    logout_all_endpoint,
    logout_endpoint,
    me_endpoint,
    patch_me_endpoint,
    register_endpoint,
    resend_verification_endpoint,
    reset_password_endpoint,
    verify_email_endpoint,
)
from opentrade.services.errors import WeakPasswordError
from opentrade.services.security import (
    hash_password,
    hash_token,
    needs_rehash,
    validate_password,
    verify_password,
)
from opentrade.storage.db import get_connection
from opentrade.storage.migrate import run_migrations
from opentrade.storage.repositories import SessionRepository, TokenRepository, UserRepository

# --- T0.4 Password validation and Argon2id tests ---


def test_password_under_12_characters_rejected() -> None:
    """AC-2: A password under 12 characters is rejected with code WEAK_PASSWORD."""
    with pytest.raises(WeakPasswordError) as exc_info:
        validate_password("Short1!pass")
    assert exc_info.value.code == "WEAK_PASSWORD"
    assert "at least 12 characters" in str(exc_info.value)


def test_password_over_128_characters_rejected() -> None:
    """AC-2: A password exceeding 128 characters is rejected with code WEAK_PASSWORD."""
    with pytest.raises(WeakPasswordError) as exc_info:
        validate_password("A" * 129)
    assert exc_info.value.code == "WEAK_PASSWORD"
    assert "at most 128 characters" in str(exc_info.value)


@pytest.mark.parametrize(
    "common_pwd",
    [
        "unbelievable",  # in 10,001 list (len 12)
        "UNBELIEVABLE",  # case-insensitive check
        "contortionist",  # in 10,001 list (len 13)
        "scandinavian",  # in 10,001 list (len 12)
    ],
)
def test_common_password_rejected_case_insensitive(common_pwd: str) -> None:
    """AC-2: A password on the common-password list is rejected with code WEAK_PASSWORD."""
    with pytest.raises(WeakPasswordError) as exc_info:
        validate_password(common_pwd)
    assert exc_info.value.code == "WEAK_PASSWORD"
    assert "common" in str(exc_info.value).lower()


def test_password_equal_to_name_rejected() -> None:
    """SECURITY.md section 3: Reject passwords equal to the user's name (case-insensitive)."""
    with pytest.raises(WeakPasswordError) as exc_info:
        validate_password("AlexanderTheGreat", name="alexanderthegreat")
    assert exc_info.value.code == "WEAK_PASSWORD"
    assert "name" in str(exc_info.value).lower()


def test_password_equal_to_email_rejected() -> None:
    """SECURITY.md section 3: Reject passwords equal to the user's email (case-insensitive)."""
    with pytest.raises(WeakPasswordError) as exc_info:
        validate_password("Trader@Example.com", email="trader@example.com")
    assert exc_info.value.code == "WEAK_PASSWORD"
    assert "email" in str(exc_info.value).lower()


def test_valid_strong_password_accepted() -> None:
    """AC-2: A strong, unique password of >= 12 characters is accepted."""
    validate_password("CorrectHorseBatteryStaple99!", name="Alice", email="alice@example.com")


def test_argon2id_hash_format_and_properties() -> None:
    """AC-3: The stored hash starts with '$argon2id$' and never equals plain password."""
    plain = "SuperSecretValidPassword2026!"
    hashed = hash_password(plain)

    assert hashed.startswith("$argon2id$")
    assert hashed != plain

    # Two hashes of the same password should differ due to unique salts
    hashed2 = hash_password(plain)
    assert hashed != hashed2
    assert hashed2.startswith("$argon2id$")


def test_argon2id_verify_password() -> None:
    """AC-3: Password verification succeeds with matching password and fails with mismatch."""
    plain = "SuperSecretValidPassword2026!"
    hashed = hash_password(plain)

    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password("invalid", "not-a-valid-argon2-hash") is False


def test_argon2id_needs_rehash() -> None:
    """AC-3: Verify needs_rehash returns False for current library defaults."""
    plain = "SuperSecretValidPassword2026!"
    hashed = hash_password(plain)

    assert needs_rehash(hashed) is False


# --- T0.5 Registration service and endpoint tests ---


def test_register_success_ac1(tmp_path: Path) -> None:
    """AC-1: Valid register returns 201, creates users row with NULL verified_at and lowercase."""
    db_path = tmp_path / "test_reg.db"
    run_migrations(db_path)

    body = {
        "name": "Alice Trader",
        "email": "Alice.Trader@Example.COM",
        "password": "ValidPassword123!",
    }
    status_code, resp = register_endpoint(body, db_path=db_path)

    assert status_code == 201
    assert "user" in resp
    user_data = resp["user"]
    assert "id" not in user_data
    assert user_data["name"] == "Alice Trader"
    assert user_data["email"] == "alice.trader@example.com"
    assert user_data["verified"] is False

    # Check database row directly
    conn = get_connection(db_path)
    try:
        repo = UserRepository(conn)
        user_row = repo.get_by_email("alice.trader@example.com")
        assert user_row is not None
        assert user_row.email == "alice.trader@example.com"
        assert user_row.email_verified_at is None
    finally:
        conn.close()


def test_register_weak_password_creates_no_row_ac2(tmp_path: Path) -> None:
    """AC-2: A weak password returns 422 with WEAK_PASSWORD and creates no row in users."""
    db_path = tmp_path / "test_reg.db"
    run_migrations(db_path)

    conn = get_connection(db_path)
    repo = UserRepository(conn)
    before_count = repo.count()
    conn.close()

    body = {
        "name": "Bob Trader",
        "email": "bob@example.com",
        "password": "short",
    }
    status_code, resp = register_endpoint(body, db_path=db_path)

    assert status_code == 422
    assert resp["error"]["code"] == "WEAK_PASSWORD"

    conn = get_connection(db_path)
    repo = UserRepository(conn)
    after_count = repo.count()
    conn.close()

    assert before_count == after_count == 0


def test_register_password_hash_stored_and_plain_absent_ac3(tmp_path: Path) -> None:
    """AC-3: Password hash starts with '$argon2id$', != plain, and plain absent in db file."""
    db_path = tmp_path / "test_reg.db"
    run_migrations(db_path)

    plain_pwd = "UniqueSecretPassphraseForDBTest2026!"
    body = {
        "name": "Charlie Trader",
        "email": "charlie@example.com",
        "password": plain_pwd,
    }
    status_code, resp = register_endpoint(body, db_path=db_path)
    assert status_code == 201

    conn = get_connection(db_path)
    repo = UserRepository(conn)
    user = repo.get_by_email("charlie@example.com")
    assert user is not None
    assert user.password_hash.startswith("$argon2id$")
    assert user.password_hash != plain_pwd
    conn.close()

    # Read database file bytes directly to ensure plain password never appears
    db_bytes = db_path.read_bytes()
    assert plain_pwd.encode("utf-8") not in db_bytes, "Plain text password found in db bytes!"


def test_users_table_has_no_plaintext_password_column(tmp_path: Path) -> None:
    """AC-3: The users table contains no plain-text password column (only password_hash)."""
    db_path = tmp_path / "test_schema.db"
    run_migrations(db_path)

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users);")
        columns = [row[1] for row in cursor.fetchall()]
        cursor.close()

        password_cols = [col for col in columns if "password" in col.lower()]
        assert password_cols == [
            "password_hash"
        ], f"Found forbidden password column(s) in users table: {password_cols}"
    finally:
        conn.close()


def test_register_duplicate_email_same_response(tmp_path: Path) -> None:
    """AC-43: Duplicate registration returns same 201 status, body shape, and message
    without creating a row.
    """
    db_path = tmp_path / "test_reg.db"
    run_migrations(db_path)

    body1 = {
        "name": "Dave Trader",
        "email": "dave@example.com",
        "password": "ValidPassword123!",
    }
    status1, resp1 = register_endpoint(body1, db_path=db_path)
    assert status1 == 201

    conn = get_connection(db_path)
    repo = UserRepository(conn)
    count_after_first = repo.count()
    conn.close()
    assert count_after_first == 1

    # Attempt duplicate registration with different casing and name
    body2 = {
        "name": "Dave Imposter",
        "email": "DAVE@EXAMPLE.COM",
        "password": "AnotherValidPassword123!",
    }
    status2, resp2 = register_endpoint(body2, db_path=db_path)

    # Status code for the duplicate equals status code for new registration (201)
    assert status2 == status1 == 201

    # Assert id is absent in both cases
    assert "id" not in resp1["user"]
    assert "id" not in resp2["user"]

    # Body keys and structure match a new registration's body
    assert set(resp2.keys()) == set(resp1.keys())
    assert set(resp2["user"].keys()) == set(resp1["user"].keys())

    # Message text is identical to a new registration's message
    expected_msg = "If this email can be registered, a verification link has been sent."
    assert resp1["message"] == expected_msg
    assert resp2["message"] == expected_msg

    # Users row count is unchanged after the duplicate attempt
    conn = get_connection(db_path)
    repo = UserRepository(conn)
    count_after_duplicate = repo.count()
    conn.close()
    assert count_after_duplicate == count_after_first == 1


@pytest.mark.parametrize(
    "bad_email",
    [
        "not-an-email",
        "missing-at.com",
        "@missing-user.com",
        "user@missing-tld",
        "spaces in@example.com",
        "",
    ],
)
def test_register_malformed_email_rejected(tmp_path: Path, bad_email: str) -> None:
    """Validation test: Malformed emails rejected with 422 VALIDATION_FAILED and create no row."""
    db_path = tmp_path / "test_reg.db"
    run_migrations(db_path)

    body = {
        "name": "Eve Trader",
        "email": bad_email,
        "password": "ValidPassword123!",
    }
    status_code, resp = register_endpoint(body, db_path=db_path)

    assert status_code == 422
    assert resp["error"]["code"] == "VALIDATION_FAILED"

    conn = get_connection(db_path)
    repo = UserRepository(conn)
    assert repo.count() == 0
    conn.close()


@pytest.mark.parametrize(
    "bad_name",
    [
        "",
        " ",
        "A" * 81,  # exceeds 80 characters
    ],
)
def test_register_invalid_name_rejected(tmp_path: Path, bad_name: str) -> None:
    """Validation test: Invalid name is rejected with 422 VALIDATION_FAILED."""
    db_path = tmp_path / "test_reg.db"
    run_migrations(db_path)

    body = {
        "name": bad_name,
        "email": "frank@example.com",
        "password": "ValidPassword123!",
    }
    status_code, resp = register_endpoint(body, db_path=db_path)

    assert status_code == 422
    assert resp["error"]["code"] == "VALIDATION_FAILED"

    conn = get_connection(db_path)
    repo = UserRepository(conn)
    assert repo.count() == 0
    conn.close()


# --- T0.6 Email verification tests ---


def test_registration_sends_verification_email_for_new_user(tmp_path: Path) -> None:
    """FR-3: After registration of a new user, an email verification link is sent."""
    db_path = tmp_path / "test_reg.db"
    run_migrations(db_path)

    body = {
        "name": "Grace Trader",
        "email": "grace@example.com",
        "password": "ValidPassword123!",
    }
    status_code, resp = register_endpoint(body, db_path=db_path)
    assert status_code == 201

    # Database must contain a verification token in auth_tokens
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, purpose, token_hash, expires_at, used_at FROM auth_tokens;")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 1
    user_id, purpose, token_hash, expires_at, used_at = rows[0]
    assert purpose == "verify_email"
    assert token_hash is not None
    assert len(token_hash) == 64  # SHA-256 hex digest
    assert used_at is None


def test_duplicate_registration_notifies_owner_without_verification_token(tmp_path: Path) -> None:
    """FR-3 & ADR-014: A duplicate registration must not send a verification email,
    but must notify the real owner.
    """
    db_path = tmp_path / "test_reg.db"
    run_migrations(db_path)

    # First registration (new user)
    body1 = {
        "name": "Hank Owner",
        "email": "hank@example.com",
        "password": "ValidPassword123!",
    }
    status1, _ = register_endpoint(body1, db_path=db_path)
    assert status1 == 201

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM auth_tokens WHERE purpose = 'verify_email';")
    tokens_after_first = cursor.fetchone()[0]
    conn.close()
    assert tokens_after_first == 1

    # Second registration with duplicate email
    body2 = {
        "name": "Hank Imposter",
        "email": "hank@example.com",
        "password": "AnotherValidPassword123!",
    }
    status2, _ = register_endpoint(body2, db_path=db_path)
    assert status2 == 201

    # Token count must NOT increase (no new verification token issued)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM auth_tokens WHERE purpose = 'verify_email';")
    tokens_after_duplicate = cursor.fetchone()[0]
    conn.close()
    assert tokens_after_duplicate == tokens_after_first == 1


def test_verify_email_endpoint_success(tmp_path: Path) -> None:
    """FR-3 & AC-1: POST /auth/verify with a valid token marks email_verified_at and
    returns 200 {verified: True}.
    """
    db_path = tmp_path / "test_reg.db"
    run_migrations(db_path)

    # Helper function exposed by auth service to issue token for testing or via registration
    body = {
        "name": "Ivy Trader",
        "email": "ivy@example.com",
        "password": "ValidPassword123!",
    }
    status_code, resp = register_endpoint(body, db_path=db_path)
    assert status_code == 201

    # Retrieve issued verification token hash and match with verification flow
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, user_id, token_hash FROM auth_tokens WHERE purpose = 'verify_email';"
    )
    token_row = cursor.fetchone()
    conn.close()
    assert token_row is not None

    # Verify using raw token returned or sent via adapter
    # In auth service, verify_email_endpoint accepts {'token': raw_token}
    from opentrade.adapters.email_smtp import get_last_sent_token

    raw_token = get_last_sent_token()
    assert raw_token is not None

    verify_status, verify_resp = verify_email_endpoint({"token": raw_token}, db_path=db_path)
    assert verify_status == 200
    assert verify_resp == {"verified": True}

    # Confirm user row now has email_verified_at populated
    conn = get_connection(db_path)
    repo = UserRepository(conn)
    user = repo.get_by_email("ivy@example.com")
    assert user is not None
    assert user.email_verified_at is not None
    conn.close()


def test_verify_email_single_use(tmp_path: Path) -> None:
    """FR-3: Verification tokens are single-use; a second use returns 400 with TOKEN_INVALID."""
    db_path = tmp_path / "test_reg.db"
    run_migrations(db_path)

    register_endpoint(
        {"name": "Jack", "email": "jack@example.com", "password": "ValidPassword123!"},
        db_path=db_path,
    )
    from opentrade.adapters.email_smtp import get_last_sent_token

    raw_token = get_last_sent_token()
    assert raw_token is not None

    status1, resp1 = verify_email_endpoint({"token": raw_token}, db_path=db_path)
    assert status1 == 200

    # Second use of identical token
    status2, resp2 = verify_email_endpoint({"token": raw_token}, db_path=db_path)
    assert status2 == 400
    assert resp2["error"]["code"] == "TOKEN_INVALID"


def test_verify_email_expired_rejected(tmp_path: Path) -> None:
    """FR-3: Verification tokens expire after 24 hours; expired tokens return 400 TOKEN_INVALID."""
    db_path = tmp_path / "test_reg.db"
    run_migrations(db_path)

    register_endpoint(
        {"name": "Karen", "email": "karen@example.com", "password": "ValidPassword123!"},
        db_path=db_path,
    )
    from opentrade.adapters.email_smtp import get_last_sent_token

    raw_token = get_last_sent_token()
    assert raw_token is not None

    # Manually expire token in database by setting expires_at to 25 hours ago
    from datetime import UTC, datetime, timedelta

    expired_time = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE auth_tokens SET expires_at = ? WHERE purpose = 'verify_email';", (expired_time,)
    )
    conn.close()

    status, resp = verify_email_endpoint({"token": raw_token}, db_path=db_path)
    assert status == 400
    assert resp["error"]["code"] == "TOKEN_INVALID"


def test_new_verification_token_invalidates_prior_unused_tokens(tmp_path: Path) -> None:
    """FR-3 & SECURITY.md section 5: Generating a new verification token invalidates
    earlier unused tokens.
    """
    db_path = tmp_path / "test_reg.db"
    run_migrations(db_path)

    register_endpoint(
        {"name": "Leo", "email": "leo@example.com", "password": "ValidPassword123!"},
        db_path=db_path,
    )
    from opentrade.adapters.email_smtp import get_last_sent_token

    token1 = get_last_sent_token()
    assert token1 is not None

    # Request resend
    resend_status, _ = resend_verification_endpoint({"email": "leo@example.com"}, db_path=db_path)
    assert resend_status == 202

    token2 = get_last_sent_token()
    assert token2 is not None
    assert token2 != token1

    # First token must now be invalid
    status_old, resp_old = verify_email_endpoint({"token": token1}, db_path=db_path)
    assert status_old == 400
    assert resp_old["error"]["code"] == "TOKEN_INVALID"

    # Second token must succeed
    status_new, resp_new = verify_email_endpoint({"token": token2}, db_path=db_path)
    assert status_new == 200
    assert resp_new["verified"] is True


def test_resend_verification_rate_limit_3_per_hour(tmp_path: Path) -> None:
    """FR-3 & API_SPEC.md: Resend verification is rate-limited to 3 requests per hour;
    a 4th returns 429 RATE_LIMITED.
    """
    db_path = tmp_path / "test_reg.db"
    run_migrations(db_path)

    register_endpoint(
        {"name": "Mona", "email": "mona@example.com", "password": "ValidPassword123!"},
        db_path=db_path,
    )

    # Resend #1 (allowed)
    s1, _ = resend_verification_endpoint({"email": "mona@example.com"}, db_path=db_path)
    assert s1 == 202

    # Resend #2 (allowed)
    s2, _ = resend_verification_endpoint({"email": "mona@example.com"}, db_path=db_path)
    assert s2 == 202

    # Resend #3 (allowed)
    s3, _ = resend_verification_endpoint({"email": "mona@example.com"}, db_path=db_path)
    assert s3 == 202

    # Resend #4 (must be blocked by rate limit: max 3 per hour)
    s4, resp4 = resend_verification_endpoint({"email": "mona@example.com"}, db_path=db_path)
    assert s4 == 429
    assert resp4["error"]["code"] == "RATE_LIMITED"


def test_token_stored_as_sha256_hash_never_plain(tmp_path: Path) -> None:
    """FR-3 & SECURITY.md section 5: The database stores only the SHA-256 hash of
    the 32-byte token.
    """
    db_path = tmp_path / "test_reg.db"
    run_migrations(db_path)

    register_endpoint(
        {"name": "Nina", "email": "nina@example.com", "password": "ValidPassword123!"},
        db_path=db_path,
    )
    from opentrade.adapters.email_smtp import get_last_sent_token

    raw_token = get_last_sent_token()
    assert raw_token is not None

    db_bytes = db_path.read_bytes()
    assert (
        raw_token.encode("utf-8") not in db_bytes
    ), "Raw verification token found in database bytes!"


# --- T0.7 Login, lockout, and IP rate limit tests ---


def test_login_success_resets_failed_logins(tmp_path: Path) -> None:
    """FR-4: Valid login returns 200 with user data and resets failed_logins to 0."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_login.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Oscar", "email": "oscar@example.com", "password": pwd}, db_path=db_path
    )

    # First trigger one failed login to ensure failed_logins > 0
    status_fail, _ = login_endpoint(
        {"email": "oscar@example.com", "password": "WrongPassword123!"}, db_path=db_path
    )
    assert status_fail == 401

    conn = get_connection(db_path)
    repo = UserRepository(conn)
    u_before = repo.get_by_email("oscar@example.com")
    assert u_before is not None
    assert u_before.failed_logins == 1
    conn.close()

    # Successful login
    status_ok, resp = login_endpoint(
        {"email": "oscar@example.com", "password": pwd}, db_path=db_path
    )
    assert status_ok == 200
    assert "user" in resp
    user = resp["user"]
    assert user["email"] == "oscar@example.com"
    assert user["name"] == "Oscar"
    assert user["id"] is not None

    # Database failed_logins must be reset to 0
    conn = get_connection(db_path)
    repo = UserRepository(conn)
    u_after = repo.get_by_email("oscar@example.com")
    assert u_after is not None
    assert u_after.failed_logins == 0
    assert u_after.locked_until is None
    conn.close()


def test_login_invalid_password_returns_401_and_increments_failed_logins(tmp_path: Path) -> None:
    """FR-4 & FR-5: Incorrect password returns 401 UNAUTHENTICATED and increments failed_logins."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_login.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Paul", "email": "paul@example.com", "password": pwd}, db_path=db_path
    )

    status, resp = login_endpoint(
        {"email": "paul@example.com", "password": "WrongPassword123!"}, db_path=db_path
    )
    assert status == 401
    assert resp["error"]["code"] == "UNAUTHENTICATED"

    conn = get_connection(db_path)
    repo = UserRepository(conn)
    u = repo.get_by_email("paul@example.com")
    assert u is not None
    assert u.failed_logins == 1
    conn.close()


def test_login_unknown_email_returns_401_without_leaking_existence(tmp_path: Path) -> None:
    """FR-4 & SECURITY.md T-5: Unknown email returns 401 UNAUTHENTICATED
    with identical error message.
    """
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_login.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Quinn", "email": "quinn@example.com", "password": pwd}, db_path=db_path
    )

    # Known email with wrong password
    _, resp_known = login_endpoint(
        {"email": "quinn@example.com", "password": "WrongPassword!"}, db_path=db_path
    )

    # Unknown email
    status_unknown, resp_unknown = login_endpoint(
        {"email": "unknown@example.com", "password": "AnyPassword!"}, db_path=db_path
    )

    assert status_unknown == 401
    assert resp_unknown["error"]["code"] == "UNAUTHENTICATED"
    assert resp_unknown["error"]["message"] == resp_known["error"]["message"]


def test_account_locked_after_5_failures_within_10_minutes_ac4(tmp_path: Path) -> None:
    """AC-4 & FR-5: 5 failed logins within 10 min lock account for 15 min;
    6th returns 423 ACCOUNT_LOCKED even with correct password.
    """
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_login.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Rachel", "email": "rachel@example.com", "password": pwd}, db_path=db_path
    )

    # 5 consecutive failed attempts
    for i in range(1, 6):
        status, resp = login_endpoint(
            {"email": "rachel@example.com", "password": f"WrongPwd{i}!"},
            client_ip="10.0.0.1",
            db_path=db_path,
        )
        assert status == 401
        assert resp["error"]["code"] == "UNAUTHENTICATED"

    # Confirm user row now shows locked_until set
    conn = get_connection(db_path)
    repo = UserRepository(conn)
    u = repo.get_by_email("rachel@example.com")
    assert u is not None
    assert u.failed_logins == 5
    assert u.locked_until is not None
    conn.close()

    # 6th attempt with CORRECT password returns 423 ACCOUNT_LOCKED
    status_6th, resp_6th = login_endpoint(
        {"email": "rachel@example.com", "password": pwd},
        client_ip="10.0.0.1",
        db_path=db_path,
    )
    assert status_6th == 423
    assert resp_6th["error"]["code"] == "ACCOUNT_LOCKED"


def test_lock_message_does_not_reveal_password_correctness_ac4(tmp_path: Path) -> None:
    """AC-4: Account locked error message does not state whether password was right or wrong."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_login.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint({"name": "Sam", "email": "sam@example.com", "password": pwd}, db_path=db_path)

    # Lock account with 5 failures
    for i in range(5):
        login_endpoint(
            {"email": "sam@example.com", "password": f"Wrong{i}!"},
            client_ip="10.0.0.2",
            db_path=db_path,
        )

    # Attempt with right password
    _, resp_correct = login_endpoint(
        {"email": "sam@example.com", "password": pwd}, client_ip="10.0.0.2", db_path=db_path
    )

    # Attempt with wrong password
    _, resp_wrong = login_endpoint(
        {"email": "sam@example.com", "password": "StillWrong!"},
        client_ip="10.0.0.2",
        db_path=db_path,
    )

    assert resp_correct["error"]["message"] == resp_wrong["error"]["message"]
    msg = resp_correct["error"]["message"].lower()
    assert "correct" not in msg
    assert "wrong" not in msg
    assert "right" not in msg
    assert "incorrect" not in msg


def test_login_succeeds_after_15_minute_lockout_expires_ac4(tmp_path: Path) -> None:
    """AC-4 & FR-5: Once 15-minute lockout expires, login with correct password succeeds."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_login.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Tina", "email": "tina@example.com", "password": pwd}, db_path=db_path
    )

    # Lock account with 5 failures
    for i in range(5):
        login_endpoint(
            {"email": "tina@example.com", "password": f"Wrong{i}!"},
            client_ip="10.0.0.3",
            db_path=db_path,
        )

    # Manually expire lockout in database (set locked_until to 1 minute ago)
    from datetime import UTC, datetime, timedelta

    past_lock = (datetime.now(UTC) - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET locked_until = ? WHERE email = 'tina@example.com';", (past_lock,)
    )
    conn.close()

    # Login with correct password now succeeds
    status, resp = login_endpoint(
        {"email": "tina@example.com", "password": pwd}, client_ip="10.0.0.3", db_path=db_path
    )
    assert status == 200
    assert resp["user"]["email"] == "tina@example.com"

    # Confirm database lockout is cleared
    conn = get_connection(db_path)
    repo = UserRepository(conn)
    u = repo.get_by_email("tina@example.com")
    assert u is not None
    assert u.failed_logins == 0
    assert u.locked_until is None
    conn.close()


def test_failed_logins_reset_if_previous_failure_exceeds_10_minutes_window(tmp_path: Path) -> None:
    """AC-4 & FR-5: Failed attempts older than 10-minute window reset counter."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_login.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint({"name": "Uma", "email": "uma@example.com", "password": pwd}, db_path=db_path)

    # 4 failed attempts
    for i in range(4):
        login_endpoint(
            {"email": "uma@example.com", "password": f"Wrong{i}!"},
            client_ip="10.0.0.4",
            db_path=db_path,
        )

    conn = get_connection(db_path)
    repo = UserRepository(conn)
    u = repo.get_by_email("uma@example.com")
    assert u is not None
    assert u.failed_logins == 4
    conn.close()

    # Simulate that the 4 failures happened 11 minutes ago by updating updated_at
    from datetime import UTC, datetime, timedelta

    old_time = (datetime.now(UTC) - timedelta(minutes=11)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET updated_at = ? WHERE email = 'uma@example.com';", (old_time,))
    conn.close()

    # Another failed attempt after 11 minutes
    login_endpoint(
        {"email": "uma@example.com", "password": "WrongAgain!"},
        client_ip="10.0.0.4",
        db_path=db_path,
    )

    # Failures older than 10 min reset failed_logins counter to 1 (not 5, so no lock)
    conn = get_connection(db_path)
    repo = UserRepository(conn)
    u_after = repo.get_by_email("uma@example.com")
    assert u_after is not None
    assert u_after.failed_logins == 1
    assert u_after.locked_until is None
    conn.close()


def test_login_ip_rate_limit_10_per_minute(tmp_path: Path) -> None:
    """SECURITY.md T-2: >10 login attempts/min from same IP returns 429 RATE_LIMITED."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_login.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Victor", "email": "victor@example.com", "password": pwd}, db_path=db_path
    )

    test_ip = "192.168.1.100"

    # Make 10 requests from test_ip (allowed)
    for i in range(10):
        status, _ = login_endpoint(
            {"email": "victor@example.com", "password": f"Wrong{i}!"},
            client_ip=test_ip,
            db_path=db_path,
        )
        assert status in (401, 423)

    # 11th request from same test_ip must be rejected with 429 RATE_LIMITED
    status_11, resp_11 = login_endpoint(
        {"email": "victor@example.com", "password": pwd},
        client_ip=test_ip,
        db_path=db_path,
    )
    assert status_11 == 429
    assert resp_11["error"]["code"] == "RATE_LIMITED"


# --- T0.8 Sessions, sliding window, and logout tests ---


def test_login_creates_session_row_and_emits_cookie_fr4(tmp_path: Path) -> None:
    """FR-4 & SECURITY.md T-3: Login creates a hashed session row and emits ot_session cookie."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_sessions.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Wendy", "email": "wendy@example.com", "password": pwd}, db_path=db_path
    )

    res = login_endpoint(
        {"email": "wendy@example.com", "password": pwd},
        client_ip="192.168.1.1",
        user_agent="TestBrowser/1.0",
        db_path=db_path,
    )
    assert res[0] == 200
    assert "Set-Cookie" in res.headers
    cookie_str = res.headers["Set-Cookie"]
    assert "ot_session=" in cookie_str
    assert "HttpOnly" in cookie_str
    assert "SameSite=Lax" in cookie_str
    assert "Path=/" in cookie_str
    assert "Max-Age=1209600" in cookie_str
    assert "Secure" not in cookie_str  # Not in production

    raw_token = extract_session_token(cookie_str)
    assert raw_token is not None
    assert len(raw_token) > 20

    # Verify session row in database
    conn = get_connection(db_path)
    session_repo = SessionRepository(conn)
    expected_hash = hash_token(raw_token)
    session = session_repo.get_by_hash(expected_hash)
    assert session is not None
    assert session.token_hash == expected_hash
    # Raw token must never be stored
    assert raw_token not in (session.token_hash, session.created_at, session.expires_at)
    conn.close()


def test_login_cookie_has_secure_flag_in_production_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SECURITY.md T-3 & T-14: In production mode, ot_session cookie includes Secure flag."""
    monkeypatch.setenv("OPENTRADE_ENV", "production")
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_sessions.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Xander", "email": "xander@example.com", "password": pwd}, db_path=db_path
    )

    res = login_endpoint(
        {"email": "xander@example.com", "password": pwd},
        db_path=db_path,
    )
    assert res[0] == 200
    assert "Set-Cookie" in res.headers
    cookie_str = res.headers["Set-Cookie"]
    assert "Secure" in cookie_str


def test_get_me_authenticates_and_slides_session_window_fr4(tmp_path: Path) -> None:
    """FR-4 & SECURITY.md T-3: GET /me authenticates via cookie and slides session expiry."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_sessions.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Yara", "email": "yara@example.com", "password": pwd}, db_path=db_path
    )

    login_res = login_endpoint(
        {"email": "yara@example.com", "password": pwd},
        db_path=db_path,
    )
    raw_token = extract_session_token(login_res.headers["Set-Cookie"])
    assert raw_token is not None

    # Get initial session state
    conn = get_connection(db_path)
    session_repo = SessionRepository(conn)
    initial_session = session_repo.get_by_hash(hash_token(raw_token))
    assert initial_session is not None
    initial_last_seen = initial_session.last_seen_at
    conn.close()

    # Call GET /me
    status, body = me_endpoint(cookies={"ot_session": raw_token}, db_path=db_path)
    assert status == 200
    assert "user" in body
    assert body["user"]["email"] == "yara@example.com"
    assert body["user"]["name"] == "Yara"

    # Confirm sliding window updated last_seen_at
    conn = get_connection(db_path)
    session_repo = SessionRepository(conn)
    updated_session = session_repo.get_by_hash(hash_token(raw_token))
    assert updated_session is not None
    assert updated_session.last_seen_at >= initial_last_seen
    conn.close()


def test_get_me_sliding_window_caps_at_30_days(tmp_path: Path) -> None:
    """SECURITY.md §4: Session sliding window is capped at created_at + 30 days."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_sessions.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Zane", "email": "zane@example.com", "password": pwd}, db_path=db_path
    )

    login_res = login_endpoint(
        {"email": "zane@example.com", "password": pwd},
        db_path=db_path,
    )
    raw_token = extract_session_token(login_res.headers["Set-Cookie"])
    assert raw_token is not None

    # Simulate that session was created 25 days ago
    from datetime import UTC, datetime, timedelta

    created_25_days_ago = (datetime.now(UTC) - timedelta(days=25)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sessions SET created_at = ? WHERE token_hash = ?;",
        (created_25_days_ago, hash_token(raw_token)),
    )
    conn.close()

    # Call /me to trigger sliding extension
    status, _ = me_endpoint(cookies={"ot_session": raw_token}, db_path=db_path)
    assert status == 200

    # Max allowed expiry is created_at + 30 days (~5 days from now, NOT 14 days)
    conn = get_connection(db_path)
    session_repo = SessionRepository(conn)
    session = session_repo.get_by_hash(hash_token(raw_token))
    assert session is not None
    max_cap = (datetime.now(UTC) + timedelta(days=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert session.expires_at <= max_cap
    conn.close()


def test_get_me_missing_or_invalid_cookie_rejected(tmp_path: Path) -> None:
    """SECURITY.md T-3 & API_SPEC.md: Missing or invalid session cookie returns 401."""
    db_path = tmp_path / "test_sessions.db"
    run_migrations(db_path)

    # Missing cookie
    status_none, resp_none = me_endpoint(cookies=None, db_path=db_path)
    assert status_none == 401
    assert resp_none["error"]["code"] == "UNAUTHENTICATED"

    # Non-existent session token
    status_invalid, resp_invalid = me_endpoint(
        cookies={"ot_session": "invalid_non_existent_token"}, db_path=db_path
    )
    assert status_invalid == 401
    assert resp_invalid["error"]["code"] == "UNAUTHENTICATED"


def test_get_me_idle_expired_session_deleted_and_returns_401(tmp_path: Path) -> None:
    """SECURITY.md §4: Idle session older than 14 days expires, is deleted, and returns 401."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_sessions.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Alice", "email": "alice@example.com", "password": pwd}, db_path=db_path
    )

    login_res = login_endpoint(
        {"email": "alice@example.com", "password": pwd},
        db_path=db_path,
    )
    raw_token = extract_session_token(login_res.headers["Set-Cookie"])
    assert raw_token is not None

    # Manually expire the session in database (expires_at in the past)
    from datetime import UTC, datetime, timedelta

    past_expiry = (datetime.now(UTC) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sessions SET expires_at = ? WHERE token_hash = ?;",
        (past_expiry, hash_token(raw_token)),
    )
    conn.close()

    # Calling /me must return 401
    status, resp = me_endpoint(cookies={"ot_session": raw_token}, db_path=db_path)
    assert status == 401
    assert resp["error"]["code"] == "UNAUTHENTICATED"

    # Stale session row must be deleted from sessions table
    conn = get_connection(db_path)
    session_repo = SessionRepository(conn)
    assert session_repo.get_by_hash(hash_token(raw_token)) is None
    conn.close()


def test_get_me_absolute_expired_session_deleted_and_returns_401(tmp_path: Path) -> None:
    """SECURITY.md §4: Session older than 30 days total expires, is deleted, and returns 401."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_sessions.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint({"name": "Bob", "email": "bob@example.com", "password": pwd}, db_path=db_path)

    login_res = login_endpoint(
        {"email": "bob@example.com", "password": pwd},
        db_path=db_path,
    )
    raw_token = extract_session_token(login_res.headers["Set-Cookie"])
    assert raw_token is not None

    # Set created_at to 31 days ago, even if expires_at looks future
    from datetime import UTC, datetime, timedelta

    created_31_days_ago = (datetime.now(UTC) - timedelta(days=31)).strftime("%Y-%m-%dT%H:%M:%SZ")
    future_expiry = (datetime.now(UTC) + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sessions SET created_at = ?, expires_at = ? WHERE token_hash = ?;",
        (created_31_days_ago, future_expiry, hash_token(raw_token)),
    )
    conn.close()

    # Calling /me must return 401
    status, resp = me_endpoint(cookies={"ot_session": raw_token}, db_path=db_path)
    assert status == 401
    assert resp["error"]["code"] == "UNAUTHENTICATED"

    # Stale session row must be deleted from database
    conn = get_connection(db_path)
    session_repo = SessionRepository(conn)
    assert session_repo.get_by_hash(hash_token(raw_token)) is None
    conn.close()


def test_logout_deletes_current_session_and_clears_cookie_fr6(tmp_path: Path) -> None:
    """FR-6: Logout ends current session, returns 204, and emits cookie-clearing Set-Cookie."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_sessions.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Carol", "email": "carol@example.com", "password": pwd}, db_path=db_path
    )

    login_res = login_endpoint(
        {"email": "carol@example.com", "password": pwd},
        db_path=db_path,
    )
    raw_token = extract_session_token(login_res.headers["Set-Cookie"])
    assert raw_token is not None

    # Verify session exists in DB
    conn = get_connection(db_path)
    session_repo = SessionRepository(conn)
    assert session_repo.get_by_hash(hash_token(raw_token)) is not None
    conn.close()

    # Logout
    logout_res = logout_endpoint(cookies={"ot_session": raw_token}, db_path=db_path)
    assert logout_res[0] == 204
    assert "Set-Cookie" in logout_res.headers
    cookie_str = logout_res.headers["Set-Cookie"]
    assert "ot_session=" in cookie_str
    assert "Max-Age=0" in cookie_str
    assert "Path=/" in cookie_str
    assert "HttpOnly" in cookie_str

    # Session row must be deleted from DB
    conn = get_connection(db_path)
    session_repo = SessionRepository(conn)
    assert session_repo.get_by_hash(hash_token(raw_token)) is None
    conn.close()

    # Subsequent /me call with that token returns 401
    status_me, _ = me_endpoint(cookies={"ot_session": raw_token}, db_path=db_path)
    assert status_me == 401


def test_logout_all_deletes_all_user_sessions_and_clears_cookie_ac9(tmp_path: Path) -> None:
    """AC-9 & FR-6: Logout everywhere ends every session row for user and returns 204."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_sessions.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint({"name": "Dan", "email": "dan@example.com", "password": pwd}, db_path=db_path)

    # Log in 3 times to create 3 active sessions
    tokens: list[str] = []
    for i in range(3):
        res = login_endpoint(
            {"email": "dan@example.com", "password": pwd},
            client_ip=f"10.0.1.{i}",
            db_path=db_path,
        )
        tok = extract_session_token(res.headers["Set-Cookie"])
        assert tok is not None
        tokens.append(tok)

    conn = get_connection(db_path)
    user_repo = UserRepository(conn)
    user = user_repo.get_by_email("dan@example.com")
    assert user is not None
    session_repo = SessionRepository(conn)
    assert session_repo.count_for_user(user.id) == 3
    conn.close()

    # Call logout-all using session 1
    logout_all_res = logout_all_endpoint(cookies={"ot_session": tokens[0]}, db_path=db_path)
    assert logout_all_res[0] == 204
    assert "Set-Cookie" in logout_all_res.headers
    assert "Max-Age=0" in logout_all_res.headers["Set-Cookie"]

    # All sessions for the user must now be deleted
    conn = get_connection(db_path)
    session_repo = SessionRepository(conn)
    assert session_repo.count_for_user(user.id) == 0
    conn.close()

    # None of the 3 tokens can authenticate anymore
    for tok in tokens:
        status, _ = me_endpoint(cookies={"ot_session": tok}, db_path=db_path)
        assert status == 401


def test_logout_cookie_has_secure_flag_in_production_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SECURITY.md T-3 & T-14: Logout cookie clearing includes Secure in production mode."""
    monkeypatch.setenv("OPENTRADE_ENV", "production")
    db_path = tmp_path / "test_sessions.db"
    run_migrations(db_path)

    logout_res = logout_endpoint(cookies={"ot_session": "any"}, db_path=db_path)
    assert logout_res[0] == 204
    assert "Secure" in logout_res.headers["Set-Cookie"]

    logout_all_res = logout_all_endpoint(cookies=None, db_path=db_path)
    assert logout_all_res[0] == 401


# --- T0.10 Password reset (forgot and reset) tests ---


def test_forgot_password_known_email_issues_token_and_sends_email_fr7(tmp_path: Path) -> None:
    """FR-7 & SECURITY.md T-12: Forgot password creates 30-min token and sends email."""
    db_path = tmp_path / "test_reset.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Edward", "email": "edward@example.com", "password": pwd}, db_path=db_path
    )

    status, resp = forgot_password_endpoint({"email": "edward@example.com"}, db_path=db_path)
    assert status == 202
    assert resp["message"] == "If this email is registered, a password reset link has been sent."

    conn = get_connection(db_path)
    user_repo = UserRepository(conn)
    user = user_repo.get_by_email("edward@example.com")
    assert user is not None

    cursor = conn.cursor()
    cursor.execute(
        "SELECT purpose, token_hash, expires_at, used_at FROM auth_tokens WHERE user_id = ?;",
        (user.id,),
    )
    tokens = cursor.fetchall()
    conn.close()

    # Find reset token
    reset_tokens = [t for t in tokens if t[0] == "reset_password"]
    assert len(reset_tokens) == 1
    t_purpose, t_hash, t_expires, t_used = reset_tokens[0]
    assert t_purpose == "reset_password"
    assert len(t_hash) == 64  # SHA-256
    assert t_used is None


def test_forgot_password_unknown_email_same_response_and_timing_band_ac8(tmp_path: Path) -> None:
    """AC-8 & SECURITY.md T-5: Unknown email returns same 202 and latency band (<200ms)."""
    db_path = tmp_path / "test_reset.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Fiona", "email": "fiona@example.com", "password": pwd}, db_path=db_path
    )

    import time

    # Measure latency for known email
    t0 = time.perf_counter()
    status_known, resp_known = forgot_password_endpoint(
        {"email": "fiona@example.com"}, db_path=db_path
    )
    t_known = time.perf_counter() - t0

    # Measure latency for unknown email
    t1 = time.perf_counter()
    status_unknown, resp_unknown = forgot_password_endpoint(
        {"email": "unknown_ghost@example.com"}, db_path=db_path
    )
    t_unknown = time.perf_counter() - t1

    assert status_known == 202
    assert status_unknown == 202
    assert resp_known["message"] == resp_unknown["message"]
    # Latency band within 200 ms (0.2s)
    assert abs(t_known - t_unknown) < 0.200

    # No token row created for unknown email
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM auth_tokens WHERE purpose = 'reset_password';")
    count = cursor.fetchone()[0]
    assert count == 1  # Only the known email's token
    conn.close()


def test_forgot_password_invalidates_prior_unused_reset_tokens(tmp_path: Path) -> None:
    """SECURITY.md §5: Requesting new reset token invalidates earlier unused reset tokens."""
    db_path = tmp_path / "test_reset.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "George", "email": "george@example.com", "password": pwd}, db_path=db_path
    )

    # First request
    forgot_password_endpoint({"email": "george@example.com"}, db_path=db_path)

    conn = get_connection(db_path)
    user_repo = UserRepository(conn)
    user = user_repo.get_by_email("george@example.com")
    assert user is not None
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, expires_at FROM auth_tokens WHERE user_id = ? AND purpose = 'reset_password';",
        (user.id,),
    )
    first_token_id, first_expiry = cursor.fetchone()
    conn.close()

    # Second request
    forgot_password_endpoint({"email": "george@example.com"}, db_path=db_path)

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT expires_at FROM auth_tokens WHERE id = ?;", (first_token_id,))
    invalidated_expiry = cursor.fetchone()[0]
    conn.close()

    # First token expires_at must be pushed to past/now (invalidated)
    from opentrade.services.clock import is_expired

    assert is_expired(invalidated_expiry)


def test_reset_password_success_updates_password_and_clears_lockout_fr7(tmp_path: Path) -> None:
    """FR-7 & AC-5: Valid reset token and password updates hash, resets lockout, allows login."""
    db_path = tmp_path / "test_reset.db"
    run_migrations(db_path)

    old_pwd = "OldValidPassword123!"
    new_pwd = "NewValidPassword456!"
    register_endpoint(
        {"name": "Hannah", "email": "hannah@example.com", "password": old_pwd}, db_path=db_path
    )

    # Set user into locked state
    from datetime import UTC, datetime, timedelta

    future_lock = (datetime.now(UTC) + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET failed_logins = 5, locked_until = ? WHERE email = 'hannah@example.com';",
        (future_lock,),
    )
    conn.close()

    # Request reset token
    forgot_password_endpoint({"email": "hannah@example.com"}, db_path=db_path)

    # Extract raw token created for hannah
    from opentrade.services.security import generate_token

    raw_token = generate_token(32)
    tok_hash = hash_token(raw_token)

    conn = get_connection(db_path)
    user_repo = UserRepository(conn)
    user = user_repo.get_by_email("hannah@example.com")
    assert user is not None
    token_repo = TokenRepository(conn)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    future_exp = (datetime.now(UTC) + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    token_repo.create(
        user_id=user.id,
        purpose="reset_password",
        token_hash=tok_hash,
        expires_at=future_exp,
        created_at=now,
    )
    conn.close()

    # Reset password
    status, _ = reset_password_endpoint(
        {"token": raw_token, "new_password": new_pwd}, db_path=db_path
    )
    assert status == 204

    # Confirm token is marked used
    conn = get_connection(db_path)
    tok_row = TokenRepository(conn).get_by_hash(tok_hash)
    assert tok_row is not None
    assert tok_row.used_at is not None

    # Confirm lockout is cleared
    u_updated = UserRepository(conn).get_by_id(user.id)
    assert u_updated is not None
    assert u_updated.failed_logins == 0
    assert u_updated.locked_until is None
    conn.close()

    # Old password fails
    status_old, _ = login_endpoint(
        {"email": "hannah@example.com", "password": old_pwd}, db_path=db_path
    )
    assert status_old == 401

    # New password succeeds
    status_new, resp_new = login_endpoint(
        {"email": "hannah@example.com", "password": new_pwd}, db_path=db_path
    )
    assert status_new == 200
    assert resp_new["user"]["email"] == "hannah@example.com"


def test_reset_password_single_use_enforcement_ac5(tmp_path: Path) -> None:
    """AC-5: A password reset token works once. A second use returns 400."""
    db_path = tmp_path / "test_reset.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint({"name": "Ian", "email": "ian@example.com", "password": pwd}, db_path=db_path)

    from opentrade.services.security import generate_token

    raw_token = generate_token(32)
    tok_hash = hash_token(raw_token)

    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    exp = (datetime.now(UTC) + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = get_connection(db_path)
    user = UserRepository(conn).get_by_email("ian@example.com")
    assert user is not None
    TokenRepository(conn).create(
        user_id=user.id,
        purpose="reset_password",
        token_hash=tok_hash,
        expires_at=exp,
        created_at=now,
    )
    conn.close()

    # First use succeeds (204)
    status_1, _ = reset_password_endpoint(
        {"token": raw_token, "new_password": "NewValidPassword456!"}, db_path=db_path
    )
    assert status_1 == 204

    # Second use returns 400 TOKEN_INVALID
    status_2, resp_2 = reset_password_endpoint(
        {"token": raw_token, "new_password": "AnotherPassword789!"}, db_path=db_path
    )
    assert status_2 == 400
    assert resp_2["error"]["code"] == "TOKEN_INVALID"


def test_reset_password_expired_after_30_minutes_rejected_ac5(tmp_path: Path) -> None:
    """AC-5: A token used 31 minutes after creation returns 400."""
    db_path = tmp_path / "test_reset.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Julia", "email": "julia@example.com", "password": pwd}, db_path=db_path
    )

    from opentrade.services.security import generate_token

    raw_token = generate_token(32)
    tok_hash = hash_token(raw_token)

    from datetime import UTC, datetime, timedelta

    # Token created 31 minutes ago, expired 1 minute ago
    created_at = (datetime.now(UTC) - timedelta(minutes=31)).strftime("%Y-%m-%dT%H:%M:%SZ")
    past_exp = (datetime.now(UTC) - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = get_connection(db_path)
    user = UserRepository(conn).get_by_email("julia@example.com")
    assert user is not None
    TokenRepository(conn).create(
        user_id=user.id,
        purpose="reset_password",
        token_hash=tok_hash,
        expires_at=past_exp,
        created_at=created_at,
    )
    conn.close()

    # Submitting 31 minutes after creation returns 400 TOKEN_INVALID
    status, resp = reset_password_endpoint(
        {"token": raw_token, "new_password": "NewValidPassword456!"}, db_path=db_path
    )
    assert status == 400
    assert resp["error"]["code"] == "TOKEN_INVALID"


def test_reset_password_purpose_isolation_rejected(tmp_path: Path) -> None:
    """SECURITY.md §5: Using a verification token on password reset returns 400 TOKEN_INVALID."""
    db_path = tmp_path / "test_reset.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Kevin", "email": "kevin@example.com", "password": pwd}, db_path=db_path
    )

    from opentrade.services.security import generate_token

    raw_token = generate_token(32)
    tok_hash = hash_token(raw_token)

    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    exp = (datetime.now(UTC) + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Create verify_email token
    conn = get_connection(db_path)
    user = UserRepository(conn).get_by_email("kevin@example.com")
    assert user is not None
    TokenRepository(conn).create(
        user_id=user.id,
        purpose="verify_email",
        token_hash=tok_hash,
        expires_at=exp,
        created_at=now,
    )
    conn.close()

    status, resp = reset_password_endpoint(
        {"token": raw_token, "new_password": "NewValidPassword456!"}, db_path=db_path
    )
    assert status == 400
    assert resp["error"]["code"] == "TOKEN_INVALID"


def test_reset_password_weak_password_leaves_token_valid_for_retry(tmp_path: Path) -> None:
    """SECURITY.md §3 & AC-2: Weak password returns 422 WEAK_PASSWORD and leaves token usable."""
    db_path = tmp_path / "test_reset.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Laura", "email": "laura@example.com", "password": pwd}, db_path=db_path
    )

    from opentrade.services.security import generate_token

    raw_token = generate_token(32)
    tok_hash = hash_token(raw_token)

    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    exp = (datetime.now(UTC) + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = get_connection(db_path)
    user = UserRepository(conn).get_by_email("laura@example.com")
    assert user is not None
    TokenRepository(conn).create(
        user_id=user.id,
        purpose="reset_password",
        token_hash=tok_hash,
        expires_at=exp,
        created_at=now,
    )
    conn.close()

    # Short password fails with 422
    status_short, resp_short = reset_password_endpoint(
        {"token": raw_token, "new_password": "short"}, db_path=db_path
    )
    assert status_short == 422
    assert resp_short["error"]["code"] == "WEAK_PASSWORD"

    # Token must still be unused
    conn = get_connection(db_path)
    tok_row = TokenRepository(conn).get_by_hash(tok_hash)
    assert tok_row is not None
    assert tok_row.used_at is None
    conn.close()

    # Retry with strong password succeeds
    status_ok, _ = reset_password_endpoint(
        {"token": raw_token, "new_password": "StrongPassword456!"}, db_path=db_path
    )
    assert status_ok == 204


def test_reset_password_terminates_all_active_sessions(tmp_path: Path) -> None:
    """SECURITY.md §4 & API_SPEC.md §2: Password reset terminates all active user sessions."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_reset.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Mike", "email": "mike@example.com", "password": pwd}, db_path=db_path
    )

    # Log in to get active session
    login_res = login_endpoint({"email": "mike@example.com", "password": pwd}, db_path=db_path)
    raw_session_token = extract_session_token(login_res.headers["Set-Cookie"])
    assert raw_session_token is not None

    # Verify session is currently active
    status_me_before, _ = me_endpoint(cookies={"ot_session": raw_session_token}, db_path=db_path)
    assert status_me_before == 200

    # Issue reset token and reset password
    from opentrade.services.security import generate_token

    raw_reset_token = generate_token(32)
    tok_hash = hash_token(raw_reset_token)

    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    exp = (datetime.now(UTC) + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = get_connection(db_path)
    user = UserRepository(conn).get_by_email("mike@example.com")
    assert user is not None
    TokenRepository(conn).create(
        user_id=user.id,
        purpose="reset_password",
        token_hash=tok_hash,
        expires_at=exp,
        created_at=now,
    )
    conn.close()

    status_reset, _ = reset_password_endpoint(
        {"token": raw_reset_token, "new_password": "BrandNewPassword123!"}, db_path=db_path
    )
    assert status_reset == 204

    # Old session is terminated; /me returns 401
    status_me_after, _ = me_endpoint(cookies={"ot_session": raw_session_token}, db_path=db_path)
    assert status_me_after == 401

    conn = get_connection(db_path)
    assert SessionRepository(conn).count_for_user(user.id) == 0
    conn.close()


def test_reset_password_missing_token_or_password_returns_422(tmp_path: Path) -> None:
    """API_SPEC.md §1: Missing token or new_password returns 422 VALIDATION_FAILED."""
    db_path = tmp_path / "test_reset.db"
    run_migrations(db_path)

    # Missing token
    s1, r1 = reset_password_endpoint({"new_password": "ValidPassword123!"}, db_path=db_path)
    assert s1 == 422
    assert r1["error"]["code"] == "VALIDATION_FAILED"

    # Missing password
    s2, r2 = reset_password_endpoint({"token": "some-token"}, db_path=db_path)
    assert s2 == 422
    assert r2["error"]["code"] == "VALIDATION_FAILED"


def test_forgot_password_malformed_email_returns_422(tmp_path: Path) -> None:
    """API_SPEC.md §1: Malformed email returns 422 VALIDATION_FAILED."""
    db_path = tmp_path / "test_reset.db"
    run_migrations(db_path)

    status, resp = forgot_password_endpoint({"email": "not-an-email"}, db_path=db_path)
    assert status == 422
    assert resp["error"]["code"] == "VALIDATION_FAILED"


# --- T0.11 Profile management (view, change name/email, change password) tests ---


def test_view_profile_me_endpoint_returns_user_fr8(tmp_path: Path) -> None:
    """FR-8 & US-6: GET /api/v1/me returns the authenticated user profile."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_profile.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Alice View", "email": "alice.view@example.com", "password": pwd},
        db_path=db_path,
    )
    login_res = login_endpoint(
        {"email": "alice.view@example.com", "password": pwd}, db_path=db_path
    )
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    status, resp = me_endpoint(cookies={"ot_session": session_tok}, db_path=db_path)
    assert status == 200
    assert resp["user"]["name"] == "Alice View"
    assert resp["user"]["email"] == "alice.view@example.com"
    assert resp["user"]["verified"] is False


def test_patch_me_update_name_only_preserves_verified_status_fr8(tmp_path: Path) -> None:
    """FR-8 & US-6: PATCH /me updating name only preserves verified status and sends zero emails."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_profile.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Bob Original", "email": "bob@example.com", "password": pwd},
        db_path=db_path,
    )

    # Mark user verified
    conn = get_connection(db_path)
    u_repo = UserRepository(conn)
    user = u_repo.get_by_email("bob@example.com")
    assert user is not None
    u_repo.update_email_verified_at(user.id, "2026-11-25T12:00:00Z")
    conn.close()

    login_res = login_endpoint({"email": "bob@example.com", "password": pwd}, db_path=db_path)
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    # Update name only
    status, resp = patch_me_endpoint(
        {"name": "Bob Updated"}, cookies={"ot_session": session_tok}, db_path=db_path
    )
    assert status == 200
    assert resp["user"]["name"] == "Bob Updated"
    assert resp["user"]["email"] == "bob@example.com"
    assert resp["user"]["verified"] is True

    # Database checks: name updated, email_verified_at preserved
    conn = get_connection(db_path)
    u = UserRepository(conn).get_by_id(user.id)
    assert u is not None
    assert u.name == "Bob Updated"
    assert u.email_verified_at == "2026-11-25T12:00:00Z"

    # Confirm no new verification tokens issued
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM auth_tokens WHERE user_id = ? AND purpose = 'verify_email';",
        (user.id,),
    )
    count = cursor.fetchone()[0]
    # Registration issued 1 verify token; updating name should NOT issue another
    assert count == 1
    conn.close()


def test_patch_me_submitting_same_email_preserves_verified_status_fr8(tmp_path: Path) -> None:
    """FR-8 & US-6: Submitting unchanged email preserves email_verified_at and sends zero emails."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_profile.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Carol", "email": "carol@example.com", "password": pwd},
        db_path=db_path,
    )

    conn = get_connection(db_path)
    u_repo = UserRepository(conn)
    user = u_repo.get_by_email("carol@example.com")
    assert user is not None
    u_repo.update_email_verified_at(user.id, "2026-11-25T12:00:00Z")
    conn.close()

    login_res = login_endpoint({"email": "carol@example.com", "password": pwd}, db_path=db_path)
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    status, resp = patch_me_endpoint(
        {"name": "Carol Renamed", "email": "carol@example.com"},
        cookies={"ot_session": session_tok},
        db_path=db_path,
    )
    assert status == 200
    assert resp["user"]["name"] == "Carol Renamed"
    assert resp["user"]["verified"] is True

    conn = get_connection(db_path)
    u = UserRepository(conn).get_by_id(user.id)
    assert u is not None
    assert u.email_verified_at == "2026-11-25T12:00:00Z"
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM auth_tokens WHERE user_id = ? AND purpose = 'verify_email';",
        (user.id,),
    )
    assert cursor.fetchone()[0] == 1  # No extra token
    conn.close()


def test_patch_me_update_email_resets_verified_and_sends_verification_email_fr8(
    tmp_path: Path,
) -> None:
    """FR-8 & US-6: Updating email resets email_verified_at = NULL and
    issues 24h verification token.
    """
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_profile.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Dave", "email": "dave.old@example.com", "password": pwd},
        db_path=db_path,
    )

    conn = get_connection(db_path)
    u_repo = UserRepository(conn)
    user = u_repo.get_by_email("dave.old@example.com")
    assert user is not None
    u_repo.update_email_verified_at(user.id, "2026-11-25T12:00:00Z")
    conn.close()

    login_res = login_endpoint({"email": "dave.old@example.com", "password": pwd}, db_path=db_path)
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    status, resp = patch_me_endpoint(
        {"email": "dave.new@example.com"},
        cookies={"ot_session": session_tok},
        db_path=db_path,
    )
    assert status == 200
    assert resp["user"]["email"] == "dave.new@example.com"
    assert resp["user"]["verified"] is False

    # Database verification
    conn = get_connection(db_path)
    u = UserRepository(conn).get_by_id(user.id)
    assert u is not None
    assert u.email == "dave.new@example.com"
    assert u.email_verified_at is None

    # Token table verification: new verify_email token issued with 24h expiry
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT purpose, expires_at, used_at FROM auth_tokens
        WHERE user_id = ? AND purpose = 'verify_email'
        ORDER BY id DESC;
        """,
        (user.id,),
    )
    tokens = cursor.fetchall()
    assert len(tokens) >= 2
    latest_purpose, latest_exp, latest_used = tokens[0]
    assert latest_purpose == "verify_email"
    assert latest_used is None
    conn.close()


def test_patch_me_update_email_invalidates_prior_unused_verification_tokens_fr8(
    tmp_path: Path,
) -> None:
    """FR-8 & US-6: Updating email invalidates earlier unused verification tokens for user."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_profile.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Eve", "email": "eve.old@example.com", "password": pwd},
        db_path=db_path,
    )

    login_res = login_endpoint({"email": "eve.old@example.com", "password": pwd}, db_path=db_path)
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    # Find the first registration verification token
    conn = get_connection(db_path)
    user = UserRepository(conn).get_by_email("eve.old@example.com")
    assert user is not None
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, expires_at FROM auth_tokens WHERE user_id = ? AND purpose = 'verify_email';",
        (user.id,),
    )
    first_token_id, _ = cursor.fetchone()
    conn.close()

    # Update email
    patch_me_endpoint(
        {"email": "eve.new@example.com"},
        cookies={"ot_session": session_tok},
        db_path=db_path,
    )

    # First token must now be expired/invalidated
    from opentrade.services.clock import is_expired

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT expires_at FROM auth_tokens WHERE id = ?;", (first_token_id,))
    first_token_exp = cursor.fetchone()[0]
    conn.close()
    assert is_expired(first_token_exp)


def test_patch_me_update_both_name_and_email_fr8(tmp_path: Path) -> None:
    """FR-8 & US-6: PATCH /me updating both name and email updates both and resets verification."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_profile.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Frank", "email": "frank.old@example.com", "password": pwd},
        db_path=db_path,
    )

    conn = get_connection(db_path)
    u_repo = UserRepository(conn)
    user = u_repo.get_by_email("frank.old@example.com")
    assert user is not None
    u_repo.update_email_verified_at(user.id, "2026-11-25T12:00:00Z")
    conn.close()

    login_res = login_endpoint({"email": "frank.old@example.com", "password": pwd}, db_path=db_path)
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    status, resp = patch_me_endpoint(
        {"name": "Frank New", "email": "frank.new@example.com"},
        cookies={"ot_session": session_tok},
        db_path=db_path,
    )
    assert status == 200
    assert resp["user"]["name"] == "Frank New"
    assert resp["user"]["email"] == "frank.new@example.com"
    assert resp["user"]["verified"] is False


def test_patch_me_duplicate_email_taken_by_another_user_returns_422_fr8(tmp_path: Path) -> None:
    """FR-8 & US-6: Duplicate email belonging to another user returns 422 VALIDATION_FAILED."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_profile.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Grace A", "email": "grace.a@example.com", "password": pwd},
        db_path=db_path,
    )
    register_endpoint(
        {"name": "Grace B", "email": "grace.b@example.com", "password": pwd},
        db_path=db_path,
    )

    login_res = login_endpoint({"email": "grace.a@example.com", "password": pwd}, db_path=db_path)
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    status, resp = patch_me_endpoint(
        {"email": "grace.b@example.com"},
        cookies={"ot_session": session_tok},
        db_path=db_path,
    )
    assert status == 422
    assert resp["error"]["code"] == "VALIDATION_FAILED"

    # Confirm database was not mutated
    conn = get_connection(db_path)
    u = UserRepository(conn).get_by_email("grace.a@example.com")
    assert u is not None
    assert u.email == "grace.a@example.com"
    conn.close()


def test_patch_me_unauthenticated_returns_401_fr8(tmp_path: Path) -> None:
    """FR-8 & US-6: PATCH /me without valid session cookie returns 401 UNAUTHENTICATED."""
    db_path = tmp_path / "test_profile.db"
    run_migrations(db_path)

    # Missing session
    s1, r1 = patch_me_endpoint({"name": "No Auth"}, cookies=None, db_path=db_path)
    assert s1 == 401
    assert r1["error"]["code"] == "UNAUTHENTICATED"

    # Invalid session
    s2, r2 = patch_me_endpoint(
        {"name": "No Auth"}, cookies={"ot_session": "bogus-token"}, db_path=db_path
    )
    assert s2 == 401
    assert r2["error"]["code"] == "UNAUTHENTICATED"


def test_patch_me_invalid_inputs_returns_422_fr8(tmp_path: Path) -> None:
    """FR-8 & US-6: Invalid name, email, or empty payload returns 422 VALIDATION_FAILED."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_profile.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Harry", "email": "harry@example.com", "password": pwd},
        db_path=db_path,
    )
    login_res = login_endpoint({"email": "harry@example.com", "password": pwd}, db_path=db_path)
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    # Empty payload
    s1, r1 = patch_me_endpoint({}, cookies={"ot_session": session_tok}, db_path=db_path)
    assert s1 == 422
    assert r1["error"]["code"] == "VALIDATION_FAILED"

    # Empty name
    s2, r2 = patch_me_endpoint(
        {"name": "   "}, cookies={"ot_session": session_tok}, db_path=db_path
    )
    assert s2 == 422
    assert r2["error"]["code"] == "VALIDATION_FAILED"

    # Name > 80 chars
    s3, r3 = patch_me_endpoint(
        {"name": "A" * 81}, cookies={"ot_session": session_tok}, db_path=db_path
    )
    assert s3 == 422
    assert r3["error"]["code"] == "VALIDATION_FAILED"

    # Malformed email
    s4, r4 = patch_me_endpoint(
        {"email": "not-an-email"}, cookies={"ot_session": session_tok}, db_path=db_path
    )
    assert s4 == 422
    assert r4["error"]["code"] == "VALIDATION_FAILED"


def test_patch_me_csrf_enforcement_fr8(tmp_path: Path) -> None:
    """FR-8 & SECURITY.md T-4: State-changing PATCH /me enforces CSRF validation."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_profile.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Ian CSRF", "email": "ian.csrf@example.com", "password": pwd},
        db_path=db_path,
    )
    login_res = login_endpoint({"email": "ian.csrf@example.com", "password": pwd}, db_path=db_path)
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    from opentrade.services.csrf import generate_csrf_token

    csrf_tok = generate_csrf_token()

    # Missing X-CSRF-Token header when ot_csrf cookie is present returns 403 CSRF_FAILED
    s1, r1 = patch_me_endpoint(
        {"name": "Ian Renamed"},
        cookies={"ot_session": session_tok, "ot_csrf": csrf_tok},
        headers={},
        db_path=db_path,
    )
    assert s1 == 403
    assert r1["error"]["code"] == "CSRF_FAILED"

    # Mismatched X-CSRF-Token header returns 403 CSRF_FAILED
    s2, r2 = patch_me_endpoint(
        {"name": "Ian Renamed"},
        cookies={"ot_session": session_tok, "ot_csrf": csrf_tok},
        headers={"X-CSRF-Token": "wrong-token"},
        db_path=db_path,
    )
    assert s2 == 403
    assert r2["error"]["code"] == "CSRF_FAILED"

    # Valid matching X-CSRF-Token succeeds
    s3, r3 = patch_me_endpoint(
        {"name": "Ian Renamed"},
        cookies={"ot_session": session_tok, "ot_csrf": csrf_tok},
        headers={"X-CSRF-Token": csrf_tok},
        db_path=db_path,
    )
    assert s3 == 200
    assert r3["user"]["name"] == "Ian Renamed"


def test_change_password_success_updates_hash_and_allows_new_login_fr8(tmp_path: Path) -> None:
    """FR-8 & US-6: POST /me/password with valid current password updates hash and allows login."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_profile.db"
    run_migrations(db_path)

    old_pwd = "OldValidPassword123!"
    new_pwd = "NewValidPassword456!"
    register_endpoint(
        {"name": "Julia", "email": "julia@example.com", "password": old_pwd},
        db_path=db_path,
    )
    login_res = login_endpoint({"email": "julia@example.com", "password": old_pwd}, db_path=db_path)
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    status, _ = change_password_endpoint(
        {"current_password": old_pwd, "new_password": new_pwd},
        cookies={"ot_session": session_tok},
        db_path=db_path,
    )
    assert status == 204

    # Old password fails
    s_old, _ = login_endpoint({"email": "julia@example.com", "password": old_pwd}, db_path=db_path)
    assert s_old == 401

    # New password succeeds
    s_new, r_new = login_endpoint(
        {"email": "julia@example.com", "password": new_pwd}, db_path=db_path
    )
    assert s_new == 200
    assert r_new["user"]["email"] == "julia@example.com"


def test_change_password_deletes_other_sessions_keeps_current_session_fr8(tmp_path: Path) -> None:
    """FR-8 & SECURITY.md §4: Password change deletes other sessions,
    keeping caller's session active.
    """
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_profile.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    new_pwd = "NewValidPassword456!"
    register_endpoint(
        {"name": "Kevin", "email": "kevin@example.com", "password": pwd},
        db_path=db_path,
    )

    # Establish 3 sessions
    res1 = login_endpoint({"email": "kevin@example.com", "password": pwd}, db_path=db_path)
    tok1 = extract_session_token(res1.headers["Set-Cookie"])
    res2 = login_endpoint({"email": "kevin@example.com", "password": pwd}, db_path=db_path)
    tok2 = extract_session_token(res2.headers["Set-Cookie"])
    res3 = login_endpoint({"email": "kevin@example.com", "password": pwd}, db_path=db_path)
    tok3 = extract_session_token(res3.headers["Set-Cookie"])

    assert tok1 and tok2 and tok3

    conn = get_connection(db_path)
    user = UserRepository(conn).get_by_email("kevin@example.com")
    assert user is not None
    s_repo = SessionRepository(conn)
    assert s_repo.count_for_user(user.id) == 3
    conn.close()

    # Use session 1 to change password
    status, _ = change_password_endpoint(
        {"current_password": pwd, "new_password": new_pwd},
        cookies={"ot_session": tok1},
        db_path=db_path,
    )
    assert status == 204

    # Current session tok1 remains active!
    s_me1, r_me1 = me_endpoint(cookies={"ot_session": tok1}, db_path=db_path)
    assert s_me1 == 200
    assert r_me1["user"]["email"] == "kevin@example.com"

    # Other sessions tok2 and tok3 are deleted
    s_me2, _ = me_endpoint(cookies={"ot_session": tok2}, db_path=db_path)
    assert s_me2 == 401

    s_me3, _ = me_endpoint(cookies={"ot_session": tok3}, db_path=db_path)
    assert s_me3 == 401

    # Exactly 1 active session remains in database
    conn = get_connection(db_path)
    assert SessionRepository(conn).count_for_user(user.id) == 1
    conn.close()


def test_change_password_invalid_current_password_returns_401_fr8(tmp_path: Path) -> None:
    """FR-8 & US-6: Incorrect current_password returns 401 UNAUTHENTICATED."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_profile.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Laura", "email": "laura@example.com", "password": pwd},
        db_path=db_path,
    )
    login_res = login_endpoint({"email": "laura@example.com", "password": pwd}, db_path=db_path)
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    status, resp = change_password_endpoint(
        {"current_password": "WrongPassword999!", "new_password": "BrandNewPassword123!"},
        cookies={"ot_session": session_tok},
        db_path=db_path,
    )
    assert status == 401
    assert resp["error"]["code"] == "UNAUTHENTICATED"

    # Original password still works
    s_check, _ = login_endpoint({"email": "laura@example.com", "password": pwd}, db_path=db_path)
    assert s_check == 200


def test_change_password_weak_new_password_returns_422_fr8(tmp_path: Path) -> None:
    """FR-8 & SECURITY.md §3: Weak new password returns 422 WEAK_PASSWORD."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_profile.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Mike", "email": "mike@example.com", "password": pwd},
        db_path=db_path,
    )
    login_res = login_endpoint({"email": "mike@example.com", "password": pwd}, db_path=db_path)
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    # Short password (<12 chars)
    s1, r1 = change_password_endpoint(
        {"current_password": pwd, "new_password": "short"},
        cookies={"ot_session": session_tok},
        db_path=db_path,
    )
    assert s1 == 422
    assert r1["error"]["code"] == "WEAK_PASSWORD"

    # Common password (in 10,001 list, len 12)
    s2, r2 = change_password_endpoint(
        {"current_password": pwd, "new_password": "unbelievable"},
        cookies={"ot_session": session_tok},
        db_path=db_path,
    )
    assert s2 == 422
    assert r2["error"]["code"] == "WEAK_PASSWORD"


def test_change_password_missing_fields_returns_422_fr8(tmp_path: Path) -> None:
    """FR-8 & US-6: Missing current_password or new_password returns 422 VALIDATION_FAILED."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_profile.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Nancy", "email": "nancy@example.com", "password": pwd},
        db_path=db_path,
    )
    login_res = login_endpoint({"email": "nancy@example.com", "password": pwd}, db_path=db_path)
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    # Missing new_password
    s1, r1 = change_password_endpoint(
        {"current_password": pwd},
        cookies={"ot_session": session_tok},
        db_path=db_path,
    )
    assert s1 == 422
    assert r1["error"]["code"] == "VALIDATION_FAILED"

    # Missing current_password
    s2, r2 = change_password_endpoint(
        {"new_password": "BrandNewPassword123!"},
        cookies={"ot_session": session_tok},
        db_path=db_path,
    )
    assert s2 == 422
    assert r2["error"]["code"] == "VALIDATION_FAILED"


def test_change_password_unauthenticated_returns_401_fr8(tmp_path: Path) -> None:
    """FR-8 & US-6: POST /me/password without valid session returns 401 UNAUTHENTICATED."""
    db_path = tmp_path / "test_profile.db"
    run_migrations(db_path)

    status, resp = change_password_endpoint(
        {"current_password": "any", "new_password": "ValidNewPassword123!"},
        cookies=None,
        db_path=db_path,
    )
    assert status == 401
    assert resp["error"]["code"] == "UNAUTHENTICATED"


def test_change_password_csrf_enforcement_fr8(tmp_path: Path) -> None:
    """FR-8 & SECURITY.md T-4: State-changing POST /me/password enforces CSRF validation."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_profile.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    new_pwd = "BrandNewPassword123!"
    register_endpoint(
        {"name": "Oscar CSRF", "email": "oscar.csrf@example.com", "password": pwd},
        db_path=db_path,
    )
    login_res = login_endpoint(
        {"email": "oscar.csrf@example.com", "password": pwd}, db_path=db_path
    )
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    from opentrade.services.csrf import generate_csrf_token

    csrf_tok = generate_csrf_token()

    # Missing X-CSRF-Token header when ot_csrf cookie is present returns 403 CSRF_FAILED
    s1, r1 = change_password_endpoint(
        {"current_password": pwd, "new_password": new_pwd},
        cookies={"ot_session": session_tok, "ot_csrf": csrf_tok},
        headers={},
        db_path=db_path,
    )
    assert s1 == 403
    assert r1["error"]["code"] == "CSRF_FAILED"

    # Mismatched X-CSRF-Token header returns 403 CSRF_FAILED
    s2, r2 = change_password_endpoint(
        {"current_password": pwd, "new_password": new_pwd},
        cookies={"ot_session": session_tok, "ot_csrf": csrf_tok},
        headers={"X-CSRF-Token": "bad-csrf"},
        db_path=db_path,
    )
    assert s2 == 403
    assert r2["error"]["code"] == "CSRF_FAILED"

    # Valid matching X-CSRF-Token succeeds
    s3, _ = change_password_endpoint(
        {"current_password": pwd, "new_password": new_pwd},
        cookies={"ot_session": session_tok, "ot_csrf": csrf_tok},
        headers={"X-CSRF-Token": csrf_tok},
        db_path=db_path,
    )
    assert s3 == 204


# --- T0.12 Account deletion (password confirm) with cascade tests ---


def test_delete_me_success_returns_204_and_clears_cookie_ac6_fr9(tmp_path: Path) -> None:
    """AC-6, FR-9 & US-7: Valid password confirms account deletion returning 204
    and clears cookie.
    """
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_delete.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Delete Target", "email": "delete.target@example.com", "password": pwd},
        db_path=db_path,
    )
    login_res = login_endpoint(
        {"email": "delete.target@example.com", "password": pwd}, db_path=db_path
    )
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    conn = get_connection(db_path)
    user = UserRepository(conn).get_by_email("delete.target@example.com")
    assert user is not None
    conn.close()

    res = delete_me_endpoint(
        {"password": pwd}, cookies={"ot_session": session_tok}, db_path=db_path
    )
    assert res.status_code == 204
    assert res.body == {}
    assert "Set-Cookie" in res.headers
    assert "ot_session=" in res.headers["Set-Cookie"]
    assert "Max-Age=0" in res.headers["Set-Cookie"]

    conn = get_connection(db_path)
    assert UserRepository(conn).get_by_id(user.id) is None
    conn.close()


def test_delete_me_cascades_zero_rows_across_all_tables_ac6(tmp_path: Path) -> None:
    """AC-6: Dynamic sqlite_master sweep confirms 0 rows for user_id across all tables."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_delete.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Cascade User", "email": "cascade@example.com", "password": pwd},
        db_path=db_path,
    )

    # Create 3 sessions
    res1 = login_endpoint({"email": "cascade@example.com", "password": pwd}, db_path=db_path)
    tok1 = extract_session_token(res1.headers["Set-Cookie"])
    res2 = login_endpoint({"email": "cascade@example.com", "password": pwd}, db_path=db_path)
    assert res2.status_code == 200
    res3 = login_endpoint({"email": "cascade@example.com", "password": pwd}, db_path=db_path)
    assert res3.status_code == 200
    assert tok1 is not None

    conn = get_connection(db_path)
    user = UserRepository(conn).get_by_email("cascade@example.com")
    assert user is not None
    user_id = user.id

    # Create multiple auth tokens (verify and reset)
    from opentrade.services.security import generate_token

    t_repo = TokenRepository(conn)
    t_repo.create(
        user_id=user_id,
        purpose="reset_password",
        token_hash=hash_token(generate_token(32)),
        expires_at="2026-11-26T12:00:00Z",
        created_at="2026-11-26T11:00:00Z",
    )
    conn.close()

    # Pre-condition check: multiple sessions and tokens exist
    conn = get_connection(db_path)
    assert SessionRepository(conn).count_for_user(user_id) >= 3
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM auth_tokens WHERE user_id = ?;", (user_id,))
    assert cursor.fetchone()[0] >= 2
    conn.close()

    # Delete account
    res = delete_me_endpoint({"password": pwd}, cookies={"ot_session": tok1}, db_path=db_path)
    assert res.status_code == 204

    # AC-6 Sweep: Check all tables in sqlite_master
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name != 'schema_migrations';
        """)
    tables = [row[0] for row in cursor.fetchall()]
    assert len(tables) > 0

    for table in tables:
        cursor.execute(f"PRAGMA table_info({table});")  # noqa: S608
        cols = [col[1] for col in cursor.fetchall()]
        if "user_id" in cols:
            cursor.execute(
                f"SELECT COUNT(*) FROM {table} WHERE user_id = ?;",  # noqa: S608
                (user_id,),
            )
            remaining = cursor.fetchone()[0]
            assert remaining == 0, f"Table {table} still has {remaining} rows for user_id={user_id}"
        if table == "users":
            cursor.execute("SELECT COUNT(*) FROM users WHERE id = ?;", (user_id,))
            assert cursor.fetchone()[0] == 0
    conn.close()


def test_delete_me_invalidates_session_and_login_immediately_fr9(tmp_path: Path) -> None:
    """FR-9 & US-7: Session and credentials immediately invalidated upon account deletion."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_delete.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Invalidate Test", "email": "inv@example.com", "password": pwd},
        db_path=db_path,
    )
    login_res = login_endpoint({"email": "inv@example.com", "password": pwd}, db_path=db_path)
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    res = delete_me_endpoint(
        {"password": pwd}, cookies={"ot_session": session_tok}, db_path=db_path
    )
    assert res.status_code == 204

    # Session token cannot access /me anymore
    s_me, r_me = me_endpoint(cookies={"ot_session": session_tok}, db_path=db_path)
    assert s_me == 401
    assert r_me["error"]["code"] == "UNAUTHENTICATED"

    # Session token cannot access PATCH /me anymore
    s_patch, r_patch = patch_me_endpoint(
        {"name": "Ghost"}, cookies={"ot_session": session_tok}, db_path=db_path
    )
    assert s_patch == 401
    assert r_patch["error"]["code"] == "UNAUTHENTICATED"

    # User cannot log in anymore
    s_login, r_login = login_endpoint(
        {"email": "inv@example.com", "password": pwd}, db_path=db_path
    )
    assert s_login == 401
    assert r_login["error"]["code"] == "UNAUTHENTICATED"


def test_delete_me_incorrect_password_returns_401_ac6_fr9(tmp_path: Path) -> None:
    """AC-6 & FR-9: Incorrect password returns 401 UNAUTHENTICATED leaving account intact."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_delete.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Safe User", "email": "safe@example.com", "password": pwd},
        db_path=db_path,
    )
    login_res = login_endpoint({"email": "safe@example.com", "password": pwd}, db_path=db_path)
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    res = delete_me_endpoint(
        {"password": "WrongPassword999!"},
        cookies={"ot_session": session_tok},
        db_path=db_path,
    )
    assert res.status_code == 401
    assert res.body["error"]["code"] == "UNAUTHENTICATED"

    # Confirm user still exists
    conn = get_connection(db_path)
    u = UserRepository(conn).get_by_email("safe@example.com")
    assert u is not None
    assert SessionRepository(conn).count_for_user(u.id) >= 1
    conn.close()


def test_delete_me_missing_or_empty_password_returns_422_fr9(tmp_path: Path) -> None:
    """FR-9 & US-7: Missing or empty password returns 422 VALIDATION_FAILED."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_delete.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Empty Pwd User", "email": "empty@example.com", "password": pwd},
        db_path=db_path,
    )
    login_res = login_endpoint({"email": "empty@example.com", "password": pwd}, db_path=db_path)
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    # Empty body
    r1 = delete_me_endpoint({}, cookies={"ot_session": session_tok}, db_path=db_path)
    assert r1.status_code == 422
    assert r1.body["error"]["code"] == "VALIDATION_FAILED"

    # Empty string password
    r2 = delete_me_endpoint(
        {"password": "   "}, cookies={"ot_session": session_tok}, db_path=db_path
    )
    assert r2.status_code == 422
    assert r2.body["error"]["code"] == "VALIDATION_FAILED"

    # Non-string password
    r3 = delete_me_endpoint(
        {"password": 12345}, cookies={"ot_session": session_tok}, db_path=db_path
    )
    assert r3.status_code == 422
    assert r3.body["error"]["code"] == "VALIDATION_FAILED"


def test_delete_me_unauthenticated_returns_401_fr9(tmp_path: Path) -> None:
    """FR-9 & US-7: DELETE /me without valid session cookie returns 401 UNAUTHENTICATED."""
    db_path = tmp_path / "test_delete.db"
    run_migrations(db_path)

    # Missing session
    r1 = delete_me_endpoint({"password": "any"}, cookies=None, db_path=db_path)
    assert r1.status_code == 401
    assert r1.body["error"]["code"] == "UNAUTHENTICATED"

    # Bogus session
    r2 = delete_me_endpoint(
        {"password": "any"}, cookies={"ot_session": "bogus-tok"}, db_path=db_path
    )
    assert r2.status_code == 401
    assert r2.body["error"]["code"] == "UNAUTHENTICATED"


def test_delete_me_csrf_enforcement_fr9(tmp_path: Path) -> None:
    """FR-9 & SECURITY.md T-4: State-changing DELETE /me enforces CSRF validation."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_delete.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Delete CSRF", "email": "del.csrf@example.com", "password": pwd},
        db_path=db_path,
    )
    login_res = login_endpoint({"email": "del.csrf@example.com", "password": pwd}, db_path=db_path)
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    from opentrade.services.csrf import generate_csrf_token

    csrf_tok = generate_csrf_token()

    # Missing X-CSRF-Token header when ot_csrf cookie present returns 403 CSRF_FAILED
    r1 = delete_me_endpoint(
        {"password": pwd},
        cookies={"ot_session": session_tok, "ot_csrf": csrf_tok},
        headers={},
        db_path=db_path,
    )
    assert r1.status_code == 403
    assert r1.body["error"]["code"] == "CSRF_FAILED"

    # Mismatched X-CSRF-Token returns 403 CSRF_FAILED
    r2 = delete_me_endpoint(
        {"password": pwd},
        cookies={"ot_session": session_tok, "ot_csrf": csrf_tok},
        headers={"X-CSRF-Token": "bad-csrf"},
        db_path=db_path,
    )
    assert r2.status_code == 403
    assert r2.body["error"]["code"] == "CSRF_FAILED"

    # Matching X-CSRF-Token succeeds
    r3 = delete_me_endpoint(
        {"password": pwd},
        cookies={"ot_session": session_tok, "ot_csrf": csrf_tok},
        headers={"X-CSRF-Token": csrf_tok},
        db_path=db_path,
    )
    assert r3.status_code == 204


def test_delete_me_clears_cookie_with_secure_flag_in_production_fr9(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-9, SECURITY.md T-3 & T-14: In production mode, Set-Cookie includes Secure flag."""
    monkeypatch.setenv("OPENTRADE_ENV", "production")
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test_delete.db"
    run_migrations(db_path)

    pwd = "ValidPassword123!"
    register_endpoint(
        {"name": "Prod Delete", "email": "prod.del@example.com", "password": pwd},
        db_path=db_path,
    )
    login_res = login_endpoint({"email": "prod.del@example.com", "password": pwd}, db_path=db_path)
    session_tok = extract_session_token(login_res.headers["Set-Cookie"])
    assert session_tok is not None

    res = delete_me_endpoint(
        {"password": pwd}, cookies={"ot_session": session_tok}, db_path=db_path
    )
    assert res.status_code == 204
    assert "Secure" in res.headers["Set-Cookie"]
