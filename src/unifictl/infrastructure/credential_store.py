"""The credentials store: a single ``0600`` ``credentials.toml`` of API keys.

Sections are credential names; each holds one ``api_key``. This is the only
unifictl file that stores secrets, and the only one required to be ``0600``.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

import tomlkit
from xdg_base_dirs import xdg_config_home

from unifictl.infrastructure.config import ConfigError


def credentials_path() -> Path:
    """Return the path to ``credentials.toml``."""
    return xdg_config_home() / "unifictl" / "credentials.toml"


def _write_0600(path: Path, text: str) -> None:
    """Write text to path, ensuring the file is 0600 from creation (no window).

    ``os.open`` with an explicit mode applies ``0600`` atomically when the file is
    created (umask does not widen 0600). The trailing ``chmod`` tightens the case
    where the file pre-existed with looser permissions.
    """
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    path.chmod(0o600)


def read_credentials() -> dict[str, dict[str, object]]:
    """Return the parsed credential sections, enforcing ``0600``.

    Returns:
        A mapping of credential name to its ``{"api_key": ...}`` table; ``{}``
        when the file is absent.

    Raises:
        ConfigError: if the file exists and is group/world-readable.
    """
    path = credentials_path()
    if not path.exists():
        return {}
    if path.stat().st_mode & 0o077:
        raise ConfigError(f"{path} is group/world-readable; run: chmod 600 {path}")
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    return {str(name): dict(table) for name, table in data.items() if isinstance(table, dict)}


def get_api_key(credential: str) -> str | None:
    """Return the ``api_key`` for a credential, or ``None`` if absent."""
    section = read_credentials().get(credential)
    if section is None:
        return None
    value = section.get("api_key")
    return value if isinstance(value, str) else None


def set_credential(name: str, api_key: str) -> None:
    """Create or rotate a credential's ``api_key``, writing the file ``0600``.

    Args:
        name: The credential section name.
        api_key: The API key to store.
    """
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = tomlkit.parse(path.read_text(encoding="utf-8")) if path.exists() else tomlkit.document()
    table = doc.get(name)
    if not isinstance(table, dict):
        table = tomlkit.table()
        doc[name] = table
    table["api_key"] = api_key
    _write_0600(path, tomlkit.dumps(doc))


def delete_credential(name: str) -> bool:
    """Remove a credential section. Returns ``True`` if it existed."""
    path = credentials_path()
    if not path.exists():
        return False
    doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    if name not in doc:
        return False
    del doc[name]
    _write_0600(path, tomlkit.dumps(doc))
    return True


def list_credential_names() -> list[str]:
    """Return the credential section names, sorted."""
    return sorted(read_credentials())
