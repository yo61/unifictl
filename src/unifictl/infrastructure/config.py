"""Load unifictl settings from env vars, a selected profile file, and credentials.

Connection fields (``base_url``, ``site``, TLS settings) resolve ``env >
selected profile file > built-in default``. The ``api_key`` resolves
``UNIFI_API_KEY env > credentials.toml[credential] > error``, where
``credential`` is the profile's ``credential`` field (default ``"default"``).
The profile is selected via ``UNIFI_PROFILE`` (which the ``--profile`` flag
sets) or ``config.toml``'s ``default_profile``; no selection means no profile
participates and behaviour matches the env-only setup.

Profiles live one-per-file under ``~/.config/unifictl/profiles/<name>.toml``
and never hold secrets. Secrets live in the single ``~/.config/unifictl/
credentials.toml``, which must be ``chmod 600``. Operational ``switch``
resolves from the selected profile file only; ``leaders`` comes from the
top-level ``config.toml`` only. CLI flags override both in the command layer.
See ``decisions/2026-07-13-separate-credential-store.md``.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from xdg_base_dirs import xdg_config_home

DEFAULT_TIMEOUT_MS = 30000


class ConfigError(RuntimeError):
    """Raised when required settings are missing or malformed."""


@dataclass(frozen=True)
class Settings:
    """Resolved connection secrets plus operational parameters."""

    base_url: str
    api_key: str
    site: str = "default"
    ca_cert: Path | None = None
    insecure_tls: bool = False
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    switch: str | None = None
    leaders: tuple[int, ...] = ()


def config_file_path() -> Path:
    """Return the path to unifictl's operational TOML config file."""
    return xdg_config_home() / "unifictl" / "config.toml"


def load_settings() -> Settings:
    """Build :class:`Settings` from env, the selected profile file, and credentials.

    Field resolution: ``env > profile file > built-in default`` for connection
    fields; ``UNIFI_API_KEY env > credentials[credential] > error`` for the key;
    ``leaders`` from ``config.toml``. Selection: ``UNIFI_PROFILE > default_profile
    > none``. With no profile and no env, behaviour matches the env-only setup.

    Raises:
        ConfigError: unknown selected profile, missing ``base_url``/``api_key``,
            or a group/world-readable ``credentials.toml``.
    """
    name = _selected_profile_name()
    profile = _selected_profile(name)

    base_url = os.environ.get("UNIFI_BASE_URL") or _pstr(profile, "base_url", name)
    if not base_url:
        raise ConfigError(_missing("UNIFI_BASE_URL", "base_url", name))
    api_key = _resolve_api_key(profile, name)

    ca_cert = os.environ.get("UNIFI_CA_CERT") or _pstr(profile, "ca_cert", name)
    timeout_ms = _resolve_int("UNIFI_TIMEOUT_MS", profile, "timeout_ms", name, DEFAULT_TIMEOUT_MS)
    return Settings(
        base_url=base_url,
        api_key=api_key,
        site=os.environ.get("UNIFI_SITE") or _pstr(profile, "site", name) or "default",
        ca_cert=_optional_path(ca_cert),
        insecure_tls=_resolve_bool("UNIFI_INSECURE_TLS", profile, "insecure_tls", name),
        timeout_ms=timeout_ms,
        switch=_pstr(profile, "switch", name),
        leaders=_toml_leaders(_load_toml(config_file_path())),
    )


def _selected_profile_name() -> str | None:
    """Return the selected profile name, or ``None`` if none is selected."""
    from unifictl.infrastructure import profile_store

    return os.environ.get("UNIFI_PROFILE") or profile_store.default_profile_name()


def _selected_profile(name: str | None) -> dict[str, object]:
    """Return the selected profile's fields (``{}`` if none selected).

    Args:
        name: The selected profile's name, or ``None``.

    Returns:
        The profile's key/value table.

    Raises:
        ConfigError: if ``name`` is set but no such profile exists.
    """
    from unifictl.infrastructure import profile_store

    if name is None:
        return {}
    if not profile_store.profile_exists(name):
        available = ", ".join(profile_store.list_profile_names()) or "(none)"
        raise ConfigError(f"unknown profile {name!r}; available: {available}")
    return profile_store.read_profile(name)


