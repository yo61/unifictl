"""Load unifictl settings: secrets/connection from env, operational from XDG TOML.

Secrets and connection details come only from ``UNIFI_*`` environment variables
and are never read from the committed TOML file. Operational parameters (switch,
ports, num_ports) come from ``~/.config/unifictl/config.toml`` and may be
overridden by CLI flags in the command layer.
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
    """Build :class:`Settings` from env, the selected profile, and TOML defaults.

    Each field resolves ``env var > selected profile > top-level TOML default >
    built-in default``. The selected profile comes from ``UNIFI_PROFILE`` (which
    the ``--profile`` flag sets) or the TOML ``default_profile``; ``None`` means
    no profile participates and behaviour matches the env-only setup.

    Returns:
        The resolved settings.

    Raises:
        ConfigError: on an unknown or malformed profile, a group/world-readable
            file holding an inline secret, or a missing ``base_url``/``api_key``.
    """
    path = config_file_path()
    data = _load_toml(path)
    profiles = load_profiles(data)
    name, profile = _select_profile(profiles, data)
    _enforce_secret_permissions(path, profiles)

    base_url = os.environ.get("UNIFI_BASE_URL") or _profile_str(profile, "base_url", name)
    api_key = os.environ.get("UNIFI_API_KEY") or _profile_str(profile, "api_key", name)
    if not base_url:
        raise ConfigError(_missing("UNIFI_BASE_URL", "base_url", name))
    if not api_key:
        raise ConfigError(_missing("UNIFI_API_KEY", "api_key", name))

    return Settings(
        base_url=base_url,
        api_key=api_key,
        site=os.environ.get("UNIFI_SITE") or _profile_str(profile, "site", name) or "default",
        ca_cert=_optional_path(
            os.environ.get("UNIFI_CA_CERT") or _profile_str(profile, "ca_cert", name)
        ),
        insecure_tls=_resolve_bool("UNIFI_INSECURE_TLS", profile, "insecure_tls", name),
        timeout_ms=_resolve_int(
            "UNIFI_TIMEOUT_MS", profile, "timeout_ms", name, DEFAULT_TIMEOUT_MS
        ),
        switch=_profile_str(profile, "switch", name) or _toml_str(data, "switch"),
        leaders=_toml_leaders(data),
    )


def _load_toml(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


_PROFILE_KEYS = frozenset(
    {"base_url", "api_key", "site", "ca_cert", "insecure_tls", "timeout_ms", "switch"}
)


def read_config() -> dict[str, object]:
    """Return the parsed ``config.toml`` mapping (empty when the file is absent)."""
    return _load_toml(config_file_path())


def load_profiles(data: dict[str, object]) -> dict[str, dict[str, object]]:
    """Extract and structurally validate the ``[profiles.*]`` tables.

    Args:
        data: The parsed ``config.toml`` mapping.

    Returns:
        A mapping of profile name to its key/value table.

    Raises:
        ConfigError: if ``profiles`` is not a table, a profile is not a table, or
            a profile contains a key outside :data:`_PROFILE_KEYS`.
    """
    raw = data.get("profiles")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError(f"config.toml: profiles must be a table, got {raw!r}")
    profiles: dict[str, dict[str, object]] = {}
    for name, table in raw.items():
        if not isinstance(table, dict):
            raise ConfigError(f"config.toml: profile {name!r} must be a table, got {table!r}")
        unknown = set(table) - _PROFILE_KEYS
        if unknown:
            keys = ", ".join(sorted(unknown))
            raise ConfigError(f"config.toml: profile {name!r} has unknown key(s): {keys}")
        profiles[str(name)] = {str(key): value for key, value in table.items()}
    return profiles


def _select_profile(
    profiles: dict[str, dict[str, object]], data: dict[str, object]
) -> tuple[str | None, dict[str, object]]:
    """Resolve the selected profile name and table.

    Args:
        profiles: Parsed ``[profiles.*]`` tables, keyed by name.
        data: The parsed ``config.toml`` mapping (for ``default_profile``).

    Returns:
        A ``(name, profile)`` pair. ``name`` is ``None`` and ``profile`` is empty
        when no profile is selected.

    Raises:
        ConfigError: if the selected profile name is not among ``profiles``.
    """
    name = os.environ.get("UNIFI_PROFILE") or _toml_str(data, "default_profile")
    if name is None:
        return None, {}
    if name not in profiles:
        available = ", ".join(sorted(profiles)) or "(none)"
        raise ConfigError(f"unknown profile {name!r}; available: {available}")
    return name, profiles[name]


def _missing(env_name: str, key: str, name: str | None) -> str:
    """Build a ``ConfigError`` message for a required field with no value."""
    if name is None:
        return f"{env_name} is not set"
    return f"{env_name} is not set and profile {name!r} does not define {key!r}"


def _profile_str(profile: dict[str, object], key: str, name: str | None) -> str | None:
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
        raise ConfigError(
            f"config.toml: profile {name!r} key {key!r} must be a string, got {value!r}"
        )
    return value


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
        raise ConfigError(
            f"config.toml: profile {name!r} key {key!r} must be a boolean, got {value!r}"
        )
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
        raise ConfigError(
            f"config.toml: profile {name!r} key {key!r} must be an integer, got {value!r}"
        )
    return value


def _enforce_secret_permissions(path: Path, profiles: dict[str, dict[str, object]]) -> None:
    """Refuse a group/world-readable config file that holds an inline secret.

    Args:
        path: The config file path.
        profiles: The parsed profile tables.

    Raises:
        ConfigError: if the file is group/world-readable and any profile carries
            an inline ``api_key``.
    """
    if not path.exists():
        return
    if not any("api_key" in table for table in profiles.values()):
        return
    if path.stat().st_mode & 0o077:
        raise ConfigError(
            f"{path} is group/world-readable but holds an inline api_key; run: chmod 600 {path}"
        )


def _optional_path(raw: str | None) -> Path | None:
    return Path(raw).expanduser() if raw else None


def _toml_str(data: dict[str, object], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"config.toml: {key} must be a string, got {value!r}")
    return value


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
