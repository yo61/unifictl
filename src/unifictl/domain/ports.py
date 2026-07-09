"""Pure description of a port's LAG role over a device's port_overrides array."""

from __future__ import annotations

from unifictl.domain.models import PortDescription, PortOverride, PortRole


def describe_port(port_overrides: list[PortOverride], port_idx: int) -> PortDescription:
    """Return the aggregation role of ``port_idx`` and its own override.

    A port is a **leader** if its own override has ``op_mode == "aggregate"``; a
    **member** if it appears in some aggregate leader's ``aggregate_members``;
    otherwise **standalone**. The input array is not mutated.
    """
    own = next((o for o in port_overrides if o.get("port_idx") == port_idx), None)

    if own is not None and own.get("op_mode") == "aggregate":
        members = tuple(own.get("aggregate_members", []))
        return PortDescription(port_idx, PortRole.LEADER, port_idx, members, own)

    for override in port_overrides:
        if override.get("op_mode") == "aggregate" and port_idx in override.get(
            "aggregate_members", []
        ):
            leader = override.get("port_idx")
            members = tuple(override.get("aggregate_members", []))
            return PortDescription(port_idx, PortRole.MEMBER, leader, members, own)

    return PortDescription(port_idx, PortRole.STANDALONE, None, (), own)
