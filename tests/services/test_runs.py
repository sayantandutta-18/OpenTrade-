"""Tests for run service and ownership access isolation per AC-7 and SECURITY.md T-6."""

import sqlite3
import uuid
from pathlib import Path

import pytest

from opentrade.config import RunConfig, compute_fingerprint
from opentrade.services.auth import (
    clear_login_ip_rate_limits,
    extract_session_token,
    login_endpoint,
    register_endpoint,
)
from opentrade.services.csrf import csrf_token_endpoint
from opentrade.services.errors import NotFoundError
from opentrade.services.runs import (
    create_run,
    delete_run,
    delete_run_endpoint,
    get_run,
    get_run_endpoint,
    list_runs,
    require_user_run,
    save_run,
)
from opentrade.storage.db import get_connection
from opentrade.storage.migrate import run_migrations
from opentrade.storage.repositories import RunRepository, RunRow


def setup_test_db(tmp_path: Path) -> Path:
    """Initialize test database with migrations applied and return db_path."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "test.db"
    run_migrations(db_path)
    return db_path


def create_authenticated_user(
    db_path: Path, name: str, email: str, password: str = "CorrectHorse123!"  # noqa: S107
) -> tuple[int, str, str]:
    """Helper to register and login a user.

    Returns (user_id, session_cookie, raw_session_token).
    """
    register_endpoint({"name": name, "email": email, "password": password}, db_path=db_path)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE users SET email_verified_at = '2026-11-25T12:00:00Z' WHERE email = ?;",
            (email.strip().lower(),),
        )
    finally:
        conn.close()

    res = login_endpoint({"email": email, "password": password}, db_path=db_path)
    user_id = res.body["user"]["id"]
    set_cookie = res.headers.get("Set-Cookie", "")
    raw_token = extract_session_token(set_cookie)
    cookie_header = f"ot_session={raw_token}"
    return user_id, cookie_header, raw_token or ""


def insert_sample_run(
    conn: sqlite3.Connection,
    user_id: int,
    run_id: str | None = None,
    name: str = "Test Impact Run",
    seed: int = 42,
    provenance: str = "SYNTHETIC",
) -> RunRow:
    """Helper to insert a sample run record for a given user."""
    run_uuid = run_id or str(uuid.uuid4())
    config = {"sizes": [100, 200, 500], "book_depth": 1000}
    results = {
        "impact": [{"size": 100, "slippage_bps": 1.2}],
        "fit": {"exponent": 0.51, "ci95": [0.46, 0.56]},
        "event_log_sha256": "abcdef123456",
    }
    return create_run(
        conn=conn,
        run_id=run_uuid,
        user_id=user_id,
        name=name,
        seed=seed,
        config=config,
        fingerprint="a1b2c3d4e5f6",
        provenance=provenance,
        results=results,
        schema_version=1,
        created_at="2026-11-25T12:00:00Z",
    )


def test_cross_user_run_access_returns_404_ac7_t6(tmp_path: Path) -> None:
    """AC-7 / SECURITY.md T-6: Request authenticated as User A for User B's run ID.

    Must return 404 (not 403) so existence is not revealed.
    """
    db_path = setup_test_db(tmp_path)
    user_a_id, user_a_cookie, _ = create_authenticated_user(
        db_path, "Alice Trader", "alice@example.com"
    )
    user_b_id, user_b_cookie, _ = create_authenticated_user(
        db_path, "Bob Trader", "bob@example.com"
    )

    conn = get_connection(db_path)
    try:
        b_run = insert_sample_run(conn, user_b_id, name="Bob's Private Run")

        # Alice attempts to access Bob's run
        response, status = get_run_endpoint(conn, cookie_header=user_a_cookie, run_id=b_run.id)

        # Must return 404 NOT_FOUND, strictly avoiding 403 to prevent existence leakage
        assert status == 404, f"Expected 404 NOT_FOUND for cross-user access, got {status}"
        assert response["error"]["code"] == "NOT_FOUND"
        assert "not found" in response["error"]["message"].lower()
        assert "request_id" in response["error"]
    finally:
        conn.close()


def test_cross_user_run_deletion_returns_404_and_leaves_row_intact_ac7_t6(
    tmp_path: Path,
) -> None:
    """AC-7 / SECURITY.md T-6: User A attempting to delete User B's run.

    Returns 404 and leaves B's run intact.
    """
    db_path = setup_test_db(tmp_path)
    user_a_id, user_a_cookie, _ = create_authenticated_user(
        db_path, "Alice Trader", "alice@example.com"
    )
    user_b_id, user_b_cookie, _ = create_authenticated_user(
        db_path, "Bob Trader", "bob@example.com"
    )

    conn = get_connection(db_path)
    try:
        b_run = insert_sample_run(conn, user_b_id, name="Bob's Safe Run")

        res = csrf_token_endpoint()
        csrf_token = res.body["token"]
        csrf_cookie = res.headers["Set-Cookie"].split(";")[0]
        combined_cookie = f"{user_a_cookie}; {csrf_cookie}"

        # Alice attempts to delete Bob's run
        response, status = delete_run_endpoint(
            conn,
            cookie_header=combined_cookie,
            csrf_token=csrf_token,
            run_id=b_run.id,
        )

        # Must return 404 NOT_FOUND (never 403)
        assert status == 404, f"Expected 404 NOT_FOUND on foreign run deletion, got {status}"
        assert response["error"]["code"] == "NOT_FOUND"

        # Verify Bob's run is untouched in the database
        repo = RunRepository(conn)
        assert repo.get_by_id_and_user_id(b_run.id, user_b_id) is not None
    finally:
        conn.close()


def test_non_existent_run_returns_identical_404_ac7_t6(tmp_path: Path) -> None:
    """AC-7 / SECURITY.md T-6: Request for non-existent run ID.

    Returns identical 404 envelope as cross-user request.
    """
    db_path = setup_test_db(tmp_path)
    user_a_id, user_a_cookie, _ = create_authenticated_user(
        db_path, "Alice Trader", "alice@example.com"
    )
    random_run_id = str(uuid.uuid4())

    conn = get_connection(db_path)
    try:
        response, status = get_run_endpoint(conn, cookie_header=user_a_cookie, run_id=random_run_id)

        assert status == 404
        assert response["error"]["code"] == "NOT_FOUND"
        assert "not found" in response["error"]["message"].lower()
    finally:
        conn.close()


def test_user_can_access_own_run_ac7(tmp_path: Path) -> None:
    """AC-7: An authenticated user can successfully retrieve their own run (HTTP 200)."""
    db_path = setup_test_db(tmp_path)
    user_a_id, user_a_cookie, _ = create_authenticated_user(
        db_path, "Alice Trader", "alice@example.com"
    )

    conn = get_connection(db_path)
    try:
        a_run = insert_sample_run(conn, user_a_id, name="Alice's Run")

        response, status = get_run_endpoint(conn, cookie_header=user_a_cookie, run_id=a_run.id)

        assert status == 200
        assert "run" in response
        run_data = response["run"]
        assert run_data["id"] == a_run.id
        assert run_data["name"] == "Alice's Run"
        assert run_data["seed"] == 42
        assert run_data["provenance"] == "SYNTHETIC"
        assert run_data["schema_version"] == 1
        assert run_data["config"] == {"sizes": [100, 200, 500], "book_depth": 1000}
        assert "results" in run_data
    finally:
        conn.close()


def test_user_can_delete_own_run_ac7(tmp_path: Path) -> None:
    """AC-7: An authenticated user can successfully delete their own run (HTTP 204)."""
    db_path = setup_test_db(tmp_path)
    user_a_id, user_a_cookie, _ = create_authenticated_user(
        db_path, "Alice Trader", "alice@example.com"
    )

    conn = get_connection(db_path)
    try:
        a_run = insert_sample_run(conn, user_a_id, name="Alice's Deletable Run")

        res = csrf_token_endpoint()
        csrf_token = res.body["token"]
        csrf_cookie = res.headers["Set-Cookie"].split(";")[0]
        combined_cookie = f"{user_a_cookie}; {csrf_cookie}"

        response, status = delete_run_endpoint(
            conn,
            cookie_header=combined_cookie,
            csrf_token=csrf_token,
            run_id=a_run.id,
        )

        assert status == 204
        assert response == {}

        # Verify run is deleted from the database
        repo = RunRepository(conn)
        assert repo.get_by_id_and_user_id(a_run.id, user_a_id) is None
    finally:
        conn.close()


def test_unauthenticated_run_access_returns_401_ac7_t6(tmp_path: Path) -> None:
    """AC-7 / SECURITY.md T-6: Unauthenticated request returns 401 UNAUTHENTICATED."""
    db_path = setup_test_db(tmp_path)
    user_id, _, _ = create_authenticated_user(db_path, "Owner", "owner@example.com")

    conn = get_connection(db_path)
    try:
        run = insert_sample_run(conn, user_id)

        # GET without cookie
        response, status = get_run_endpoint(conn, cookie_header=None, run_id=run.id)
        assert status == 401
        assert response["error"]["code"] == "UNAUTHENTICATED"

        # DELETE without cookie
        del_resp, del_status = delete_run_endpoint(
            conn, cookie_header=None, csrf_token="token", run_id=run.id
        )
        assert del_status == 401
        assert del_resp["error"]["code"] == "UNAUTHENTICATED"
    finally:
        conn.close()


def test_run_deletion_csrf_enforcement_ac7_t6(tmp_path: Path) -> None:
    """AC-7 / SECURITY.md T-6: DELETE /runs/{id} requires valid CSRF token."""
    db_path = setup_test_db(tmp_path)
    user_id, cookie, _ = create_authenticated_user(db_path, "Owner", "owner@example.com")

    conn = get_connection(db_path)
    try:
        run = insert_sample_run(conn, user_id)

        res = csrf_token_endpoint()
        csrf_cookie = res.headers["Set-Cookie"].split(";")[0]

        # Missing CSRF token header
        combined_cookie = f"{cookie}; {csrf_cookie}"
        resp, status = delete_run_endpoint(
            conn, cookie_header=combined_cookie, csrf_token=None, run_id=run.id
        )
        assert status == 403
        assert resp["error"]["code"] == "CSRF_FAILED"

        # Wrong CSRF token header
        resp_wrong, status_wrong = delete_run_endpoint(
            conn,
            cookie_header=combined_cookie,
            csrf_token="wrong-token-value",
            run_id=run.id,
        )
        assert status_wrong == 403
        assert resp_wrong["error"]["code"] == "CSRF_FAILED"

        # Run still exists in DB
        repo = RunRepository(conn)
        assert repo.get_by_id_and_user_id(run.id, user_id) is not None
    finally:
        conn.close()


def test_require_user_run_guard_raises_not_found_on_mismatch_or_missing_ac7_t6(
    tmp_path: Path,
) -> None:
    """AC-7 / SECURITY.md T-6: require_user_run raises NotFoundError.

    Triggered on ownership mismatch or non-existent run ID.
    """
    db_path = setup_test_db(tmp_path)
    user_a_id, _, _ = create_authenticated_user(db_path, "User A", "usera@example.com")
    user_b_id, _, _ = create_authenticated_user(db_path, "User B", "userb@example.com")

    conn = get_connection(db_path)
    try:
        b_run = insert_sample_run(conn, user_b_id)

        # Valid owner succeeds
        run_row = require_user_run(conn, run_id=b_run.id, user_id=user_b_id)
        assert run_row.id == b_run.id
        assert run_row.user_id == user_b_id

        # Mismatched owner raises NotFoundError (never PermissionDenied / Forbidden)
        with pytest.raises(NotFoundError) as exc_info_mismatch:
            require_user_run(conn, run_id=b_run.id, user_id=user_a_id)
        assert exc_info_mismatch.value.code == "NOT_FOUND"
        assert exc_info_mismatch.value.status_code == 404

        # Non-existent run raises NotFoundError
        with pytest.raises(NotFoundError) as exc_info_missing:
            require_user_run(conn, run_id=str(uuid.uuid4()), user_id=user_a_id)
        assert exc_info_missing.value.code == "NOT_FOUND"
        assert exc_info_missing.value.status_code == 404
    finally:
        conn.close()


def test_save_list_get_delete_run_with_isolation_t1_11(tmp_path: Path) -> None:
    """T1.11, AC-7, AC-21: save_run, paginated list_runs, get_run, delete_run with 404 isolation."""
    db_path = setup_test_db(tmp_path)
    user_a_id, _, _ = create_authenticated_user(db_path, "User A", "a_t11@example.com")
    user_b_id, _, _ = create_authenticated_user(db_path, "User B", "b_t11@example.com")

    conn = get_connection(db_path)
    try:
        cfg = RunConfig(seed=42, profile_id="synthetic_default", sizes=(100, 500), book_depth=10)
        r1 = save_run(conn, user_a_id, cfg, name="Run 1", created_at="2026-11-26T00:00:01Z")
        r2 = save_run(conn, user_a_id, cfg, name="Run 2", created_at="2026-11-26T00:00:02Z")
        r3 = save_run(conn, user_a_id, cfg, name="Run 3", created_at="2026-11-26T00:00:03Z")
        b_run = save_run(conn, user_b_id, cfg, name="B Run", created_at="2026-11-26T00:00:04Z")

        assert r1.fingerprint == compute_fingerprint(cfg)
        assert r1.provenance == "SYNTHETIC"
        assert r1.schema_version == 1

        page1, next_cursor = list_runs(conn, user_a_id, limit=2)
        assert [row.id for row in page1] == [r3.id, r2.id]
        assert next_cursor == r2.created_at
        page2, cursor2 = list_runs(conn, user_a_id, limit=2, cursor=next_cursor)
        assert [row.id for row in page2] == [r1.id]
        assert cursor2 is None

        assert get_run(conn, r1.id, user_a_id).id == r1.id
        with pytest.raises(NotFoundError):
            get_run(conn, b_run.id, user_a_id)
        with pytest.raises(NotFoundError):
            delete_run(conn, b_run.id, user_a_id)

        delete_run(conn, r1.id, user_a_id)
        with pytest.raises(NotFoundError):
            get_run(conn, r1.id, user_a_id)
    finally:
        conn.close()
