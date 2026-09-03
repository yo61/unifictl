"""Pure extraction of the lean summary fields from a raw device object."""

from __future__ import annotations

from typing import Any

from unifictl.domain.models import DeviceSummary


def device_summary(raw_device: dict[str, Any]) -> DeviceSummary:
    """Pull ``name``/``model``/``type``/``mac``/``ip`` from a raw device dict.

    ``ip`` resolves to the device's LAN address. Switches and APs report that
    directly in ``ip``; gateways put their WAN address there and their LAN
    address in ``lan_ip``, which is absent on every non-gateway, so preferring
    it needs no device-type check.

    ``wan_ip`` is the gateway's public address, empty for every device behind
    it. Absence is reported as an empty string; rendering a placeholder for it
    is the table's job, not this function's.

    Missing fields default to an empty string so the table always renders.
    """
    return DeviceSummary(
        name=str(raw_device.get("name", "")),
        model=str(raw_device.get("model", "")),
        type=str(raw_device.get("type", "")),
        mac=str(raw_device.get("mac", "")),
        ip=str(raw_device.get("lan_ip") or raw_device.get("ip", "")),
        wan_ip=str(raw_device.get("last_wan_ip", "")),
    )
