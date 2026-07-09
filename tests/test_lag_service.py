"""Tests for the set_aggregation use-case."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from unifictl.application.lag_service import set_aggregation

AGGREGATED = {
    "_id": "dev1",
    "port_overrides": [{"port_idx": 11, "op_mode": "aggregate", "aggregate_num_ports": 2}],
}
SWITCHED = [{"port_idx": 11, "op_mode": "switch"}]


class FakeClient:
    """Stand-in for UnifiClient recording put calls; the network boundary."""

    def __init__(self, device: dict[str, Any]) -> None:
        self._device = device
        self.put_calls: list[tuple[str, list[dict[str, Any]]]] = []

    def get_device(self, mac: str) -> dict[str, Any]:
        return self._device

    def put_port_overrides(self, device_id: str, port_overrides: list[dict[str, Any]]) -> None:
        self.put_calls.append((device_id, port_overrides))


def test_dry_run_computes_without_writing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    client = FakeClient({"_id": "dev1", "port_overrides": AGGREGATED["port_overrides"]})
    result = set_aggregation(client, "70:aa", [11], 2, enable=False, dry_run=True)
    assert result.applied is False
    assert result.backup_path is None
    assert result.after == SWITCHED
    assert client.put_calls == []
    assert list((tmp_path / "unifictl" / "backups").glob("*.json")) == []


def test_apply_backs_up_before_array_and_puts_after(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    before = [{"port_idx": 11, "op_mode": "aggregate", "aggregate_num_ports": 2}]
    client = FakeClient({"_id": "dev1", "port_overrides": before})
    result = set_aggregation(client, "70:aa", [11], 2, enable=False, dry_run=False)
    assert result.applied is True
    assert result.backup_path is not None
    assert json.loads(Path(result.backup_path).read_text(encoding="utf-8")) == before
    assert client.put_calls == [("dev1", SWITCHED)]


def test_backup_is_written_before_the_put(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    events: list[str] = []

    def fake_snapshot(mac: str, overrides: list[dict[str, Any]]) -> Path:
        events.append("backup")
        return tmp_path / "snap.json"

    monkeypatch.setattr("unifictl.application.lag_service.write_snapshot", fake_snapshot)

    class OrderingClient(FakeClient):
        def put_port_overrides(self, device_id: str, port_overrides: list[dict[str, Any]]) -> None:
            events.append("put")
            super().put_port_overrides(device_id, port_overrides)

    client = OrderingClient({"_id": "dev1", "port_overrides": AGGREGATED["port_overrides"]})
    set_aggregation(client, "70:aa", [11], 2, enable=True, dry_run=False)
    assert events == ["backup", "put"]
