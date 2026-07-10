"""Tests for the pure port-description function."""

from __future__ import annotations

import copy

from hypothesis import given
from hypothesis import strategies as st

from unifictl.domain.models import PortRole
from unifictl.domain.ports import describe_port

LEADER_17 = {
    "port_idx": 17,
    "op_mode": "aggregate",
    "aggregate_members": [17, 18],
    "name": "Port 17",
}


def test_leader_is_reported_as_leader() -> None:
    result = describe_port([LEADER_17], 17)
    assert result.role is PortRole.LEADER
    assert result.leader_port == 17
    assert result.members == (17, 18)
    assert result.override == LEADER_17


def test_member_reports_its_leader() -> None:
    result = describe_port([LEADER_17], 18)
    assert result.role is PortRole.MEMBER
    assert result.leader_port == 17
    assert result.members == (17, 18)
    assert result.override is None


def test_member_with_own_override_keeps_it() -> None:
    member = {"port_idx": 18, "poe_mode": "off"}
    result = describe_port([LEADER_17, member], 18)
    assert result.role is PortRole.MEMBER
    assert result.leader_port == 17
    assert result.override == member


def test_standalone_port_with_override() -> None:
    plain = {"port_idx": 3, "name": "Port 3"}
    result = describe_port([plain], 3)
    assert result.role is PortRole.STANDALONE
    assert result.leader_port is None
    assert result.members == ()
    assert result.override == plain


def test_standalone_port_without_override() -> None:
    result = describe_port([LEADER_17], 3)
    assert result.role is PortRole.STANDALONE
    assert result.override is None


@st.composite
def _overrides_and_target(draw: st.DrawFn) -> tuple[list[dict[str, object]], int]:
    indices = draw(st.lists(st.integers(min_value=1, max_value=52), unique=True, min_size=1))
    overrides: list[dict[str, object]] = []
    for idx in indices:
        override: dict[str, object] = {"port_idx": idx}
        if draw(st.booleans()):
            override["op_mode"] = "aggregate"
            override["aggregate_members"] = [idx, idx + 1]
        overrides.append(override)
    target = draw(st.sampled_from([*indices, max(indices) + 5]))
    return overrides, target


@given(_overrides_and_target())
def test_role_is_exactly_one_kind(data: tuple[list[dict[str, object]], int]) -> None:
    overrides, target = data
    result = describe_port(overrides, target)
    assert result.role in (PortRole.LEADER, PortRole.MEMBER, PortRole.STANDALONE)
    if result.role is PortRole.LEADER:
        assert result.leader_port == target
        assert target in result.members
    elif result.role is PortRole.MEMBER:
        assert result.leader_port != target
        assert target in result.members
    else:
        assert result.leader_port is None
        assert result.members == ()


@given(_overrides_and_target())
def test_input_never_mutated(data: tuple[list[dict[str, object]], int]) -> None:
    overrides, target = data
    snapshot = copy.deepcopy(overrides)
    describe_port(overrides, target)
    assert overrides == snapshot
