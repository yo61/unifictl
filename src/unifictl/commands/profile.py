"""``unifictl profile`` sub-app: manage connection profiles."""

from __future__ import annotations

import tomllib

import questionary
import tomlkit
from cyclopts import App
from rich.console import Console

from unifictl.commands import _editor
from unifictl.commands._prompt import prompt_api_key
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


def _require_profile(name: str) -> None:
    if not profile_store.profile_exists(name):
        available = ", ".join(profile_store.list_profile_names()) or "(none)"
        raise ConfigError(f"unknown profile {name!r}; available: {available}")


@app.command(name="describe")
def describe(name: str, /) -> None:
    """Show a profile's fields plus its (redacted) api_key.

    Raises:
        ConfigError: if ``name`` is not a defined profile.
    """
    _require_profile(name)
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
        key = prompt_api_key()
        if key:
            credential_store.set_credential(credential, key)
        else:
            _console.print(
                f"no api_key set; run: unifictl credential set {credential}", markup=False
            )


@app.command(name="edit")
def edit(name: str, /) -> None:
    """Edit an existing profile's non-secret file in $EDITOR.

    Raises:
        ConfigError: if ``name`` is not a defined profile.
    """
    _require_profile(name)
    initial = profile_store.profile_path(name).read_text(encoding="utf-8")
    text = _editor.edit_toml(initial, validate=_validate_profile_text)
    if text is None:
        _console.print("aborted")
        return
    profile_store.write_profile_doc(name, tomlkit.parse(text))


def _coerce_profile_value(key: str, value: str) -> object:
    """Coerce a `profile set` string value to the profile key's TOML type."""
    if key == "insecure_tls":
        low = value.strip().lower()
        if low in {"true", "1", "yes", "on"}:
            return True
        if low in {"false", "0", "no", "off"}:
            return False
        raise ConfigError(f"insecure_tls must be a boolean, got {value!r}")
    if key == "timeout_ms":
        try:
            return int(value)
        except ValueError as exc:
            raise ConfigError(f"timeout_ms must be an integer, got {value!r}") from exc
    return value


@app.command(name="set")
def set_(name: str, key: str, value: str, /) -> None:
    """Set a non-secret field on a profile (comments preserved).

    Raises:
        ConfigError: unknown profile, ``key == 'api_key'``, an unknown key, or a
            value that cannot be coerced to the key's type.
    """
    _require_profile(name)
    if key == "api_key":
        raise ConfigError("api_key is not a profile field; run: unifictl credential set")
    if key not in profile_store.PROFILE_KEYS:
        allowed = ", ".join(sorted(profile_store.PROFILE_KEYS))
        raise ConfigError(f"unknown key {key!r}; allowed: {allowed}")
    doc = profile_store.read_profile_doc(name)
    doc[key] = _coerce_profile_value(key, value)
    profile_store.write_profile_doc(name, doc)


@app.command(name="unset")
def unset(name: str, key: str, /) -> None:
    """Remove a field from a profile.

    Raises:
        ConfigError: if ``name`` is not a defined profile.
    """
    _require_profile(name)
    doc = profile_store.read_profile_doc(name)
    if key in doc:
        del doc[key]
        profile_store.write_profile_doc(name, doc)


@app.command(name="activate")
def activate(name: str, /) -> None:
    """Make ``name`` the default profile (writes config.toml).

    Raises:
        ConfigError: if ``name`` is not a defined profile.
    """
    _require_profile(name)
    profile_store.set_default_profile(name)
    _console.print(f"default profile is now {name!r}", markup=False)


@app.command(name="delete")
def delete(name: str, /, *, yes: bool = False) -> None:
    """Delete a profile file (credentials are left untouched).

    Args:
        name: The profile to remove.
        yes: Skip the confirmation prompt.
    """
    if not yes and not questionary.confirm(f"Delete profile {name!r}?", default=False).ask():
        _console.print("aborted")
        return
    if profile_store.delete_profile(name):
        _console.print(f"profile {name!r} deleted", markup=False)
    else:
        _console.print(f"no such profile {name!r}", markup=False)
