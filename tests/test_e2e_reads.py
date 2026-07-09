"""End-to-end read tests: CLI down to mocked HTTP."""

from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock

from unifictl.cli import app

DEVICES_URL = "https://gw/proxy/network/api/s/default/stat/device"
DEVICE_URL = "https://gw/proxy/network/api/s/default/stat/device/70:aa"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNIFI_BASE_URL", "https://gw")
    monkeypatch.setenv("UNIFI_API_KEY", "secret")


def _run(*argv: str) -> None:
    with pytest.raises(SystemExit) as exc:
        app(list(argv))
    assert exc.value.code in (0, None)


def test_list_devices_json(httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]) -> None:
    httpx_mock.add_response(
        method="GET",
        url=DEVICES_URL,
        json={
            "meta": {"rc": "ok"},
            "data": [{"name": "SW", "mac": "aa", "model": "M", "type": "usw", "ip": "1.2.3.4"}],
        },
    )
    _run("list", "devices", "--json")
    assert json.loads(capsys.readouterr().out)[0]["mac"] == "aa"


def test_show_port_member(httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]) -> None:
    httpx_mock.add_response(
        method="GET",
        url=DEVICE_URL,
        json={
            "meta": {"rc": "ok"},
            "data": [
                {
                    "_id": "dev1",
                    "port_table": [{"port_idx": 17}, {"port_idx": 18}],
                    "port_overrides": [
                        {"port_idx": 17, "op_mode": "aggregate", "aggregate_members": [17, 18]}
                    ],
                }
            ],
        },
    )
    _run("show", "port", "18", "--switch", "70:aa")
    out = capsys.readouterr().out.lower()
    assert "member" in out
    assert "17" in out
