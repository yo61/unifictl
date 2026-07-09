"""HTTP client for the private UniFi controller API (API-key auth).

Confirmed on a live UDM Pro that ``X-API-KEY`` authenticates both the
``stat/device`` read and the ``rest/device`` write — no session/cookie/CSRF.
See ``decisions/2026-07-09-private-api-auth.md``.
"""

from __future__ import annotations

from typing import Any

import httpx

from unifictl.infrastructure.config import Settings


class UnifiClient:
    """Talks to the private controller API using ``X-API-KEY`` auth."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = _build_httpx_client(settings)

    @property
    def site(self) -> str:
        """The controller site these calls target."""
        return self._settings.site

    def get_device(self, mac: str) -> dict[str, Any]:
        """Return the raw device object, including ``_id`` and ``port_overrides``.

        Args:
            mac: MAC of the switch to read.

        Returns:
            The device object as returned by ``stat/device/<mac>``.
        """
        raise NotImplementedError("implement test-first — see SPEC.md §6")

    def put_port_overrides(self, device_id: str, port_overrides: list[dict[str, Any]]) -> None:
        """PUT the full ``port_overrides`` array back to the device.

        Args:
            device_id: The device ``_id`` from :meth:`get_device`.
            port_overrides: The complete, modified ``port_overrides`` array.
        """
        raise NotImplementedError("implement test-first — see SPEC.md §6")

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()


def _build_httpx_client(settings: Settings) -> httpx.Client:
    verify: bool | str = True
    if settings.insecure_tls:
        verify = False
    elif settings.ca_cert is not None:
        verify = str(settings.ca_cert)
    return httpx.Client(
        base_url=settings.base_url,
        headers={"X-API-KEY": settings.api_key, "Accept": "application/json"},
        verify=verify,
        timeout=settings.timeout_ms / 1000,
    )
