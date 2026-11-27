"""Tests for settings loader and environment validation per docs/ENVIRONMENT.md."""

import json
import re
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from opentrade.config import (
    RESULT_SCHEMA_VERSION,
    Provenance,
    RunConfig,
    ValidationError,
    compute_fingerprint,
    ensure_provenance_preserved,
    load_result,
    load_settings,
    migrate_result,
    parse_provenance,
    save_result,
)


@pytest.fixture(autouse=True)
def _isolate_cwd_from_repo_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent tests/test_config.py from reading a developer's local .env file."""
    monkeypatch.chdir(tmp_path)


def test_valid_minimal_local_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings test: Validate that minimal required settings load successfully with defaults."""
    env = {
        "OPENTRADE_ENV": "local",
        "OPENTRADE_SECRET_KEY": "a" * 32,
        "OPENTRADE_BASE_URL": "http://localhost:8501",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    settings = load_settings()
    assert settings.environment == "local"
    assert settings.secret_key == "a" * 32
    assert settings.base_url == "http://localhost:8501"
    assert settings.db_path == "./data/opentrade.db"
    assert settings.log_level == "INFO"
    assert settings.chat_hourly_limit == 30
    assert settings.chat_daily_limit == 50
    assert settings.analyst_daily_limit == 20
    assert settings.run_daily_limit == 100
    assert settings.allow_live_data is False
    assert settings.market_provider == "yfinance"
    assert settings.smtp_port == 587
    assert settings.llm_provider is None


def test_missing_environment_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings test: Refuse to start if OPENTRADE_ENV is missing."""
    monkeypatch.delenv("OPENTRADE_ENV", raising=False)
    monkeypatch.setenv("OPENTRADE_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("OPENTRADE_BASE_URL", "http://localhost:8501")

    with pytest.raises(ValidationError, match="OPENTRADE_ENV is required"):
        load_settings()


def test_invalid_environment_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings test: Refuse to start if OPENTRADE_ENV is not local, staging, or production."""
    monkeypatch.setenv("OPENTRADE_ENV", "dev")
    monkeypatch.setenv("OPENTRADE_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("OPENTRADE_BASE_URL", "http://localhost:8501")

    with pytest.raises(ValidationError, match="OPENTRADE_ENV must be one of"):
        load_settings()


def test_missing_secret_key_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings test: Refuse to start if OPENTRADE_SECRET_KEY is missing."""
    monkeypatch.setenv("OPENTRADE_ENV", "local")
    monkeypatch.delenv("OPENTRADE_SECRET_KEY", raising=False)
    monkeypatch.setenv("OPENTRADE_BASE_URL", "http://localhost:8501")

    with pytest.raises(ValidationError, match="OPENTRADE_SECRET_KEY is required"):
        load_settings()


def test_short_secret_key_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings test: Refuse to start if OPENTRADE_SECRET_KEY is shorter than 32 characters."""
    monkeypatch.setenv("OPENTRADE_ENV", "local")
    monkeypatch.setenv("OPENTRADE_SECRET_KEY", "too-short-secret")
    monkeypatch.setenv("OPENTRADE_BASE_URL", "http://localhost:8501")

    with pytest.raises(
        ValidationError, match="OPENTRADE_SECRET_KEY must be at least 32 characters"
    ):
        load_settings()


def test_missing_base_url_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings test: Refuse to start if OPENTRADE_BASE_URL is missing."""
    monkeypatch.setenv("OPENTRADE_ENV", "local")
    monkeypatch.setenv("OPENTRADE_SECRET_KEY", "a" * 32)
    monkeypatch.delenv("OPENTRADE_BASE_URL", raising=False)

    with pytest.raises(ValidationError, match="OPENTRADE_BASE_URL is required"):
        load_settings()


@pytest.mark.parametrize("env_name", ["staging", "production"])
def test_staging_production_require_smtp_host(
    monkeypatch: pytest.MonkeyPatch, env_name: str
) -> None:
    """Settings test: Staging and production require SMTP_HOST."""
    monkeypatch.setenv("OPENTRADE_ENV", env_name)
    monkeypatch.setenv("OPENTRADE_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("OPENTRADE_BASE_URL", "https://example.com")

    with pytest.raises(ValidationError, match="SMTP_HOST is required"):
        load_settings()


@pytest.mark.parametrize(
    ("missing_field", "match_str"),
    [
        ("SMTP_USER", "SMTP_USER is required"),
        ("SMTP_PASSWORD", "SMTP_PASSWORD is required"),
        ("SMTP_FROM", "SMTP_FROM is required"),
    ],
)
def test_staging_production_require_all_smtp_fields(
    monkeypatch: pytest.MonkeyPatch, missing_field: str, match_str: str
) -> None:
    """Settings test: Staging and production require SMTP_USER, SMTP_PASSWORD, and SMTP_FROM."""
    monkeypatch.setenv("OPENTRADE_ENV", "production")
    monkeypatch.setenv("OPENTRADE_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("OPENTRADE_BASE_URL", "https://example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "no-reply@example.com")
    monkeypatch.delenv(missing_field)

    with pytest.raises(ValidationError, match=match_str):
        load_settings()


def test_twelvedata_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings test: MARKET_PROVIDER twelvedata requires TWELVE_DATA_API_KEY."""
    monkeypatch.setenv("OPENTRADE_ENV", "local")
    monkeypatch.setenv("OPENTRADE_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("OPENTRADE_BASE_URL", "http://localhost:8501")
    monkeypatch.setenv("MARKET_PROVIDER", "twelvedata")
    monkeypatch.delenv("TWELVE_DATA_API_KEY", raising=False)

    with pytest.raises(ValidationError, match="TWELVE_DATA_API_KEY is required"):
        load_settings()


def test_invalid_log_level_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings test: OPENTRADE_LOG_LEVEL must be a valid log level."""
    monkeypatch.setenv("OPENTRADE_ENV", "local")
    monkeypatch.setenv("OPENTRADE_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("OPENTRADE_BASE_URL", "http://localhost:8501")
    monkeypatch.setenv("OPENTRADE_LOG_LEVEL", "TRACE")

    with pytest.raises(ValidationError, match="OPENTRADE_LOG_LEVEL must be one of"):
        load_settings()


def test_invalid_boolean_allow_live_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings test: Invalid boolean string for ALLOW_LIVE_DATA raises ValidationError."""
    monkeypatch.setenv("OPENTRADE_ENV", "local")
    monkeypatch.setenv("OPENTRADE_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("OPENTRADE_BASE_URL", "http://localhost:8501")
    monkeypatch.setenv("OPENTRADE_ALLOW_LIVE_DATA", "not-a-bool")

    with pytest.raises(ValidationError, match="Invalid boolean value"):
        load_settings()


def test_invalid_integer_limit_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings test: Non-positive or non-integer rate limits raise ValidationError."""
    monkeypatch.setenv("OPENTRADE_ENV", "local")
    monkeypatch.setenv("OPENTRADE_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("OPENTRADE_BASE_URL", "http://localhost:8501")
    monkeypatch.setenv("OPENTRADE_CHAT_HOURLY_LIMIT", "-5")

    with pytest.raises(ValidationError, match="must be a positive integer"):
        load_settings()


def test_news_feeds_parsed_as_tuple(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings test: NEWS_FEEDS comma-separated string parsed into a clean tuple."""
    monkeypatch.setenv("OPENTRADE_ENV", "local")
    monkeypatch.setenv("OPENTRADE_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("OPENTRADE_BASE_URL", "http://localhost:8501")
    monkeypatch.setenv("NEWS_FEEDS", "https://feed1.rss, https://feed2.rss ")

    settings = load_settings()
    assert settings.news_feeds == ("https://feed1.rss", "https://feed2.rss")


def test_empty_llm_provider_allowed_for_demo_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings test: If LLM_PROVIDER is empty, the app starts in demo mode without error."""
    monkeypatch.setenv("OPENTRADE_ENV", "local")
    monkeypatch.setenv("OPENTRADE_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("OPENTRADE_BASE_URL", "http://localhost:8501")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    settings = load_settings()
    assert settings.llm_provider is None
    assert settings.llm_api_key is None


def test_secrets_redacted_in_repr_and_str(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings test: Secrets are never printed or logged via str or repr."""
    secret = "x" * 64
    smtp_pass = "super-secret-smtp-password"
    twelve_key = "secret-twelve-data-key"
    llm_key = "secret-llm-api-key"

    monkeypatch.setenv("OPENTRADE_ENV", "local")
    monkeypatch.setenv("OPENTRADE_SECRET_KEY", secret)
    monkeypatch.setenv("OPENTRADE_BASE_URL", "http://localhost:8501")
    monkeypatch.setenv("SMTP_PASSWORD", smtp_pass)
    monkeypatch.setenv("TWELVE_DATA_API_KEY", twelve_key)
    monkeypatch.setenv("LLM_API_KEY", llm_key)

    settings = load_settings()
    for text in (str(settings), repr(settings)):
        assert secret not in text
        assert smtp_pass not in text
        assert twelve_key not in text
        assert llm_key not in text
        assert "[REDACTED]" in text


def test_run_config_is_frozen_and_validates_fields() -> None:
    """AC-21, FR-27, CODING_STANDARDS.md §5: RunConfig is frozen and validates fields."""
    cfg = RunConfig(seed=42, profile_id="AAPL", sizes=(100, 500, 1000), book_depth=15)
    assert cfg.seed == 42
    assert cfg.profile_id == "AAPL"
    assert cfg.sizes == (100, 500, 1000)
    assert cfg.book_depth == 15

    with pytest.raises(FrozenInstanceError):
        cfg.seed = 99  # type: ignore[misc]

    roundtrip = RunConfig.from_dict(cfg.to_dict())
    assert roundtrip == cfg

    with pytest.raises(ValidationError):
        RunConfig(seed=True, profile_id="AAPL", sizes=(100,))
    with pytest.raises(ValidationError):
        RunConfig(seed=42, profile_id="   ", sizes=(100,))
    with pytest.raises(ValidationError):
        RunConfig(seed=42, profile_id="AAPL", sizes=())
    with pytest.raises(ValidationError):
        RunConfig(seed=42, profile_id="AAPL", sizes=(100, 0))
    with pytest.raises(ValidationError):
        RunConfig(seed=42, profile_id="AAPL", sizes=(100,), book_depth=0)


def test_compute_fingerprint_is_deterministic_12_hex_chars() -> None:
    """AC-21, FR-27: compute_fingerprint returns deterministic 12-char lowercase hex SHA-256."""
    cfg1 = RunConfig(seed=42, profile_id="synthetic_default", sizes=(100, 500), book_depth=10)
    cfg2 = RunConfig(seed=42, profile_id="synthetic_default", sizes=(100, 500), book_depth=10)

    fp1 = compute_fingerprint(cfg1)
    fp2 = compute_fingerprint(cfg2)

    assert fp1 == fp2
    assert re.fullmatch(r"[0-9a-f]{12}", fp1) is not None

    # Dict key ordering must not affect the canonical JSON fingerprint
    dict_a = {"seed": 42, "profile_id": "synthetic_default", "sizes": [100, 500], "book_depth": 10}
    dict_b = {"book_depth": 10, "sizes": [100, 500], "profile_id": "synthetic_default", "seed": 42}
    assert compute_fingerprint(dict_a) == fp1
    assert compute_fingerprint(dict_b) == fp1

    # Changing any simulation parameter yields a distinct fingerprint
    assert (
        compute_fingerprint(RunConfig(seed=43, profile_id="synthetic_default", sizes=(100, 500)))
        != fp1
    )
    assert compute_fingerprint(RunConfig(seed=42, profile_id="MSFT", sizes=(100, 500))) != fp1
    assert (
        compute_fingerprint(RunConfig(seed=42, profile_id="synthetic_default", sizes=(100, 600)))
        != fp1
    )
    assert (
        compute_fingerprint(
            RunConfig(seed=42, profile_id="synthetic_default", sizes=(100, 500), book_depth=20)
        )
        != fp1
    )


def test_provenance_strict_validation_and_no_silent_widening() -> None:
    """FR-52, CODING_STANDARDS.md §8: Provenance restricts values and prevents silent widening."""
    assert Provenance.REAL.value == "REAL"
    assert Provenance.CALIBRATED.value == "CALIBRATED"
    assert Provenance.SYNTHETIC.value == "SYNTHETIC"
    assert {p.value for p in Provenance} == {"REAL", "CALIBRATED", "SYNTHETIC"}

    assert parse_provenance("REAL") is Provenance.REAL
    assert parse_provenance(Provenance.CALIBRATED) is Provenance.CALIBRATED
    assert parse_provenance("synthetic") is Provenance.SYNTHETIC

    for bad in ("", "SIMULATED", "ESTIMATED", "FAKE", "unknown"):
        with pytest.raises(ValidationError):
            parse_provenance(bad)

    # Identical provenance is preserved
    preserved = ensure_provenance_preserved(Provenance.SYNTHETIC, Provenance.SYNTHETIC)
    assert preserved is Provenance.SYNTHETIC
    assert ensure_provenance_preserved(Provenance.REAL, Provenance.REAL) is Provenance.REAL

    # Never label synthetic/calibrated as REAL or silently change provenance
    with pytest.raises(ValidationError):
        ensure_provenance_preserved(Provenance.SYNTHETIC, Provenance.REAL)
    with pytest.raises(ValidationError):
        ensure_provenance_preserved(Provenance.CALIBRATED, Provenance.REAL)
    with pytest.raises(ValidationError):
        ensure_provenance_preserved(Provenance.REAL, Provenance.SYNTHETIC)


def test_save_result_writes_complete_ac21_payload(tmp_path: Path) -> None:
    """AC-21, FR-27, FR-52: save_result writes config, seed, fingerprint, provenance,
    schema_version, created_at, and results.
    """
    cfg = RunConfig(seed=7, profile_id="NVDA", sizes=(50, 200), book_depth=12)
    results = {
        "impact": [{"size": 50, "slippage_bps": 1.1}],
        "event_log_sha256": "deadbeef" * 8,
    }
    output_path = save_result(
        config=cfg,
        results=results,
        provenance=Provenance.CALIBRATED,
        results_dir=tmp_path,
        created_at="2026-11-26T00:00:00Z",
    )

    expected_fp = compute_fingerprint(cfg)
    assert output_path == tmp_path / f"{expected_fp}.json"
    assert output_path.is_file()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["config"] == cfg.to_dict()
    assert payload["seed"] == 7
    assert payload["fingerprint"] == expected_fp
    assert payload["provenance"] == "CALIBRATED"
    assert payload["schema_version"] == RESULT_SCHEMA_VERSION == 1
    assert payload["created_at"] == "2026-11-26T00:00:00Z"
    assert payload["results"] == results


def test_load_result_and_migrate_result_handle_versions(tmp_path: Path) -> None:
    """AC-21, TRD.md §2.5: load_result and migrate_result validate and migrate schema_version."""
    cfg = RunConfig(seed=11, profile_id="synthetic_default", sizes=(100,))
    saved_path = save_result(
        config=cfg,
        results={"impact": []},
        provenance="SYNTHETIC",
        results_dir=tmp_path,
        created_at="2026-11-26T00:00:00Z",
    )

    loaded = load_result(saved_path)
    assert loaded["schema_version"] == 1
    assert loaded["fingerprint"] == compute_fingerprint(cfg)

    # Invalid or unsupported schema versions are rejected
    for bad_payload in (
        {"config": cfg.to_dict()},  # missing schema_version
        {"schema_version": "1"},  # non-int
        {"schema_version": True},  # bool
        {"schema_version": 0},  # < 1
        {"schema_version": RESULT_SCHEMA_VERSION + 1},  # future unsupported version
    ):
        with pytest.raises(ValidationError):
            migrate_result(bad_payload)

    # Migration hook runs when target_version > source version
    v0_style = dict(loaded)
    v0_style["schema_version"] = 1
    migrated = migrate_result(
        v0_style,
        target_version=2,
        migrations={1: lambda data: {**data, "schema_version": 2, "migrated": True}},
    )
    assert migrated["schema_version"] == 2
    assert migrated["migrated"] is True
