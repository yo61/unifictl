"""The ``unifictl`` CLI entry point. Commands are registered explicitly below."""

from __future__ import annotations

import sys

from cyclopts import App

from unifictl import __version__
from unifictl.commands.completion import app as completion_app
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
app.command(completion_app)


def main() -> None:
    """Entry point: dispatch to cyclopts, mapping known errors to clean exits.

    Fast-path: ``unifictl __complete …`` dispatches straight to the completion
    handler, skipping the full App build (and its ``questionary`` import).

    Cyclopts raises ``SystemExit`` for ``--help``/``--version`` and usage
    errors. Configuration problems (:class:`ConfigError`) and private-API
    failures (:class:`UnifiClientError`) are converted to a single stderr line
    rather than a traceback.
    """
    if len(sys.argv) >= 2 and sys.argv[1] == "__complete":
        from unifictl.commands._complete import run as complete_run

        complete_run(*sys.argv[2:])
        return

    from unifictl.commands import completion

    completion.maybe_refresh_installed_stubs()

    from unifictl.application.device_service import PortNotFoundError
    from unifictl.infrastructure.client import UnifiClientError
    from unifictl.infrastructure.config import ConfigError

    try:
        app()
    except (ConfigError, UnifiClientError, PortNotFoundError) as exc:
        print(f"unifictl: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
