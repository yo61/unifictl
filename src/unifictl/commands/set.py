"""``unifictl set`` sub-app. Currently exposes ``set lag on|off``."""

from __future__ import annotations

from typing import Literal

from cyclopts import App

app = App(name="set", help="Set a property on a UniFi device.")


@app.command(name="lag")
def lag(
    state: Literal["on", "off"],
    /,
    *,
    switch: str | None = None,
    ports: list[int] | None = None,
    num_ports: int = 2,
    dry_run: bool = False,
    yes: bool = False,
) -> None:
    """Break or restore LACP link aggregation so cluster nodes can PXE boot.

    Args:
        state: ``off`` dissolves the LAGs (nodes PXE as plain access ports);
            ``on`` restores the LACP bonds.
        switch: MAC of the switch; falls back to config/env when omitted.
        ports: LAG leader port(s); falls back to config when omitted.
        num_ports: Ports per LAG (2-8).
        dry_run: Print the computed ``port_overrides`` change without applying.
        yes: Skip the confirmation prompt. A backup is still written.
    """
    raise NotImplementedError("implement test-first — see SPEC.md §2 and §6")
