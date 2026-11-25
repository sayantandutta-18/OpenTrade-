"""Email delivery adapter supporting local console logging and testing."""

import re
from dataclasses import dataclass

_TOKEN_REGEX = re.compile(r"token=([A-Za-z0-9_-]+)")


@dataclass(frozen=True)
class SentEmail:
    """Record of an email sent by the adapter."""

    to: str
    subject: str
    body: str


_sent_emails: list[SentEmail] = []


def send_email(to: str, subject: str, body: str) -> None:
    """Send an email. In local mode or during tests, logs to console and stores in memory.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Text content of the email.
    """
    record = SentEmail(to=to, subject=subject, body=body)
    _sent_emails.append(record)
    # Console logging in local mode per docs/ENVIRONMENT.md and T0.6
    print(f"[CONSOLE EMAIL] To: {to} | Subject: {subject} | Body: {body}")


def get_sent_emails() -> list[SentEmail]:
    """Retrieve all emails recorded by the local adapter."""
    return list(_sent_emails)


def clear_sent_emails() -> None:
    """Clear recorded sent emails."""
    _sent_emails.clear()


def get_last_sent_token() -> str | None:
    """Helper to extract the last generated verification/reset token from captured emails."""
    if not _sent_emails:
        return None
    last_body = _sent_emails[-1].body
    match = _TOKEN_REGEX.search(last_body)
    return match.group(1) if match else None
