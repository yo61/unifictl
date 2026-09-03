"""``unifictl list`` sub-app. Currently exposes ``list devices``."""

from __future__ import annotations

import json
from typing import Annotated

from cyclopts import App, Parameter
from rich.console import Console
from rich.table import Table

from unifictl.application.device_service import list_devices
from unifictl.domain.models import DeviceSummary
from unifictl.infrastructure.client import UnifiClient
from unifictl.infrastructure.config import load_settings

app = App(name="list", help="List UniFi resources.")
_console = Console()
_NO_WAN_ADDRESS = "-"


@app.command(name="devices")
def devices(
    *,
    as_json: Annotated[bool, Parameter(name=["--json"], negative=())] = False,
    wan: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """List all adopted devices with their MAC addresses.

    Args:
        as_json: Emit the raw device objects as JSON instead of a table.
        wan: Add a WAN column with each gateway's public address. Devices behind
            the gateway have none and show ``-``.
    """
    settings = load_settings()
    client = UnifiClient(settings)
    try:
        if as_json:
            print(json.dumps(client.get_devices()))
            return
        _render_devices(list_devices(client), wan=wan)
    finally:
        client.close()


def _render_devices(summaries: list[DeviceSummary], *, wan: bool) -> None:
    table = Table(box=None, pad_edge=False)
    for column in ("NAME", "MODEL", "TYPE", "MAC", "IP"):
        table.add_column(column)
    if wan:
        table.add_column("WAN")
    for summary in summaries:
        row = [summary.name, summary.model, summary.type, summary.mac, summary.ip]
        if wan:
            row.append(summary.wan_ip or _NO_WAN_ADDRESS)
        table.add_row(*row)
    _console.print(table)
