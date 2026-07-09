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
    """Build :class:`Settings` from the environment and the XDG TOML file.

    Returns:
        The resolved settings.

    Raises:
        ConfigError: if ``UNIFI_BASE_URL`` or ``UNIFI_API_KEY`` is unset, or if a
            TOML/env value has the wrong type.
    """
    base_url = os.environ.get("UNIFI_BASE_URL")
    api_key = os.environ.get("UNIFI_API_KEY")
    if not base_url:
        raise ConfigError("UNIFI_BASE_URL is not set")
    if not api_key:
        raise ConfigError("UNIFI_API_KEY is not set")

    data = _load_toml(config_file_path())
    return Settings(
        base_url=base_url,
        api_key=api_key,
        site=os.environ.get("UNIFI_SITE", "default"),
        ca_cert=_optional_path(os.environ.get("UNIFI_CA_CERT")),
        insecure_tls=_env_bool("UNIFI_INSECURE_TLS"),
        timeout_ms=_env_int("UNIFI_TIMEOUT_MS", DEFAULT_TIMEOUT_MS),
        switch=_toml_str(data, "switch"),
        leaders=_toml_leaders(data),
    )


def _load_toml(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _optional_path(raw: str | None) -> Path | None:
    return Path(raw).expanduser() if raw else None


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


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