def _resolve_api_key(profile: dict[str, object], name: str | None) -> str:
    """Resolve the API key: env var, then the profile's bound credential.

    Args:
        profile: The selected profile's key/value table (empty if none selected).
        name: The selected profile's name, for error messages.

    Returns:
        The resolved API key.

    Raises:
        ConfigError: if neither the env var nor the credential holds a key.
    """
    from unifictl.infrastructure import credential_store

    env = os.environ.get("UNIFI_API_KEY")
    if env:
        return env
    credential = _pstr(profile, "credential", name) or "default"
    key = credential_store.get_api_key(credential)
    if key:
        return key
    if name is None:
        raise ConfigError("UNIFI_API_KEY is not set")
    raise ConfigError(
        f"UNIFI_API_KEY is not set and credential {credential!r} has no api_key; "
        f"run: unifictl credential set {credential}"
    )


def _pstr(profile: dict[str, object], key: str, name: str | None) -> str | None:
    """Read a string field from the selected profile.

    Args:
        profile: The selected profile's key/value table (empty if none selected).
        key: The profile key to read.
        name: The selected profile's name, for error messages.

    Returns:
        The string value, or ``None`` if the key is absent.

    Raises:
        ConfigError: if the value is present but not a string.
    """
    value = profile.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"profile {name!r} key {key!r} must be a string, got {value!r}")
    return value


def _missing(env_name: str, key: str, name: str | None) -> str:
    """Build a ``ConfigError`` message for a required field with no value."""
    if name is None:
        return f"{env_name} is not set"
    return f"{env_name} is not set and profile {name!r} does not define {key!r}"


def _load_toml(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _resolve_bool(env_name: str, profile: dict[str, object], key: str, name: str | None) -> bool:
    """Resolve a boolean field: env var, then profile, then ``False``.

    Args:
        env_name: The environment variable name.
        profile: The selected profile's key/value table (empty if none selected).
        key: The profile key to read.
        name: The selected profile's name, for error messages.

    Returns:
        The resolved boolean.

    Raises:
        ConfigError: if the profile value is present but not a boolean.
    """
    raw = os.environ.get(env_name)
    if raw is not None and raw.strip() != "":
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    value = profile.get(key)
    if value is None:
        return False
    if not isinstance(value, bool):
        raise ConfigError(f"profile {name!r} key {key!r} must be a boolean, got {value!r}")
    return value


def _resolve_int(
    env_name: str, profile: dict[str, object], key: str, name: str | None, default: int
) -> int:
    """Resolve an integer field: env var, then profile, then ``default``.

    Args:
        env_name: The environment variable name.
        profile: The selected profile's key/value table (empty if none selected).
        key: The profile key to read.
        name: The selected profile's name, for error messages.
        default: The built-in default, used when neither env nor profile is set.

    Returns:
        The resolved integer.

    Raises:
        ConfigError: if the env value is not an integer, or the profile value is
            present but not an integer.
    """
    raw = os.environ.get(env_name)
    if raw:
        try:
            return int(raw)
        except ValueError as exc:
            raise ConfigError(f"{env_name} must be an integer, got {raw!r}") from exc
    value = profile.get(key)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"profile {name!r} key {key!r} must be an integer, got {value!r}")
    return value


def _optional_path(raw: str | None) -> Path | None:
    return Path(raw).expanduser() if raw else None


def _toml_leaders(data: dict[str, object]) -> tuple[int, ...]:
    value = data.get("leaders")
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ConfigError(f"config.toml: leaders must be a list of integers, got {value!r}")
    leaders: list[int] = []
    for port in value:
        if isinstance(port, bool) or not isinstance(port, int):
            raise ConfigError(f"config.toml: leaders must be a list of integers, got {value!r}")
        leaders.append(port)
    return tuple(leaders)
