"""The ``set_aggregation`` use-case: fetch -> transform -> snapshot -> apply."""

from __future__ import annotations

from dataclasses import dataclass

from unifictl.domain.models import PortOverride
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
    raise NotImplementedError("implement test-first — see SPEC.md §3 and §6")
