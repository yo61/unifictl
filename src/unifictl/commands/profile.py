"""``unifictl profile`` sub-app: inspect and scaffold connection profiles."""

from __future__ import annotations

from cyclopts import App
from rich.console import Console

from unifictl.infrastructure.config import load_profiles, read_config

app = App(name="profile", help="Inspect and scaffold connection profiles.")
_console = Console()


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
