"""Pure LAG toggle over a device's ``port_overrides`` array.

Grounded in observed controller behaviour (see
``decisions/2026-07-09-lag-toggle-model.md``): a LAG lives entirely on its
**leader** port's override as ``op_mode: aggregate`` + ``aggregate_members``
(+ a controller-managed ``lag_idx``). Toggling a LAG is purely an ``op_mode``
flip on the leader — the member list persists dormant when the leader is
``switch``, and the controller re-assigns ``lag_idx`` when it becomes
``aggregate`` again. The tool therefore changes nothing but ``op_mode``.
"""

from __future__ import annotations

from unifictl.domain.models import PortOverride


class UnknownLeaderError(ValueError):
    """Raised when a named leader port has no override (not a configured LAG)."""


def apply_aggregation(
    port_overrides: list[PortOverride],
    leader_ports: list[int],
    *,
    enable: bool,
) -> list[PortOverride]:
    """Return a new ``port_overrides`` array toggling the named LAG leaders.

    Sets each leader's ``op_mode`` to ``"aggregate"`` (enable) or ``"switch"``
    (disable), preserving every other field and every other override. The input
    array is not mutated.

    Args:
        port_overrides: The device's current full ``port_overrides`` array.
        leader_ports: LAG leader port indices to toggle.
        enable: ``True`` to form the LAGs, ``False`` to dissolve them.

    Returns:
        A new ``port_overrides`` array.

    Raises:
        UnknownLeaderError: if a named leader port has no override, i.e. it is
            not a configured LAG leader.
    """
    result = [dict(override) for override in port_overrides]
    by_idx = {override.get("port_idx"): override for override in result}
    op_mode = "aggregate" if enable else "switch"
    for leader in leader_ports:
        override = by_idx.get(leader)
        if override is None:
            raise UnknownLeaderError(f"port {leader} is not a configured LAG leader")
        override["op_mode"] = op_mode
    return result
