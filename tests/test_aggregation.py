"""Tests for the pure LAG aggregation transform."""

from __future__ import annotations

import copy

import pytest
from hypothesis import given
from hypothesis import strategies as st

from unifictl.domain.aggregation import apply_aggregation


@st.composite
def _overrides_and_leaders(draw: st.DrawFn) -> tuple[list[dict[str, object]], list[int], int]:
    indices = draw(st.lists(st.integers(min_value=1, max_value=52), unique=True, max_size=10))
    overrides: list[dict[str, object]] = []
    for idx in indices:
        override: dict[str, object] = {"port_idx": idx}
        if draw(st.booleans()):
            override["poe_mode"] = draw(st.sampled_from(["auto", "off"]))
        if draw(st.booleans()):
            override["op_mode"] = draw(st.sampled_from(["switch", "aggregate"]))
        overrides.append(override)
    leaders = draw(st.lists(st.integers(min_value=1, max_value=52), unique=True, max_size=4))
    num_ports = draw(st.integers(min_value=2, max_value=8))
    return overrides, leaders, num_ports


def test_enable_creates_aggregate_override_when_missing() -> None:
    result = apply_aggregation([], leader_ports=[11], num_ports=2, enable=True)
    assert result == [{"port_idx": 11, "op_mode": "aggregate", "aggregate_num_ports": 2}]


def test_disable_sets_switch_and_drops_num_ports() -> None:
    current = [{"port_idx": 11, "op_mode": "aggregate", "aggregate_num_ports": 2}]
    result = apply_aggregation(current, leader_ports=[11], num_ports=2, enable=False)
    assert result == [{"port_idx": 11, "op_mode": "switch"}]


@pytest.mark.parametrize("bad", [1, 0, -1, 9, 100])
def test_num_ports_out_of_range_raises(bad: int) -> None:
    with pytest.raises(ValueError, match="num_ports"):
        apply_aggregation([], leader_ports=[11], num_ports=bad, enable=True)


@given(_overrides_and_leaders(), st.booleans())
def test_input_is_never_mutated(
    data: tuple[list[dict[str, object]], list[int], int], enable: bool
) -> None:
    overrides, leaders, num_ports = data
    snapshot = copy.deepcopy(overrides)
    apply_aggregation(overrides, leaders, num_ports, enable=enable)
    assert overrides == snapshot


@given(_overrides_and_leaders(), st.booleans())
def test_non_leader_overrides_are_preserved(
    data: tuple[list[dict[str, object]], list[int], int], enable: bool
) -> None:
    overrides, leaders, num_ports = data
    original = {o["port_idx"]: o for o in overrides}
    leader_set = set(leaders)
    result = apply_aggregation(overrides, leaders, num_ports, enable=enable)
    for override in result:
        idx = override["port_idx"]
        if idx not in leader_set:
            assert override == original[idx]


@given(_overrides_and_leaders())
def test_enable_aggregates_every_leader(
    data: tuple[list[dict[str, object]], list[int], int],
) -> None:
    overrides, leaders, num_ports = data
    result = apply_aggregation(overrides, leaders, num_ports, enable=True)
    by_idx = {o["port_idx"]: o for o in result}
    for leader in leaders:
        assert by_idx[leader]["op_mode"] == "aggregate"
        assert by_idx[leader]["aggregate_num_ports"] == num_ports


@given(_overrides_and_leaders(), st.booleans())
def test_applying_twice_equals_once(
    data: tuple[list[dict[str, object]], list[int], int], enable: bool
) -> None:
    overrides, leaders, num_ports = data
    once = apply_aggregation(overrides, leaders, num_ports, enable=enable)
    twice = apply_aggregation(once, leaders, num_ports, enable=enable)
    assert once == twice


@given(_overrides_and_leaders())
def test_disable_then_enable_restores_aggregation(
    data: tuple[list[dict[str, object]], list[int], int],
) -> None:
    overrides, leaders, num_ports = data
    aggregated = apply_aggregation(overrides, leaders, num_ports, enable=True)
    dissolved = apply_aggregation(aggregated, leaders, num_ports, enable=False)
    restored = apply_aggregation(dissolved, leaders, num_ports, enable=True)
    assert restored == aggregated
