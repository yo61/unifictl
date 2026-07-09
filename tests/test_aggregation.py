"""Tests for the pure LAG toggle transform.

The model is grounded in observed controller behaviour: a LAG lives on its
leader port's override, and toggling is purely an ``op_mode`` flip on the
leader — members persist and the controller manages ``lag_idx``.
"""

from __future__ import annotations

import copy

import pytest
from hypothesis import given
from hypothesis import strategies as st

from unifictl.domain.aggregation import UnknownLeaderError, apply_aggregation


def test_enable_sets_leader_to_aggregate() -> None:
    before = [{"port_idx": 17, "op_mode": "switch", "aggregate_members": [17, 18]}]
    after = apply_aggregation(before, [17], enable=True)
    assert after[0]["op_mode"] == "aggregate"


def test_disable_sets_leader_to_switch() -> None:
    before = [{"port_idx": 17, "op_mode": "aggregate", "aggregate_members": [17, 18], "lag_idx": 1}]
    after = apply_aggregation(before, [17], enable=False)
    assert after[0]["op_mode"] == "switch"


def test_only_op_mode_changes_all_else_preserved() -> None:
    before = [
        {
            "port_idx": 17,
            "op_mode": "aggregate",
            "aggregate_members": [17, 18],
            "lag_idx": 1,
            "name": "Port 17",
            "poe_mode": "auto",
        }
    ]
    after = apply_aggregation(before, [17], enable=False)
    assert after[0] == {**before[0], "op_mode": "switch"}


def test_non_leader_overrides_untouched() -> None:
    before = [
        {"port_idx": 1, "poe_mode": "off"},
        {"port_idx": 17, "op_mode": "aggregate", "aggregate_members": [17, 18]},
    ]
    after = apply_aggregation(before, [17], enable=False)
    assert after[0] == {"port_idx": 1, "poe_mode": "off"}


def test_unknown_leader_raises() -> None:
    before = [{"port_idx": 17, "op_mode": "aggregate", "aggregate_members": [17, 18]}]
    with pytest.raises(UnknownLeaderError, match="99"):
        apply_aggregation(before, [99], enable=True)


def test_multiple_leaders_all_toggled() -> None:
    before = [
        {"port_idx": p, "op_mode": "aggregate", "aggregate_members": [p, p + 1]}
        for p in (17, 19, 21)
    ]
    after = apply_aggregation(before, [17, 19, 21], enable=False)
    assert [o["op_mode"] for o in after] == ["switch", "switch", "switch"]


@st.composite
def _overrides_and_leaders(draw: st.DrawFn) -> tuple[list[dict[str, object]], list[int]]:
    indices = draw(st.lists(st.integers(min_value=1, max_value=52), unique=True, min_size=1))
    overrides: list[dict[str, object]] = []
    for idx in indices:
        override: dict[str, object] = {
            "port_idx": idx,
            "op_mode": draw(st.sampled_from(["switch", "aggregate"])),
        }
        if draw(st.booleans()):
            override["aggregate_members"] = [idx, idx + 1]
        if draw(st.booleans()):
            override["name"] = f"Port {idx}"
        overrides.append(override)
    leaders = draw(st.lists(st.sampled_from(indices), unique=True, min_size=1))
    return overrides, leaders


@given(_overrides_and_leaders(), st.booleans())
def test_input_is_never_mutated(
    data: tuple[list[dict[str, object]], list[int]], enable: bool
) -> None:
    overrides, leaders = data
    snapshot = copy.deepcopy(overrides)
    apply_aggregation(overrides, leaders, enable=enable)
    assert overrides == snapshot


@given(_overrides_and_leaders(), st.booleans())
def test_only_leader_op_mode_differs(
    data: tuple[list[dict[str, object]], list[int]], enable: bool
) -> None:
    overrides, leaders = data
    leader_set = set(leaders)
    original = {o["port_idx"]: o for o in overrides}
    result = apply_aggregation(overrides, leaders, enable=enable)
    expected_op_mode = "aggregate" if enable else "switch"
    for override in result:
        idx = override["port_idx"]
        if idx in leader_set:
            assert override == {**original[idx], "op_mode": expected_op_mode}
        else:
            assert override == original[idx]


@given(_overrides_and_leaders(), st.booleans())
def test_applying_twice_equals_once(
    data: tuple[list[dict[str, object]], list[int]], enable: bool
) -> None:
    overrides, leaders = data
    once = apply_aggregation(overrides, leaders, enable=enable)
    twice = apply_aggregation(once, leaders, enable=enable)
    assert once == twice
