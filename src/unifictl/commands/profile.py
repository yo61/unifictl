"""``unifictl profile`` sub-app: manage connection profiles."""

from __future__ import annotations

from cyclopts import App
from rich.console import Console

from unifictl.infrastructure import credential_store, profile_store
from unifictl.infrastructure.config import ConfigError

app = App(name="profile", help="Manage connection profiles.")
_console = Console()

_DESCRIBE_ORDER = (
    "base_url",
    "site",
    "switch",
    "credential",
    "ca_cert",
    "insecure_tls",
    "timeout_ms",
)


@app.command(name="list")
def list_() -> None:
    """List profiles, marking the default."""
    names = profile_store.list_profile_names()
    if not names:
        _console.print("no profiles defined")
        return
    default = profile_store.default_profile_name()
    for name in names:
        marker = " (default)" if name == default else ""
        _console.print(f"{name}{marker}", markup=False)


@app.command(name="describe")
def describe(name: str, /) -> None:
    """Show a profile's fields plus its (redacted) api_key.

    Raises:
        ConfigError: if ``name`` is not a defined profile.
    """
    if not profile_store.profile_exists(name):
        available = ", ".join(profile_store.list_profile_names()) or "(none)"
        raise ConfigError(f"unknown profile {name!r}; available: {available}")
    profile = profile_store.read_profile(name)
    for key in _DESCRIBE_ORDER:
        if key in profile:
            _console.print(f"{key} = {profile[key]!r}", markup=False)
    credential = profile.get("credential") or "default"
    api_key = credential_store.get_api_key(str(credential))
    shown = _redact(api_key) if api_key else "(unset)"
    _console.print(f"api_key = {shown}  (credential {credential!r})", markup=False)


def _redact(value: str) -> str:
    return f"…{value[-4:]}" if len(value) > 4 else "****"
