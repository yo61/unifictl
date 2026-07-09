"""Pure extraction of the lean summary fields from a raw device object."""

from __future__ import annotations

from typing import Any

from unifictl.domain.models import DeviceSummary


def device_summary(raw_device: dict[str, Any]) -> DeviceSummary:
    """Pull ``name``/``model``/``type``/``mac``/``ip`` from a raw device dict.

    Missing fields default to an empty string so the table always renders.
    """
    return DeviceSummary(
        name=str(raw_device.get("name", "")),
        model=str(raw_device.get("model", "")),
        type=str(raw_device.get("type", "")),
        mac=str(raw_device.get("mac", "")),
        ip=str(raw_device.get("ip", "")),
    )
