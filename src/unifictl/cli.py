"""The ``unifictl`` CLI entry point. Commands are registered lazily below."""

from __future__ import annotations

import os
import sys
from typing import Annotated, Any

from cyclopts import App, Parameter

from unifictl import __version__


def _apply_profile(profile: str | None) -> None:
    """Set ``UNIFI_PROFILE`` from the ``--profile`` flag (flag beats env)."""
    if profile is not None:
        os.environ["UNIFI_PROFILE"] = profile


def get_app() -> App:
    """Build the top-level cyclopts App, importing command modules lazily.

    The command modules pull in heavy dependencies (``questionary``,
    ``rich``); importing them here rather than at module scope keeps
    ``import unifictl.cli`` cheap, so the ``__complete`` fast-path in
    :func:`main` stays fast.
    """
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

    @app.meta.default
    def _launcher(
        *tokens: Annotated[str, Parameter(show=False, allow_leading_hyphen=True)],
        profile: Annotated[
            str | None, Parameter(help="Configuration profile to use (sets UNIFI_PROFILE).")
        ] = None,
    ) -> None:
        _apply_profile(profile)
        app(tokens)

    return app


def app(*args: Any, **kwargs: Any) -> Any:
    """Invoke the CLI through the meta launcher so ``--profile`` is global.

    Exposed as a function (not the ``App`` instance) so the lazy build stays
    transparent to callers such as ``app(["--help"])`` in tests.
    """
    return get_app().meta(*args, **kwargs)


def main() -> None:
    """Entry point: dispatch to cyclopts, mapping known errors to clean exits.

    Fast-path: ``unifictl __complete …`` dispatches straight to the completion
    handler, skipping the App build and its command-module imports
    (``questionary``/``rich``), so tab completion stays fast.

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
