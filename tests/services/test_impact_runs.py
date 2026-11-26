"""Tests for impact run service and persistence gating (T3.4, AC-21).

Follows docs/ACCEPTANCE_CRITERIA.md (AC-7, AC-21), docs/API_SPEC.md (§3),
and docs/SRS.md (FR-27, FR-52).
"""

import json
from pathlib import Path

from opentrade.config import RunConfig, compute_fingerprint
from opentrade.services.auth import clear_login_ip_rate_limits, register_endpoint
from opentrade.services.runs import (
    get_run,
    list_available_profiles,
    preview_book_and_inject,
    save_impact_run,
)
from opentrade.storage.db import get_connection
from opentrade.storage.migrate import run_migrations
from opentrade.storage.repositories import RunRepository, UserRepository


def test_save_impact_run_persists_for_verified_user_ac21(tmp_path: Path) -> None:
    """T3.4, AC-21, FR-27: Verified user saves impact sweep + decay with fingerprint."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "impact_run.db"
    run_migrations(db_path)

    status, _ = register_endpoint(
        {"name": "Ada", "email": "ada@example.com", "password": "AdaStrongPassword99!"},
        db_path=db_path,
    )
    assert status == 201

    conn = get_connection(db_path)
    try:
        user = UserRepository(conn).get_by_email("ada@example.com")
        assert user is not None

        cfg = RunConfig(
            seed=42,
            profile_id="synthetic_default",
            sizes=(100, 300, 1000, 3000, 6000, 10000),
            book_depth=15,
        )
        run_dict, saved = save_impact_run(
            conn=conn,
            user_id=user.id,
            is_verified=True,
            config=cfg,
            name="Default Impact Sweep",
        )
        assert saved is True
        assert run_dict["fingerprint"] == compute_fingerprint(cfg)
        assert run_dict["provenance"] == "SYNTHETIC"
        assert run_dict["schema_version"] == 1
        assert 0.4 <= run_dict["results"]["fit"]["beta"] <= 0.6
        assert len(run_dict["results"]["decay"]["curve"]) >= 2

        loaded = get_run(conn, run_dict["id"], user.id)
        assert loaded.fingerprint == compute_fingerprint(cfg)
        assert json.loads(loaded.result_json)["event_log_sha256"] == (
            run_dict["results"]["event_log_sha256"]
        )
    finally:
        conn.close()


def test_save_impact_run_does_not_persist_for_demo_or_unverified(tmp_path: Path) -> None:
    """T3.4, API_SPEC §3: Demo mode and unverified users run sweep without writing to SQLite."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "impact_demo.db"
    run_migrations(db_path)
    conn = get_connection(db_path)
    try:
        cfg = RunConfig(seed=42, profile_id="deep_book", sizes=(100, 300, 1000, 3000, 6000, 10000))

        demo_dict, demo_saved = save_impact_run(
            conn=conn,
            user_id=None,
            is_verified=False,
            config=cfg,
            name="Demo Sweep",
        )
        assert demo_saved is False
        assert demo_dict["provenance"] == "CALIBRATED"
        assert demo_dict["fingerprint"] == compute_fingerprint(cfg)

        unverified_dict, unverified_saved = save_impact_run(
            conn=conn,
            user_id=999,
            is_verified=False,
            config=cfg,
            name="Unverified Sweep",
        )
        assert unverified_saved is False
        assert unverified_dict["fingerprint"] == compute_fingerprint(cfg)

        assert RunRepository(conn).list_by_user_id(999) == []
    finally:
        conn.close()


def test_preview_book_and_inject_returns_depth_and_slippage() -> None:
    """T3.4, T3.5: Service helper returns book depth snapshot and injection slippage."""
    profiles = list_available_profiles()
    assert "synthetic_default" in profiles
    assert "deep_book" in profiles

    snap = preview_book_and_inject(
        profile_id="synthetic_default",
        seed=42,
        side="BUY",
        qty=400,
    )
    assert snap["provenance"] == "SYNTHETIC"
    assert snap["injection"]["filled_qty"] == 400
    assert snap["injection"]["slippage_bps"] > 0.0
    assert len(snap["bids"]) > 0
    assert len(snap["asks"]) > 0
