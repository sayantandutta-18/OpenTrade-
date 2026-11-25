"""Run configuration, execution, result persistence, and ownership access isolation.

Follows docs/API_SPEC.md (§3), docs/SECURITY.md (T-6), and docs/ACCEPTANCE_CRITERIA.md (AC-7).
"""

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any

from opentrade.config import (
    RESULT_SCHEMA_VERSION,
    Provenance,
    RunConfig,
    compute_fingerprint,
    parse_provenance,
)
from opentrade.engine.runner import run_simulation
from opentrade.services.auth import authenticate_session, extract_session_token
from opentrade.services.csrf import verify_csrf_token
from opentrade.services.errors import AppError, NotFoundError, UnauthenticatedError
from opentrade.storage.repositories import RunRepository, RunRow


def require_user_run(conn: sqlite3.Connection, run_id: str, user_id: int) -> RunRow:
    """Ownership guard fetching a run strictly scoped to the requesting user.

    SECURITY.md T-6 / AC-7:
    Every query filters by user_id. When the run does not exist or belongs to
    another user, NotFoundError (HTTP 404) is raised. Under no circumstances is 403
    returned, ensuring resource existence is never revealed.

    Args:
        conn: Active SQLite database connection.
        run_id: UUID string of the target run.
        user_id: ID of the authenticated user.

    Returns:
        RunRow: The user's run record if found.

    Raises:
        NotFoundError: If the run does not exist or belongs to another user.
    """
    repo = RunRepository(conn)
    run = repo.get_by_id_and_user_id(run_id=run_id, user_id=user_id)
    if run is None:
        raise NotFoundError("Run not found")
    return run


def delete_user_run(conn: sqlite3.Connection, run_id: str, user_id: int) -> None:
    """Delete a run strictly scoped to the requesting user.

    SECURITY.md T-6 / AC-7:
    Returns 404 NOT_FOUND if the run does not exist or belongs to another user.
    Zero rows of other users are ever affected.

    Args:
        conn: Active SQLite database connection.
        run_id: UUID string of the target run.
        user_id: ID of the authenticated user.

    Raises:
        NotFoundError: If the run does not exist or belongs to another user.
    """
    repo = RunRepository(conn)
    deleted_count = repo.delete_by_id_and_user_id(run_id=run_id, user_id=user_id)
    if deleted_count == 0:
        raise NotFoundError("Run not found")


def format_run_dict(run: RunRow) -> dict[str, Any]:
    """Format a RunRow database record into the JSON response object per docs/API_SPEC.md §3."""
    return {
        "id": run.id,
        "name": run.name,
        "seed": run.seed,
        "fingerprint": run.fingerprint,
        "provenance": run.provenance,
        "schema_version": run.schema_version,
        "created_at": run.created_at,
        "config": json.loads(run.config_json),
        "results": json.loads(run.result_json),
    }


def create_run(
    conn: sqlite3.Connection,
    run_id: str,
    user_id: int,
    name: str,
    seed: int,
    config: dict[str, Any],
    fingerprint: str,
    provenance: str,
    results: dict[str, Any],
    schema_version: int = 1,
    created_at: str | None = None,
) -> RunRow:
    """Insert and persist a new run for a user using strictly parameterized SQL.

    Args:
        conn: Active SQLite database connection.
        run_id: UUID string identifier for the run.
        user_id: Owning user foreign key.
        name: Name of the run.
        seed: Random seed used in simulation.
        config: Dictionary representing the run configuration.
        fingerprint: Hash/fingerprint of the configuration.
        provenance: Provenance tag (REAL, CALIBRATED, or SYNTHETIC).
        results: Dictionary containing the run results.
        schema_version: Schema version integer (defaults to 1).
        created_at: ISO 8601 UTC creation timestamp (defaults to current time).

    Returns:
        RunRow: The newly inserted run record.
    """
    now_iso = created_at or datetime.now(UTC).isoformat()
    repo = RunRepository(conn)
    return repo.create(
        id=run_id,
        user_id=user_id,
        name=name,
        seed=seed,
        config_json=json.dumps(config),
        fingerprint=fingerprint,
        provenance=provenance,
        result_json=json.dumps(results),
        schema_version=schema_version,
        created_at=now_iso,
    )


