"""Tests for the port_overrides snapshot writer."""

from __future__ import annotations

import json

import pytest

from unifictl.infrastructure.backup import write_snapshot


def test_write_snapshot_roundtrips(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    overrides = [{"port_idx": 11, "op_mode": "aggregate", "aggregate_num_ports": 2}]
    path = write_snapshot("70:a7:41:90:82:dd", overrides)
    assert path.exists()
    assert path.parent == tmp_path / "unifictl" / "backups"
    assert json.loads(path.read_text(encoding="utf-8")) == overrides


def test_write_snapshot_names_include_mac(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    path = write_snapshot("aa:bb:cc:dd:ee:ff", [])
    assert "aa:bb:cc:dd:ee:ff" in path.name
    assert path.name.endswith(".json")
