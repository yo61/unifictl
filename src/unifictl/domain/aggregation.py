"""Pure LAG aggregation rule over a device's ``port_overrides`` array.

See ``SPEC.md`` §4 "LAG domain rule". Implemented test-first in the build phase.
"""

from __future__ import annotations

from unifictl.domain.models import PortOverride

MIN_LAG_PORTS = 2
MAX_LAG_PORTS = 8


def apply_aggregation(
    port_overrides: list[PortOverride],
    leader_ports: list[int],
    num_ports: int,
    *,
    enable: bool,
) -> list[PortOverride]:
    """Return a new ``port_overrides`` array with LAG aggregation applied.

    Enabling sets each leader port's ``op_mode`` to ``"aggregate"`` with
    ``aggregate_num_ports = num_ports``; disabling sets ``op_mode`` to
    ``"switch"``. Every override that is not a leader port is preserved
    unchanged, and the input array is not mutated.

    Args:
        port_overrides: The device's current full ``port_overrides`` array.
        leader_ports: LAG leader port indices to modify.
        num_ports: Ports per LAG; must be between ``MIN_LAG_PORTS`` and
            ``MAX_LAG_PORTS`` inclusive.
        enable: ``True`` to form LAGs, ``False`` to dissolve them.

    Returns:
        A new ``port_overrides`` array.

    Raises:
        ValueError: if ``num_ports`` is outside the valid range.
    """
    if not MIN_LAG_PORTS <= num_ports <= MAX_LAG_PORTS:
        raise ValueError(
            f"num_ports must be between {MIN_LAG_PORTS} and {MAX_LAG_PORTS}, got {num_ports}"
        )
    result: list[PortOverride] = [dict(override) for override in port_overrides]
    by_idx = {override.get("port_idx"): override for override in result}
    for leader in leader_ports:
        override = by_idx.get(leader)
        if enable:
            if override is None:
                override = _new_override(leader)
                result.append(override)
                by_idx[leader] = override
            override["op_mode"] = "aggregate"
            override["aggregate_num_ports"] = num_ports
        elif override is not None:
            override["op_mode"] = "switch"
            override.pop("aggregate_num_ports", None)
    return result


def _new_override(port_idx: int) -> PortOverride:
    return {"port_idx": port_idx}
