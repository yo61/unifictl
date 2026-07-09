"""Tests for the private-API HTTP client (mocked with pytest-httpx)."""

from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock

from unifictl.infrastructure.client import UnifiClient, UnifiClientError
from unifictl.infrastructure.config import Settings

MAC = "70:a7:41:90:82:dd"


def _settings() -> Settings:
    return Settings(base_url="https://gw", api_key="secret", site="default")


def test_get_device_returns_device_and_sends_api_key(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=f"https://gw/proxy/network/api/s/default/stat/device/{MAC}",
        json={"meta": {"rc": "ok"}, "data": [{"_id": "dev1", "port_overrides": [{"port_idx": 1}]}]},
    )
    client = UnifiClient(_settings())
    device = client.get_device(MAC)
    assert device["_id"] == "dev1"
    assert device["port_overrides"] == [{"port_idx": 1}]
    assert httpx_mock.get_requests()[0].headers["X-API-KEY"] == "secret"


def test_put_port_overrides_sends_full_array(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="PUT",
        url="https://gw/proxy/network/api/s/default/rest/device/dev1",
        json={"meta": {"rc": "ok"}, "data": []},
    )
    overrides = [{"port_idx": 11, "op_mode": "switch"}]
    client = UnifiClient(_settings())
    client.put_port_overrides("dev1", overrides)
    request = httpx_mock.get_requests()[0]
    assert request.method == "PUT"
    assert json.loads(request.content) == {"port_overrides": overrides}
    assert request.headers["X-API-KEY"] == "secret"


def test_get_device_not_found_raises(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=f"https://gw/proxy/network/api/s/default/stat/device/{MAC}",
        json={"meta": {"rc": "ok"}, "data": []},
    )
    client = UnifiClient(_settings())
    with pytest.raises(UnifiClientError, match="mac"):
        client.get_device(MAC)


def test_http_error_is_wrapped_as_client_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=f"https://gw/proxy/network/api/s/default/stat/device/{MAC}",
        status_code=500,
        json={"meta": {"rc": "error"}},
    )
    client = UnifiClient(_settings())
    with pytest.raises(UnifiClientError):
        client.get_device(MAC)
