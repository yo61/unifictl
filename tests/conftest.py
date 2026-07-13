"""Shared pytest fixtures for the unifictl test suite."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest


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
