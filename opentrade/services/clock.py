"""Clock helper providing standard ISO 8601 UTC timestamps."""

from datetime import UTC, datetime, timedelta


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string ending in 'Z'."""
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def add_hours_iso(hours: int = 24) -> str:
    """Return an ISO 8601 UTC timestamp offset by a given number of hours in the future."""
    future = datetime.now(UTC) + timedelta(hours=hours)
    return future.strftime("%Y-%m-%dT%H:%M:%SZ")


def add_days_iso(days: int = 14) -> str:
    """Return an ISO 8601 UTC timestamp offset by a given number of days in the future."""
    future = datetime.now(UTC) + timedelta(days=days)
    return future.strftime("%Y-%m-%dT%H:%M:%SZ")


def add_days_from_iso(base_iso: str, days: int = 30) -> str:
    """Return an ISO 8601 UTC timestamp offset by a given number of days from base_iso."""
    clean_str = base_iso.replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean_str)
    future = dt + timedelta(days=days)
    return future.strftime("%Y-%m-%dT%H:%M:%SZ")


def add_minutes_iso(minutes: int = 15) -> str:
    """Return an ISO 8601 UTC timestamp offset by a given number of minutes in the future."""
    future = datetime.now(UTC) + timedelta(minutes=minutes)
    return future.strftime("%Y-%m-%dT%H:%M:%SZ")


def hours_ago_iso(hours: int = 1) -> str:
    """Return an ISO 8601 UTC timestamp offset by a given number of hours in the past."""
    past = datetime.now(UTC) - timedelta(hours=hours)
    return past.strftime("%Y-%m-%dT%H:%M:%SZ")


def is_expired(expires_at_iso: str) -> bool:
    """Check whether an ISO 8601 UTC timestamp has passed.

    Args:
        expires_at_iso: Timestamp string to compare against current UTC time.

    Returns:
        bool: True if expires_at is in the past, False otherwise.
    """
    clean_str = expires_at_iso.replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean_str)
    return dt <= datetime.now(UTC)


def is_within_minutes(timestamp_iso: str, minutes: int = 10) -> bool:
    """Check whether a past ISO 8601 UTC timestamp occurred within the last `minutes`.

    Args:
        timestamp_iso: ISO 8601 timestamp string.
        minutes: Window duration in minutes.

    Returns:
        bool: True if timestamp is within the last `minutes`, False if older.
    """
    clean_str = timestamp_iso.replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean_str)
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=minutes)
    return dt >= cutoff
