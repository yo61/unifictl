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


@app.command(name="devices")
def devices(*, as_json: Annotated[bool, Parameter(name=["--json"], negative=())] = False) -> None:
    """List all adopted devices with their MAC addresses.

    Args:
        as_json: Emit the raw device objects as JSON instead of a table.
    """
    settings = load_settings()
    client = UnifiClient(settings)
    try:
        if as_json:
            print(json.dumps(client.get_devices()))
            return
        _render_devices(list_devices(client))
    finally:
        client.close()


def _render_devices(summaries: list[DeviceSummary]) -> None:
    table = Table(box=None, pad_edge=False)
    for column in ("NAME", "MODEL", "TYPE", "MAC", "IP"):
        table.add_column(column)
    for summary in summaries:
        table.add_row(summary.name, summary.model, summary.type, summary.mac, summary.ip)
    _console.print(table)
