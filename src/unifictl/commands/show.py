"""``unifictl show`` sub-app. Currently exposes ``show port``."""

from __future__ import annotations

import json
from typing import Annotated

from cyclopts import App, Parameter
from rich.console import Console

from unifictl.application.device_service import describe_switch_port
from unifictl.domain.models import PortDescription, PortRole
from unifictl.infrastructure.client import UnifiClient
from unifictl.infrastructure.config import ConfigError, load_settings

app = App(name="show", help="Show UniFi resource configuration.")
_console = Console()


@app.command(name="port")
def port(
    port_idx: int,
    /,
    *,
    switch: str | None = None,
    as_json: Annotated[bool, Parameter(name=["--json"], negative=())] = False,
) -> None:
    """Show a port's configuration, and its LAG leader if it is aggregated.

    Args:
        port_idx: The port index to inspect.
        switch: MAC of the switch; falls back to config/env when omitted.
        as_json: Emit the description as JSON instead of formatted text.
    """
    settings = load_settings()
    switch_mac = switch or settings.switch
    if not switch_mac:
        raise ConfigError("no switch specified; pass --switch or set 'switch' in a profile")
    client = UnifiClient(settings)
    try:
        description = describe_switch_port(client, switch_mac, port_idx)
    finally:
        client.close()

    if as_json:
        print(json.dumps(_as_dict(description)))
        return
    _render(description)


def _as_dict(description: PortDescription) -> dict[str, object]:
    return {
        "port_idx": description.port_idx,
        "role": description.role.value,
        "leader_port": description.leader_port,
        "members": list(description.members),
        "override": description.override,
    }


def _render(description: PortDescription) -> None:
    members = list(description.members)
    if description.role is PortRole.LEADER:
        headline = f"port {description.port_idx}: LAG leader — members {members}"
    elif description.role is PortRole.MEMBER:
        headline = (
            f"port {description.port_idx}: member of LAG — "
            f"leader {description.leader_port}, members {members}"
        )
    else:
        headline = f"port {description.port_idx}: not aggregated"
    _console.print(headline)

    if description.override:
        fields = ", ".join(
            f"{key}={value!r}" for key, value in description.override.items() if key != "port_idx"
        )
        _console.print(f"  overrides: {fields}")
    else:
        _console.print("  overrides: (none; controller defaults)")
