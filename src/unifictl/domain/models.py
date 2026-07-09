"""Value types for UniFi devices and their port overrides."""

from __future__ import annotations

from typing import Any

PortOverride = dict[str, Any]
"""A single entry in a device's ``port_overrides`` array, keyed by ``port_idx``."""
