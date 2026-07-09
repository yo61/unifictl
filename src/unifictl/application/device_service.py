"""Read use-cases: list devices, describe a switch port."""

from __future__ import annotations

from unifictl.domain.devices import device_summary
from unifictl.domain.models import DeviceSummary, PortDescription
from unifictl.domain.ports import describe_port
from unifictl.infrastructure.client import UnifiClient


class PortNotFoundError(ValueError):
    """Raised when a port index does not exist on the target switch."""


def list_devices(client: UnifiClient) -> list[DeviceSummary]:
    """Return a lean summary of every adopted device."""
    return [device_summary(raw) for raw in client.get_devices()]


def describe_switch_port(client: UnifiClient, switch_mac: str, port_idx: int) -> PortDescription:
    """Return the aggregation role of ``port_idx`` on ``switch_mac``.

    Raises:
        PortNotFoundError: if the switch has a port table that does not list
            ``port_idx``.
    """
    device = client.get_device(switch_mac)
    port_indices = {p.get("port_idx") for p in device.get("port_table", [])}
    if port_indices and port_idx not in port_indices:
        raise PortNotFoundError(f"port {port_idx} not found on {switch_mac}")
    return describe_port(device["port_overrides"], port_idx)
