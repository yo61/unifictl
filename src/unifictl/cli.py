"""The ``unifictl`` CLI entry point. Commands are registered explicitly below."""

from __future__ import annotations

import sys

from cyclopts import App

from unifictl import __version__
from unifictl.commands.list_ import app as list_app
from unifictl.commands.set import app as set_app
from unifictl.commands.show import app as show_app

app = App(
    name="unifictl",
    help="Imperative UniFi homelab actions.",
    version=__version__,
)
app.command(set_app)
app.command(list_app)
app.command(show_app)


def main() -> None:
    """Entry point: dispatch to cyclopts, mapping known errors to clean exits.

    Cyclopts raises ``SystemExit`` for ``--help``/``--version`` and usage
    errors. Configuration problems (:class:`ConfigError`) and private-API
    failures (:class:`UnifiClientError`) are converted to a single stderr line
    rather than a traceback.
    """
    from unifictl.application.device_service import PortNotFoundError
    from unifictl.infrastructure.client import UnifiClientError
    from unifictl.infrastructure.config import ConfigError

    try:
        app()
    except (ConfigError, UnifiClientError, PortNotFoundError) as exc:
        print(f"unifictl: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
