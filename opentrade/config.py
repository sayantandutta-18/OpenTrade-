"""Settings loader, RunConfig, Provenance, fingerprint, and save_result.

Follows specifications in docs/ENVIRONMENT.md and docs/CODING_STANDARDS.md.
"""

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, TypeGuard

from dotenv import dotenv_values


class ValidationError(Exception):
    """Raised when environment settings are missing or malformed."""


@dataclass(frozen=True)
class Settings:
    """Application configuration loaded from environment variables or .env file."""

    environment: str
    secret_key: str
    base_url: str
    db_path: str = "./data/opentrade.db"
    log_level: str = "INFO"
    chat_hourly_limit: int = 30
    chat_daily_limit: int = 50
    analyst_daily_limit: int = 20
    run_daily_limit: int = 100
    allow_live_data: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    market_provider: str = "yfinance"
    twelve_data_api_key: str | None = None
    news_feeds: tuple[str, ...] = ()
    llm_provider: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None

    def __repr__(self) -> str:
        """Return representation with secret variables redacted per docs/ENVIRONMENT.md."""
        return (
            f"Settings(environment={self.environment!r}, "
            f"secret_key='[REDACTED]', "
            f"base_url={self.base_url!r}, "
            f"db_path={self.db_path!r}, "
            f"log_level={self.log_level!r}, "
            f"chat_hourly_limit={self.chat_hourly_limit}, "
            f"chat_daily_limit={self.chat_daily_limit}, "
            f"analyst_daily_limit={self.analyst_daily_limit}, "
            f"run_daily_limit={self.run_daily_limit}, "
            f"allow_live_data={self.allow_live_data}, "
            f"smtp_host={self.smtp_host!r}, "
            f"smtp_port={self.smtp_port}, "
            f"smtp_user={self.smtp_user!r}, "
            f"smtp_password='[REDACTED]' if self.smtp_password else None, "
            f"smtp_from={self.smtp_from!r}, "
            f"market_provider={self.market_provider!r}, "
            f"twelve_data_api_key='[REDACTED]' if self.twelve_data_api_key else None, "
            f"news_feeds={self.news_feeds!r}, "
            f"llm_provider={self.llm_provider!r}, "
            f"llm_api_key='[REDACTED]' if self.llm_api_key else None, "
            f"llm_model={self.llm_model!r})"
        )

    def __str__(self) -> str:
        """Return string representation with secret variables redacted."""
        return self.__repr__()


