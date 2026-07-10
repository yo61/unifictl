"""Value types for UniFi devices and their port overrides."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

PortOverride = dict[str, Any]
"""A single entry in a device's ``port_overrides`` array, keyed by ``port_idx``."""


class PortRole(StrEnum):
    """Whether a port leads a LAG, is a member of one, or is standalone."""

    LEADER = "leader"
    MEMBER = "member"
    STANDALONE = "standalone"


@dataclass(frozen=True)
class PortDescription:
    """A port's aggregation role plus its own override (if any)."""

    port_idx: int
    role: PortRole
    leader_port: int | None
    members: tuple[int, ...]
    override: PortOverride | None


@dataclass(frozen=True)
class DeviceSummary:
    """The lean device fields shown by ``list devices``."""

    name: str
    model: str
    type: str
    mac: str
    ip: str
