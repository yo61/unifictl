"""Write timestamped snapshots of a device's ``port_overrides`` before a write."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from xdg_base_dirs import xdg_data_home


def backup_dir() -> Path:
    """Return the directory where ``port_overrides`` snapshots are written."""
    return xdg_data_home() / "unifictl" / "backups"


def write_snapshot(switch_mac: str, port_overrides: list[dict[str, Any]]) -> Path:
    """Write ``port_overrides`` to a timestamped JSON file and return its path.

    Args:
        switch_mac: MAC of the switch, used in the filename.
        port_overrides: The full ``port_overrides`` array to snapshot.

    Returns:
        The path of the written snapshot file.
    """
    directory = backup_dir()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"port-overrides-{switch_mac}-{stamp}.json"
    path.write_text(json.dumps(port_overrides, indent=2), encoding="utf-8")
    return path
