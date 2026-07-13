"""``unifictl set`` sub-app. Currently exposes ``set lag on|off``."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any, Literal

import questionary
from cyclopts import App, Parameter
from rich.console import Console

from unifictl.application.lag_service import AggregationResult, set_aggregation
from unifictl.infrastructure.client import UnifiClient
from unifictl.infrastructure.config import ConfigError, load_settings

app = App(name="set", help="Set a property on a UniFi device.")
_console = Console()


def _split_leaders(type_: Any, tokens: Sequence[Any]) -> list[int]:
    """Parse leader ports from comma-separated and/or repeated ``--leader`` tokens."""
    ports: list[int] = []
    for token in tokens:
        ports.extend(int(part) for part in token.value.split(",") if part.strip())
    return ports


@app.command(name="lag")
def lag(
    state: Literal["on", "off"],
    /,
    *,
    switch: str | None = None,
    leader: Annotated[list[int], Parameter(converter=_split_leaders)] | None = None,
    dry_run: bool = False,
    yes: bool = False,
) -> None:
    """Break or restore LACP link aggregation on a switch's leader ports.

    Args:
        state: ``off`` dissolves the LAGs; ``on`` restores the LACP bonds.
        switch: MAC of the switch; falls back to config/env when omitted.
        leader: LAG leader port(s), e.g. ``--leader 17,19,21`` or repeated
            ``--leader`` flags; falls back to config when omitted.
        dry_run: Print the computed ``port_overrides`` change without applying.
        yes: Skip the confirmation prompt. A backup is still written.
    """
    enable = state == "on"
    settings = load_settings()
    switch_mac = switch or settings.switch
    if not switch_mac:
        raise ConfigError(
            "no switch specified; pass --switch or set 'switch' in the active profile"
        )
    leader_ports = list(leader) if leader else list(settings.leaders)
    if not leader_ports:
        raise ConfigError("no LAG leader ports; pass --leader or set 'leaders' in config")

    client = UnifiClient(settings)
    try:
        preview = set_aggregation(client, switch_mac, leader_ports, enable=enable, dry_run=True)
        _show_diff(preview, enable=enable)
        if dry_run:
            _console.print("[dim]dry-run: nothing applied[/dim]")
            return
        if not yes and not _confirm():
            _console.print("aborted; nothing applied")
            return
        result = set_aggregation(client, switch_mac, leader_ports, enable=enable, dry_run=False)
        _console.print(f"applied; backup written to {result.backup_path}")
    finally:
        client.close()


def _confirm() -> bool:
    return bool(questionary.confirm("Apply this change to the switch?", default=False).ask())


def _show_diff(result: AggregationResult, *, enable: bool) -> None:
    action = "form LAG(s)" if enable else "dissolve LAG(s)"
    _console.print(f"[bold]{result.switch_mac}[/bold]: {action}")
    before = {override.get("port_idx"): override for override in result.before}
    for override in result.after:
        idx = override.get("port_idx")
        if idx not in before or before[idx] != override:
            _console.print(f"  port {idx}: {before.get(idx)} -> {override}")
