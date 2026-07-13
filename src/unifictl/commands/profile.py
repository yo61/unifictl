"""``unifictl profile`` sub-app: manage connection profiles."""

from __future__ import annotations

import tomllib

import questionary
import tomlkit
from cyclopts import App
from rich.console import Console

from unifictl.commands import _editor
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


def _prompt_key() -> str:
    return str(questionary.password("API key:").ask() or "")


def _validate_profile_text(text: str) -> None:
    """Validate edited profile TOML: parseable, no api_key, only allowed keys.

    Raises:
        ConfigError: on invalid TOML, an ``api_key`` field, or an unknown key.
        (The editor loop catches this, shows it, and re-opens the editor.)
    """
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML: {exc}") from exc
    if "api_key" in data:
        raise ConfigError("api_key belongs in credentials.toml (unifictl credential set)")
    unknown = set(data) - profile_store.PROFILE_KEYS
    if unknown:
        raise ConfigError(f"unknown key(s): {', '.join(sorted(unknown))}")


@app.command(name="create")
def create(name: str, /) -> None:
    """Create a profile in $EDITOR, then set its credential if missing.

    Args:
        name: The new profile's name.
    """
    template = profile_store.PROFILE_TEMPLATE.format(name=name, credential="default")
    text = _editor.edit_toml(template, validate=_validate_profile_text)
    if text is None:
        _console.print("aborted")
        return
    profile_store.write_profile_doc(name, tomlkit.parse(text))
    new_profile = profile_store.read_profile(name)
    credential = str(new_profile.get("credential") or "default")
    if credential_store.get_api_key(credential) is None:
        key = _prompt_key()
        if key:
            credential_store.set_credential(credential, key)


@app.command(name="edit")
def edit(name: str, /) -> None:
    """Edit an existing profile's non-secret file in $EDITOR.

    Raises:
        ConfigError: if ``name`` is not a defined profile.
    """
    if not profile_store.profile_exists(name):
        available = ", ".join(profile_store.list_profile_names()) or "(none)"
        raise ConfigError(f"unknown profile {name!r}; available: {available}")
    initial = profile_store.profile_path(name).read_text(encoding="utf-8")
    text = _editor.edit_toml(initial, validate=_validate_profile_text)
    if text is None:
        _console.print("aborted")
        return
    profile_store.write_profile_doc(name, tomlkit.parse(text))
