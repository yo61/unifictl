"""``unifictl profile`` sub-app: inspect and scaffold connection profiles."""

from __future__ import annotations

from cyclopts import App
from rich.console import Console

from unifictl.infrastructure.config import (
    ConfigError,
    config_file_path,
    load_profiles,
    read_config,
)

app = App(name="profile", help="Inspect and scaffold connection profiles.")
_console = Console()

_SHOW_ORDER = ("base_url", "api_key", "site", "switch", "ca_cert", "insecure_tls", "timeout_ms")

_EXAMPLE = """\
# Append to {path}, then run: chmod 600 {path}
[profiles.{name}]
base_url = "https://192.168.1.1"   # controller URL
api_key  = "REPLACE_ME"            # Integration API key
site     = "default"               # controller site
switch   = "aa:bb:cc:dd:ee:ff"     # MAC of the switch to operate on
# ca_cert      = "/path/to/controller-ca.pem"
# insecure_tls = false
# timeout_ms   = 30000
"""


@app.command(name="list")
def list_() -> None:
    """List defined profiles, marking the default, with each ``base_url``."""
    data = read_config()
    profiles = load_profiles(data)
    if not profiles:
        _console.print("no profiles defined")
        return
    default = data.get("default_profile")
    for name in sorted(profiles):
        marker = " (default)" if name == default else ""
        base_url = profiles[name].get("base_url", "—")
        _console.print(f"{name}{marker}: {base_url}")


@app.command(name="show")
def show(name: str, /) -> None:
    """Show a profile's fields, redacting ``api_key``.

    Args:
        name: The profile to display.

    Raises:
        ConfigError: if ``name`` is not a defined profile.
    """
    data = read_config()
    profiles = load_profiles(data)
    if name not in profiles:
        available = ", ".join(sorted(profiles)) or "(none)"
        raise ConfigError(f"unknown profile {name!r}; available: {available}")
    table = profiles[name]
    for key in _SHOW_ORDER:
        if key not in table:
            continue
        value = table[key]
        if key == "api_key":
            value = _redact(str(value))
        _console.print(f"{key} = {value!r}")


@app.command(name="example")
def example(name: str = "example", /) -> None:
    """Print a commented profile block to stdout (does not write the file).

    Args:
        name: The profile name to scaffold. Defaults to ``example``.
    """
    print(_EXAMPLE.format(name=name, path=config_file_path()))


def _redact(value: str) -> str:
    """Redact a secret, keeping only the last four characters visible.

    Args:
        value: The secret to redact.

    Returns:
        ``…`` followed by the last four characters, or ``****`` if ``value``
        is four characters or shorter.
    """
    return f"…{value[-4:]}" if len(value) > 4 else "****"
