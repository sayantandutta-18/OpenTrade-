"""Phase 1 end-to-end integration and performance benchmark tests (T1.12).

Follows docs/TRD.md (§4 performance targets), docs/ACCEPTANCE_CRITERIA.md (AC-21).
"""

import json
import time
from pathlib import Path

from opentrade.config import RunConfig, compute_fingerprint
from opentrade.engine.book import OrderBook, OrderType, Side
from opentrade.engine.matching import submit_order
from opentrade.engine.runner import run_simulation
from opentrade.services.auth import clear_login_ip_rate_limits, register_endpoint
from opentrade.services.runs import get_run, save_run
from opentrade.storage.db import get_connection
from opentrade.storage.migrate import run_migrations
from opentrade.storage.repositories import UserRepository


def test_phase1_end_to_end_presets_and_persistence(tmp_path: Path) -> None:
    """T1.12, AC-21: Run preset profiles through engine and persist verified runs to SQLite."""
    clear_login_ip_rate_limits()
    db_path = tmp_path / "phase1_e2e.db"
    run_migrations(db_path)

    status, _ = register_endpoint(
        {"name": "Quant", "email": "quant@example.com", "password": "QuantStrongPassword99!"},
        db_path=db_path,
    )
    assert status == 201

    conn = get_connection(db_path)
    try:
        user = UserRepository(conn).get_by_email("quant@example.com")
        assert user is not None

        for profile_id, expected_prov in (
            ("synthetic_default", "SYNTHETIC"),
            ("thin_book", "SYNTHETIC"),
            ("deep_book", "CALIBRATED"),
            ("high_volatility", "SYNTHETIC"),
        ):
            cfg = RunConfig(seed=42, profile_id=profile_id, sizes=(100, 500, 1000), book_depth=15)
            sim = run_simulation(
                seed=cfg.seed,
                profile_id=cfg.profile_id,
                sizes=cfg.sizes,
                book_depth=cfg.book_depth,
            )
            saved = save_run(
                conn=conn,
                user_id=user.id,
                config=cfg,
                name=f"E2E {profile_id}",
                results=sim.to_dict(),
                provenance=sim.provenance.value,
            )
            loaded = get_run(conn, saved.id, user.id)
            assert loaded.fingerprint == compute_fingerprint(cfg)
            assert loaded.provenance == expected_prov
            assert json.loads(loaded.result_json)["event_log_sha256"] == sim.event_log_sha256
    finally:
        conn.close()


def test_phase1_performance_targets_trd_section_4() -> None:
    """T1.12, TRD.md §4: Single order injection < 10 ms; 20-size sweep < 30 s."""
    book = OrderBook()
    for i in range(1, 50):
        submit_order(book, Side.BUY, OrderType.LIMIT, qty=100, price_ticks=10_000 - i)
        submit_order(book, Side.SELL, OrderType.LIMIT, qty=100, price_ticks=10_000 + i)

    t0 = time.perf_counter()
    submit_order(book, Side.BUY, OrderType.MARKET, qty=500)
    inject_ms = (time.perf_counter() - t0) * 1000.0
    assert inject_ms < 10.0, f"Single order injection took {inject_ms:.2f} ms (target < 10 ms)"

    sizes_20 = tuple(100 * i for i in range(1, 21))
    t1 = time.perf_counter()
    res = run_simulation(seed=42, profile_id="synthetic_default", sizes=sizes_20, book_depth=10)
    sweep_s = time.perf_counter() - t1
    assert len(res.points) == 80  # 20 sizes x 4 strategies
    assert sweep_s < 30.0, f"20-size sweep took {sweep_s:.2f} s (target < 30 s)"
