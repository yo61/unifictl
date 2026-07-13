"""``unifictl credential`` sub-app: manage API keys in credentials.toml."""

from __future__ import annotations

import sys

import questionary
from cyclopts import App
from rich.console import Console

from unifictl.commands._prompt import prompt_api_key
from unifictl.infrastructure import credential_store
from unifictl.infrastructure.config import ConfigError

app = App(name="credential", help="Manage API keys (credentials.toml, 0600).")
_console = Console()


@app.command(name="set")
def set_(name: str = "default", /, *, stdin: bool = False) -> None:
    """Set or rotate a credential's API key (written 0600).

    Args:
        name: Credential section name. Defaults to ``default``.
        stdin: Read the key from stdin instead of a hidden prompt.
    """
    key = sys.stdin.readline().strip() if stdin else prompt_api_key()
    if not key:
        raise ConfigError("no API key provided")
    credential_store.set_credential(name, key)
    _console.print(f"credential {name!r} set", markup=False)


@app.command(name="list")
def list_() -> None:
    """List credential names (never prints keys)."""
    names = credential_store.list_credential_names()
    if not names:
        _console.print("no credentials defined")
        return
    for name in names:
        _console.print(name, markup=False)


@app.command(name="delete")
def delete(name: str, /, *, yes: bool = False) -> None:
    """Delete a credential section.

    Args:
        name: The credential to remove.
        yes: Skip the confirmation prompt.
    """
    if not yes and not questionary.confirm(f"Delete credential {name!r}?", default=False).ask():
        _console.print("aborted")
        return
    if credential_store.delete_credential(name):
        _console.print(f"credential {name!r} deleted", markup=False)
    else:
        _console.print(f"no such credential {name!r}", markup=False)
