"""End-to-end tests: the whole stack from the CLI down to mocked HTTP."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from unifictl.cli import app

STAT_URL = "https://gw/proxy/network/api/s/default/stat/device/70:aa"
REST_URL = "https://gw/proxy/network/api/s/default/rest/device/dev1"
DEVICE = {
    "meta": {"rc": "ok"},
    "data": [
        {
            "_id": "dev1",
            "port_overrides": [
                {"port_idx": 11, "op_mode": "aggregate", "aggregate_members": [11, 12]}
            ],
        }
    ],
}


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("UNIFI_BASE_URL", "https://gw")
    monkeypatch.setenv("UNIFI_API_KEY", "secret")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))


def _run(*argv: str) -> None:
    # cyclopts raises SystemExit(0) on successful completion.
    with pytest.raises(SystemExit) as exc:
        app(list(argv))
    assert exc.value.code in (0, None)


def test_dry_run_reads_only(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="GET", url=STAT_URL, json=DEVICE)
    _run("set", "lag", "off", "--switch", "70:aa", "--leader", "11", "--dry-run")
    assert all(request.method == "GET" for request in httpx_mock.get_requests())


def test_apply_with_yes_writes_switched_array(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    httpx_mock.add_response(method="GET", url=STAT_URL, json=DEVICE, is_reusable=True)
    httpx_mock.add_response(method="PUT", url=REST_URL, json={"meta": {"rc": "ok"}, "data": []})
    _run("set", "lag", "off", "--switch", "70:aa", "--leader", "11", "--yes")
    puts = [request for request in httpx_mock.get_requests() if request.method == "PUT"]
    assert len(puts) == 1
    assert json.loads(puts[0].content) == {
        "port_overrides": [{"port_idx": 11, "op_mode": "switch", "aggregate_members": [11, 12]}]
    }
    assert list((tmp_path / "unifictl" / "backups").glob("*.json"))