def _parse_bool(value: Any, default: bool = False) -> bool:
    """Parse a boolean value from environment string or boolean."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    val_str = str(value).strip().lower()
    if val_str in ("true", "1", "yes", "on"):
        return True
    if val_str in ("false", "0", "no", "off"):
        return False
    raise ValidationError(f"Invalid boolean value: {value!r}")


def _parse_int(value: Any, default: int, field_name: str) -> int:
    """Parse an integer value with validation."""
    if value is None or str(value).strip() == "":
        return default
    try:
        parsed = int(str(value).strip())
        if parsed <= 0:
            raise ValidationError(f"{field_name} must be a positive integer, got {parsed}")
        return parsed
    except ValueError as exc:
        raise ValidationError(f"{field_name} must be a valid integer, got {value!r}") from exc


def load_settings(
    env_file: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> Settings:
    """Load and validate settings from environment variables and optional .env file.

    Args:
        env_file: Optional path to .env file.
        overrides: Optional dictionary of direct overrides.

    Returns:
        Settings: Validated, immutable application settings.

    Raises:
        ValidationError: If required settings are missing or values are malformed.
    """
    raw: dict[str, Any] = {}

    # Load from .env if present or specified
    path_to_load = Path(env_file) if env_file else Path(".env")
    if path_to_load.is_file():
        raw.update(dotenv_values(path_to_load))

    # Environment variables take precedence over .env file
    for key, val in os.environ.items():
        if val is not None:
            raw[key] = val

    if overrides:
        raw.update(overrides)

    # 1. OPENTRADE_ENV
    env_val = raw.get("OPENTRADE_ENV")
    if not env_val or str(env_val).strip() == "":
        raise ValidationError("OPENTRADE_ENV is required (local, staging, production)")
    environment = str(env_val).strip().lower()
    if environment not in ("local", "staging", "production"):
        raise ValidationError(
            f"OPENTRADE_ENV must be one of ('local', 'staging', 'production'), got {env_val!r}"
        )

    # 2. OPENTRADE_SECRET_KEY
    secret_key = raw.get("OPENTRADE_SECRET_KEY")
    if not secret_key or str(secret_key).strip() == "":
        raise ValidationError("OPENTRADE_SECRET_KEY is required")
    secret_key = str(secret_key).strip()
    if len(secret_key) < 32:
        raise ValidationError("OPENTRADE_SECRET_KEY must be at least 32 characters")

    # 3. OPENTRADE_BASE_URL
    base_url_val = raw.get("OPENTRADE_BASE_URL")
    if not base_url_val or str(base_url_val).strip() == "":
        raise ValidationError("OPENTRADE_BASE_URL is required (e.g. http://localhost:8501)")
    base_url = str(base_url_val).strip().rstrip("/")

    # 4. Optional variables with defaults
    db_path = str(raw.get("OPENTRADE_DB_PATH") or "./data/opentrade.db").strip()
    log_level = str(raw.get("OPENTRADE_LOG_LEVEL") or "INFO").strip().upper()
    valid_log_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    if log_level not in valid_log_levels:
        raise ValidationError(
            f"OPENTRADE_LOG_LEVEL must be one of {valid_log_levels}, got {log_level!r}"
        )

    chat_hourly_limit = _parse_int(
        raw.get("OPENTRADE_CHAT_HOURLY_LIMIT"), 30, "OPENTRADE_CHAT_HOURLY_LIMIT"
    )
    chat_daily_limit = _parse_int(
        raw.get("OPENTRADE_CHAT_DAILY_LIMIT"), 50, "OPENTRADE_CHAT_DAILY_LIMIT"
    )
    analyst_daily_limit = _parse_int(
        raw.get("OPENTRADE_ANALYST_DAILY_LIMIT"), 20, "OPENTRADE_ANALYST_DAILY_LIMIT"
    )
    run_daily_limit = _parse_int(
        raw.get("OPENTRADE_RUN_DAILY_LIMIT"), 100, "OPENTRADE_RUN_DAILY_LIMIT"
    )

    allow_live_data = _parse_bool(raw.get("OPENTRADE_ALLOW_LIVE_DATA"), default=False)

    # 5. SMTP settings
    smtp_host = raw.get("SMTP_HOST")
    smtp_port = _parse_int(raw.get("SMTP_PORT"), 587, "SMTP_PORT")
    smtp_user = raw.get("SMTP_USER")
    smtp_password = raw.get("SMTP_PASSWORD")
    smtp_from = raw.get("SMTP_FROM")

    if environment in ("staging", "production"):
        if not smtp_host or str(smtp_host).strip() == "":
            raise ValidationError(f"SMTP_HOST is required in {environment} environment")
        if not smtp_user or str(smtp_user).strip() == "":
            raise ValidationError(f"SMTP_USER is required in {environment} environment")
        if not smtp_password or str(smtp_password).strip() == "":
            raise ValidationError(f"SMTP_PASSWORD is required in {environment} environment")
        if not smtp_from or str(smtp_from).strip() == "":
            raise ValidationError(f"SMTP_FROM is required in {environment} environment")

    # 6. Market provider
    market_provider = str(raw.get("MARKET_PROVIDER") or "yfinance").strip().lower()
    if market_provider not in ("yfinance", "twelvedata"):
        raise ValidationError(
            f"MARKET_PROVIDER must be 'yfinance' or 'twelvedata', got {market_provider!r}"
        )

    twelve_data_api_key = raw.get("TWELVE_DATA_API_KEY")
    if market_provider == "twelvedata":
        if not twelve_data_api_key or str(twelve_data_api_key).strip() == "":
            raise ValidationError(
                "TWELVE_DATA_API_KEY is required when MARKET_PROVIDER is 'twelvedata'"
            )
        twelve_data_api_key = str(twelve_data_api_key).strip()
    else:
        twelve_data_api_key = str(twelve_data_api_key).strip() if twelve_data_api_key else None

    # 7. News feeds
    news_feeds_raw = raw.get("NEWS_FEEDS")
    news_feeds: tuple[str, ...]
    if news_feeds_raw:
        news_feeds = tuple(feed.strip() for feed in str(news_feeds_raw).split(",") if feed.strip())
    else:
        news_feeds = ()

    # 8. LLM settings
    llm_provider = str(raw.get("LLM_PROVIDER")).strip() if raw.get("LLM_PROVIDER") else None
    llm_api_key = str(raw.get("LLM_API_KEY")).strip() if raw.get("LLM_API_KEY") else None
    llm_model = str(raw.get("LLM_MODEL")).strip() if raw.get("LLM_MODEL") else None

    return Settings(
        environment=environment,
        secret_key=secret_key,
        base_url=base_url,
        db_path=db_path,
        log_level=log_level,
        chat_hourly_limit=chat_hourly_limit,
        chat_daily_limit=chat_daily_limit,
        analyst_daily_limit=analyst_daily_limit,
        run_daily_limit=run_daily_limit,
        allow_live_data=allow_live_data,
        smtp_host=str(smtp_host).strip() if smtp_host else None,
        smtp_port=smtp_port,
        smtp_user=str(smtp_user).strip() if smtp_user else None,
        smtp_password=str(smtp_password).strip() if smtp_password else None,
        smtp_from=str(smtp_from).strip() if smtp_from else None,
        market_provider=market_provider,
        twelve_data_api_key=twelve_data_api_key,
        news_feeds=news_feeds,
        llm_provider=llm_provider,
        llm_api_key=llm_api_key,
        llm_model=llm_model,
    )


RESULT_SCHEMA_VERSION: int = 1


class Provenance(StrEnum):
    """Canonical data and simulation provenance labels per docs/CODING_STANDARDS.md §8."""

    REAL = "REAL"
    CALIBRATED = "CALIBRATED"
    SYNTHETIC = "SYNTHETIC"


def parse_provenance(value: Provenance | str) -> Provenance:
    """Parse and validate a provenance label against allowed values."""
    if isinstance(value, Provenance):
        return value
    normalized = str(value).strip().upper()
    try:
        return Provenance(normalized)
    except ValueError as exc:
        raise ValidationError(
            f"Invalid provenance {value!r}; expected REAL, CALIBRATED, or SYNTHETIC"
        ) from exc


def ensure_provenance_preserved(source: Provenance | str, target: Provenance | str) -> Provenance:
    """Enforce that provenance is never silently widened or changed per CODING_STANDARDS.md §8."""
    src, dst = parse_provenance(source), parse_provenance(target)
    if src is not dst:
        raise ValidationError(f"Provenance mismatch: cannot change {src.value} to {dst.value}")
    return dst


def _is_strict_int(value: Any) -> TypeGuard[int]:
    """Return True only for non-boolean integers."""
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True)
class RunConfig:
    """Immutable simulation run configuration per docs/CODING_STANDARDS.md §5 and AC-21."""

    seed: int = 42
    profile_id: str = "synthetic_default"
    sizes: tuple[int, ...] = (100, 500, 1000)
    book_depth: int = 10

    def __post_init__(self) -> None:
        """Validate run configuration fields."""
        if not _is_strict_int(self.seed):
            raise ValidationError(f"seed must be an integer, got {self.seed!r}")
        if not isinstance(self.profile_id, str) or not self.profile_id.strip():
            raise ValidationError("profile_id must be a non-empty string")
        if not self.sizes or any(not _is_strict_int(s) or s <= 0 for s in self.sizes):
            raise ValidationError("sizes must be a non-empty tuple of positive integers")
        if not _is_strict_int(self.book_depth) or self.book_depth <= 0:
            raise ValidationError(f"book_depth must be a positive integer, got {self.book_depth!r}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize RunConfig to a JSON-compatible dictionary."""
        return {
            "seed": self.seed,
            "profile_id": self.profile_id,
            "sizes": list(self.sizes),
            "book_depth": self.book_depth,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunConfig":
        """Construct a validated RunConfig from a dictionary."""
        sizes_raw = data.get("sizes")
        if not isinstance(sizes_raw, (list, tuple)):
            raise ValidationError("sizes must be a list or tuple of positive integers")
        return cls(
            seed=data.get("seed", 42),
            profile_id=str(data.get("profile_id", "")),
            sizes=tuple(sizes_raw),
            book_depth=data.get("book_depth", 10),
        )


def compute_fingerprint(config: RunConfig | dict[str, Any]) -> str:
    """Return the first 12 lowercase hex chars of SHA-256 of canonical config JSON."""
    payload = config.to_dict() if isinstance(config, RunConfig) else config
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def migrate_result(
    payload: dict[str, Any],
    target_version: int = RESULT_SCHEMA_VERSION,
    migrations: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Validate and migrate a saved result payload to target_version per docs/TRD.md §2.5."""
    version = payload.get("schema_version")
    if not _is_strict_int(version) or version < 1:
        raise ValidationError(f"Invalid schema_version: {version!r}")
    if version > target_version:
        raise ValidationError(f"Unsupported schema_version {version} (max {target_version})")
    current = dict(payload)
    registry = migrations or {}
    while version < target_version:
        migrator = registry.get(version)
        if migrator is None:
            raise ValidationError(f"No migration registered from schema_version {version}")
        current = migrator(current)
        version += 1
        current["schema_version"] = version
    return current


def save_result(
    config: RunConfig,
    results: dict[str, Any],
    provenance: Provenance | str,
    results_dir: str | Path = Path("results"),
    created_at: str | None = None,
    output_path: str | Path | None = None,
) -> Path:
    """Save a run result JSON file with provenance and schema_version per AC-21."""
    validated_provenance = parse_provenance(provenance)
    fingerprint = compute_fingerprint(config)
    payload: dict[str, Any] = {
        "config": config.to_dict(),
        "seed": config.seed,
        "fingerprint": fingerprint,
        "provenance": validated_provenance.value,
        "schema_version": RESULT_SCHEMA_VERSION,
        "created_at": created_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "results": results,
    }
    target = Path(output_path or Path(results_dir) / f"{fingerprint}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def load_result(path: str | Path) -> dict[str, Any]:
    """Load and migrate a saved result JSON file from disk."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValidationError("Saved result file must contain a JSON object")
    return migrate_result(raw)
