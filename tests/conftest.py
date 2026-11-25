"""Shared pytest fixtures and configuration."""

import socket

import pytest


@pytest.fixture(autouse=True)
def block_network_access(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Block network access during tests unless explicitly marked with @pytest.mark.network."""
    if request.node.get_closest_marker("network"):
        return

    orig_connect = socket.socket.connect
    orig_socketpair = socket.socketpair

    def guarded_connect(self: socket.socket, *args: object, **kwargs: object) -> None:
        raise RuntimeError(
            "Live network calls are forbidden in tests per docs/AGENTS.md and docs/TESTING.md."
        )

    def safe_socketpair(*args: object, **kwargs: object) -> tuple[socket.socket, socket.socket]:
        # Allow stdlib in-process socketpair (used by asyncio ProactorEventLoop on Windows)
        monkeypatch.setattr(socket.socket, "connect", orig_connect)
        try:
            return orig_socketpair(*args, **kwargs)  # type: ignore[arg-type]
        finally:
            monkeypatch.setattr(socket.socket, "connect", guarded_connect)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "socketpair", safe_socketpair)
