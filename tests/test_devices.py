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


def test_gateway_lan_ip_wins_over_the_wan_address_in_ip() -> None:
    """A gateway reports its WAN address in ``ip`` and its LAN address in ``lan_ip``."""
    raw = {
        "name": "gw",
        "model": "UDMPRO",
        "type": "udm",
        "mac": "d0:21:f9:d0:24:59",
        "ip": "203.0.113.7",
        "lan_ip": "192.168.1.1",
    }
    assert device_summary(raw).ip == "192.168.1.1"


def test_ip_is_used_when_no_lan_ip_is_reported() -> None:
    """Switches and APs report only ``ip``, which is already the LAN address."""
    raw = {"name": "SW", "model": "USL24P", "type": "usw", "mac": "aa", "ip": "192.168.1.170"}
    assert device_summary(raw).ip == "192.168.1.170"


def test_gateway_wan_address_is_kept_as_wan_ip() -> None:
    """The gateway's public address stays available alongside its LAN address."""
    raw = {
        "type": "udm",
        "ip": "203.0.113.7",
        "lan_ip": "192.168.1.1",
        "last_wan_ip": "203.0.113.7",
    }
    summary = device_summary(raw)
    assert summary.ip == "192.168.1.1"
    assert summary.wan_ip == "203.0.113.7"


def test_devices_behind_the_gateway_have_no_wan_ip() -> None:
    """Switches and APs report no WAN address at all."""
    assert device_summary({"type": "usw", "ip": "192.168.1.170"}).wan_ip == ""
