"""Shared pytest fixtures for the unifictl test suite."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import pytest


class WriteProfile(Protocol):
    """Callable that writes a profile TOML file under a test's XDG config home."""

    def __call__(self, name: str, body: str) -> None: ...


@pytest.fixture
def write_profile(tmp_path: Path) -> WriteProfile:
    """Return a helper that writes ``<XDG_CONFIG_HOME>/unifictl/profiles/<name>.toml``.

    Assumes the test has already set ``XDG_CONFIG_HOME`` to ``tmp_path`` via
    ``monkeypatch.setenv``.
    """

    def _write(name: str, body: str) -> None:
        d = tmp_path / "unifictl" / "profiles"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.toml").write_text(body, encoding="utf-8")

    return _write


@pytest.fixture(autouse=True)
def _isolate_unifi_profile() -> Iterator[None]:
    """Snapshot and restore ``UNIFI_PROFILE`` around each test.

    Some CLI tests set ``UNIFI_PROFILE`` by mutating ``os.environ`` directly
    (the ``--profile`` launcher does this), which pytest's ``monkeypatch``
    cannot undo when the variable started absent. Restoring it here keeps a
    set or leaked value from bleeding into a later test.
    """
    saved = os.environ.get("UNIFI_PROFILE")
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop("UNIFI_PROFILE", None)
        else:
            os.environ["UNIFI_PROFILE"] = saved
