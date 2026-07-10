"""Tests for device-summary extraction."""

from __future__ import annotations

from unifictl.domain.devices import device_summary


def test_extracts_the_lean_fields() -> None:
    raw = {
        "name": "USW 24 PoE",
        "model": "USL24P",
        "type": "usw",
        "mac": "70:a7:41:90:82:dd",
        "ip": "192.168.1.10",
        "extra": "ignored",
    }
    summary = device_summary(raw)
    assert summary.name == "USW 24 PoE"
    assert summary.model == "USL24P"
    assert summary.type == "usw"
    assert summary.mac == "70:a7:41:90:82:dd"
    assert summary.ip == "192.168.1.10"


def test_missing_fields_become_empty_strings() -> None:
    summary = device_summary({"mac": "aa:bb"})
    assert summary.mac == "aa:bb"
    assert summary.name == ""
    assert summary.ip == ""
