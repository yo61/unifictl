"""The ``set_aggregation`` use-case: fetch -> transform -> snapshot -> apply."""

from __future__ import annotations

from dataclasses import dataclass

from unifictl.domain.aggregation import apply_aggregation
from unifictl.domain.models import PortOverride
from unifictl.infrastructure.backup import write_snapshot
from unifictl.infrastructure.client import UnifiClient


@dataclass(frozen=True)
class AggregationResult:
    """Outcome of :func:`set_aggregation`, for the command layer to render."""

    switch_mac: str
    before: list[PortOverride]
    after: list[PortOverride]
    applied: bool
    backup_path: str | None


def set_aggregation(
    client: UnifiClient,
    switch_mac: str,
    leader_ports: list[int],
    num_ports: int,
    *,
    enable: bool,
    dry_run: bool,
) -> AggregationResult:
    """Read the switch, compute the new overrides, snapshot, and apply.

    Args:
        client: The private-API client.
        switch_mac: MAC of the switch to modify.
        leader_ports: LAG leader port indices.
        num_ports: Ports per LAG.
        enable: ``True`` to form LAGs, ``False`` to dissolve them.
        dry_run: When ``True``, compute and return the change but write nothing.

    Returns:
        The before/after arrays, whether it was applied, and the backup path.
    """
    device = client.get_device(switch_mac)
    before: list[PortOverride] = device["port_overrides"]
    after = apply_aggregation(before, leader_ports, num_ports, enable=enable)
    if dry_run:
        return AggregationResult(switch_mac, before, after, applied=False, backup_path=None)
    backup_path = write_snapshot(switch_mac, before)
    client.put_port_overrides(device["_id"], after)
    return AggregationResult(switch_mac, before, after, applied=True, backup_path=str(backup_path))
