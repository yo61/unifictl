"""The profile store: per-profile ``profiles/<name>.toml`` files + config.toml.

Each file holds one profile's **non-secret** configuration (the filename is the
profile name). The API key lives in the credentials store, never here.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import tomlkit

from unifictl.infrastructure.config import ConfigError, config_file_path

PROFILE_KEYS = frozenset(
    {"base_url", "site", "switch", "ca_cert", "insecure_tls", "timeout_ms", "credential"}
)

PROFILE_TEMPLATE = """\
# unifictl profile: {name}
# The API key is NOT stored here — set it with: unifictl credential set {credential}
base_url = "https://192.168.1.1"   # controller URL
# site       = "default"
switch     = "aa:bb:cc:dd:ee:ff"   # MAC of the switch to operate on
# credential = "default"           # which credentials.toml section holds the api_key
# ca_cert      = "/path/to/controller-ca.pem"
# insecure_tls = false
# timeout_ms   = 30000
"""


def profiles_dir() -> Path:
    """Return the profiles directory, honouring ``profiles_dir`` in config.toml.

    A relative override is resolved against the config directory; ``~`` expands.
    Defaults to ``<config>/unifictl/profiles``.
    """
    override = _config_str("profiles_dir")
    if override is None:
        return config_file_path().parent / "profiles"
    expanded = Path(override).expanduser()
    if expanded.is_absolute():
        return expanded
    return config_file_path().parent / expanded


def profile_path(name: str) -> Path:
    """Return the path to a profile's file."""
    return profiles_dir() / f"{name}.toml"


def list_profile_names() -> list[str]:
    """Return the names (file stems) of every profile, sorted."""
    directory = profiles_dir()
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.toml"))


def profile_exists(name: str) -> bool:
    """Return whether a profile file exists."""
    return profile_path(name).is_file()


def read_profile_doc(name: str) -> tomlkit.TOMLDocument:
    """Return a profile as a mutable tomlkit document (empty if absent)."""
    path = profile_path(name)
    if not path.is_file():
        return tomlkit.document()
    return tomlkit.parse(path.read_text(encoding="utf-8"))


def read_profile(name: str) -> dict[str, object]:
    """Return a profile's validated key/value table (``{}`` if absent).

    Args:
        name: The profile name.

    Returns:
        The profile's fields as a plain dict.

    Raises:
        ConfigError: if the file contains ``api_key`` or an unknown key.
    """
    path = profile_path(name)
    if not path.is_file():
        return {}
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    if "api_key" in data:
        raise ConfigError(
            f"profile {name!r} must not contain api_key; run: unifictl credential set"
        )
    unknown = set(data) - PROFILE_KEYS
    if unknown:
        keys = ", ".join(sorted(unknown))
        raise ConfigError(f"profile {name!r} has unknown key(s): {keys}")
    return {str(key): value for key, value in data.items()}


def write_profile(name: str, fields: dict[str, object]) -> None:
    """Write a profile file from a plain dict (used for fresh writes)."""
    doc = tomlkit.document()
    for key, value in fields.items():
        doc[key] = value
    write_profile_doc(name, doc)


def write_profile_doc(name: str, doc: tomlkit.TOMLDocument) -> None:
    """Write a profile from a tomlkit document (preserves comments)."""
    path = profile_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")


def delete_profile(name: str) -> bool:
    """Remove a profile file. Returns ``True`` if it existed."""
    path = profile_path(name)
    if not path.is_file():
        return False
    path.unlink()
    return True


def default_profile_name() -> str | None:
    """Return ``default_profile`` from config.toml, or ``None``."""
    return _config_str("default_profile")


def set_default_profile(name: str) -> None:
    """Write ``default_profile = name`` into config.toml (create if absent)."""
    path = config_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = tomlkit.parse(path.read_text(encoding="utf-8")) if path.exists() else tomlkit.document()
    doc["default_profile"] = name
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")


def _config_str(key: str) -> str | None:
    path = config_file_path()
    if not path.is_file():
        return None
    with path.open("rb") as fh:
        value = tomllib.load(fh).get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"config.toml: {key} must be a string, got {value!r}")
    return value