def get_run_endpoint(
    conn: sqlite3.Connection,
    cookie_header: str | None,
    run_id: str,
) -> tuple[dict[str, Any], int]:
    """Handler for GET /api/v1/runs/{id} per docs/API_SPEC.md §3 and AC-7.

    Requires valid session authentication.
    Returns 200 {"run": {...}} on success.
    Returns 404 NOT_FOUND (never 403) if the run is missing or belongs to another user.
    Returns 401 UNAUTHENTICATED if session is missing or invalid.
    """
    request_id = str(uuid.uuid4())
    try:
        raw_token = extract_session_token(cookie_header)
        if not raw_token:
            raise UnauthenticatedError("Authentication required")

        user = authenticate_session(conn, raw_token)
        run = require_user_run(conn, run_id=run_id, user_id=user.id)
        return {"run": format_run_dict(run)}, 200
    except AppError as err:
        err.request_id = request_id
        return err.to_dict(), err.status_code
    except Exception:
        err_dict = {
            "error": {
                "code": "INTERNAL",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            }
        }
        return err_dict, 500


def delete_run_endpoint(
    conn: sqlite3.Connection,
    cookie_header: str | None,
    csrf_token: str | None,
    run_id: str,
    enforce_csrf: bool = False,
) -> tuple[dict[str, Any], int]:
    """Handler for DELETE /api/v1/runs/{id} per docs/API_SPEC.md §3 and AC-7.

    Requires valid session authentication and valid CSRF token header.
    Returns 204 on success.
    Returns 404 NOT_FOUND (never 403) if the run is missing or belongs to another user.
    Returns 401 UNAUTHENTICATED if session is missing or invalid.
    Returns 403 CSRF_FAILED if CSRF token is missing or invalid.
    """
    request_id = str(uuid.uuid4())
    try:
        raw_token = extract_session_token(cookie_header)
        if not raw_token:
            raise UnauthenticatedError("Authentication required")

        user = authenticate_session(conn, raw_token)

        # Validate CSRF for state-changing DELETE request
        headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}
        verify_csrf_token(method="DELETE", headers=headers, cookies=cookie_header)

        delete_user_run(conn, run_id=run_id, user_id=user.id)
        return {}, 204
    except AppError as err:
        err.request_id = request_id
        return err.to_dict(), err.status_code
    except Exception:
        err_dict = {
            "error": {
                "code": "INTERNAL",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            }
        }
        return err_dict, 500


def save_run(
    conn: sqlite3.Connection,
    user_id: int,
    config: RunConfig,
    name: str,
    results: dict[str, Any] | None = None,
    provenance: Provenance | str | None = None,
    run_id: str | None = None,
    created_at: str | None = None,
) -> RunRow:
    """Execute (if needed) and persist a run with fingerprint, provenance, and schema_version."""
    if results is None:
        sim = run_simulation(
            seed=config.seed,
            profile_id=config.profile_id,
            sizes=config.sizes,
            book_depth=config.book_depth,
        )
        resolved_results = sim.to_dict()
        resolved_prov = parse_provenance(provenance or sim.provenance.value)
    else:
        resolved_results = results
        resolved_prov = parse_provenance(provenance or Provenance.SYNTHETIC)

    return create_run(
        conn=conn,
        run_id=run_id or str(uuid.uuid4()),
        user_id=user_id,
        name=name,
        seed=config.seed,
        config=config.to_dict(),
        fingerprint=compute_fingerprint(config),
        provenance=resolved_prov.value,
        results=resolved_results,
        schema_version=RESULT_SCHEMA_VERSION,
        created_at=created_at,
    )


def get_run(conn: sqlite3.Connection, run_id: str, user_id: int) -> RunRow:
    """Fetch a run strictly scoped to user_id (raises NotFoundError 404 otherwise)."""
    return require_user_run(conn, run_id=run_id, user_id=user_id)


def delete_run(conn: sqlite3.Connection, run_id: str, user_id: int) -> None:
    """Delete a run strictly scoped to user_id (raises NotFoundError 404 otherwise)."""
    delete_user_run(conn, run_id=run_id, user_id=user_id)


def list_runs(
    conn: sqlite3.Connection,
    user_id: int,
    limit: int = 50,
    cursor: str | None = None,
) -> tuple[list[RunRow], str | None]:
    """List recent runs for user_id with cursor pagination (max 50 per page)."""
    clamped = max(1, min(50, limit))
    rows = RunRepository(conn).list_by_user_id(
        user_id=user_id,
        limit=clamped + 1,
        cursor_created_at=cursor,
    )
    if len(rows) > clamped:
        page = rows[:clamped]
        return page, page[-1].created_at
    return rows, None
