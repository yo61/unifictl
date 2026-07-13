# Profiles & Credentials Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace PR #11's single-file `[profiles.*]` model with a file-per-profile store plus a separate credential store, and add `profile`/`credential` CRUD commands.

**Architecture:** Two new infrastructure stores own all filesystem + TOML I/O: `credential_store.py` (the single `0600` `credentials.toml`) and `profile_store.py` (the `profiles/<name>.toml` directory + `config.toml` selection keys). `load_settings()` resolves the unchanged `Settings` from env → profile file → credential store. Commands (`profile …`, `credential …`) sit on top; `create`/`edit` drive `$EDITOR` for non-secret fields while the API key only ever arrives via a hidden prompt / `--stdin`.

**Tech Stack:** Python ≥3.11, cyclopts (CLI), rich (output), questionary (prompts), `tomllib` (stdlib read), **`tomlkit`** (comment-preserving write), `xdg-base-dirs`, pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-13-profiles-credentials-redesign-design.md`. Decision: `decisions/2026-07-13-separate-credential-store.md` (supersedes the `2026-07-12` inline-secrets one).
- This revises PR #11 on the **same branch** (`feat/config-profiles`). No migration — nothing shipped.
- TDD: write the failing test, run it and watch it fail, implement, run it and watch it pass, commit. One logical change per commit; imperative ≤72-char subject.
- Storage under `xdg_config_home()/unifictl/`: `config.toml` (keys `default_profile`, `profiles_dir`, `leaders`), `profiles/<name>.toml` (one non-secret profile each), `credentials.toml` (single file, `[<credential>]` sections each with `api_key`).
- Allowed profile-file keys: `base_url`, `site`, `switch`, `ca_cert`, `insecure_tls`, `timeout_ms`, `credential`. `api_key` inside a profile file is **rejected** (→ use `credential set`). Unknown keys rejected.
- Profile → credential binding: profile's optional `credential` field, **defaults to `"default"`**.
- Field resolution: `base_url`/`site`/`ca_cert`/`insecure_tls`/`timeout_ms` = `UNIFI_* env > profile file > built-in`; `api_key` = `UNIFI_API_KEY env > credentials[credential].api_key > ConfigError`; `switch` = `--switch (command layer) > profile file`; `leaders` = `--leader > config.toml leaders > ()`.
- Profile selection: `UNIFI_PROFILE (set by --profile) > default_profile (config.toml) > none`. Unknown selected profile ⇒ `ConfigError` listing available profile names.
- Secrets: only `credentials.toml`, created/kept `0600`; a group/world-readable `credentials.toml` is refused (`chmod 600` hint) whenever a key is read. `profiles/*.toml` and `config.toml` use normal perms. No command prints a raw `api_key`; `describe` redacts.
- `$EDITOR` never receives the secret. `create`/`edit` use `$VISUAL` then `$EDITOR`; neither set ⇒ `ConfigError`.
- Code style: absolute imports only, `from __future__ import annotations`, Google-style docstrings on public APIs, functions ≤100 lines / ≤5 positional params, 100-char lines. Zero-warning gate: `prek` runs ruff/ruff-format/ty/import-linter/commitlint on commit (`ty check src`).
- Import boundaries (import-linter): `infrastructure` must not import `domain`/`application`; `commands > application > domain`. New stores are `infrastructure`; commands may import them.

---

## File Structure

- `pyproject.toml` — MODIFY. Swap unused `tomli-w` for `tomlkit`.
- `src/unifictl/infrastructure/credential_store.py` — CREATE. `credentials.toml` I/O + `0600`.
- `src/unifictl/infrastructure/profile_store.py` — CREATE. `profiles/` dir + profile files + `config.toml` selection keys + template.
- `src/unifictl/infrastructure/config.py` — MODIFY. Rewrite `load_settings` resolution onto the stores; delete superseded helpers; update module docstring.
- `src/unifictl/commands/_editor.py` — CREATE. `$EDITOR` launch + validate-on-save loop.
- `src/unifictl/commands/profile.py` — REWRITE. `create/edit/set/unset/list/describe/activate/delete`.
- `src/unifictl/commands/credential.py` — CREATE. `set/list/delete`.
- `src/unifictl/cli.py` — MODIFY. Register the `credential` sub-app.
- `src/unifictl/commands/_complete.py` — MODIFY. New `profile` sub-commands + `credential` tree.
- `tests/` — `test_credential_store.py`, `test_profile_store.py` (CREATE); `test_editor.py`, `test_cmd_credential.py` (CREATE); `test_config.py`, `test_cmd_profile.py`, `test_complete.py`, `test_cli.py` (MODIFY).
- `README.md` — MODIFY. Rewrite the Profiles section.

**Verified during planning:** `tomli-w` is declared in `pyproject.toml` but used nowhere (grep clean) — safe to remove. `questionary.confirm(...).ask()` is the existing prompt idiom (`set.py:74`); `questionary.password(...).ask()` gives hidden input. `Settings` (config.py:31-42) is unchanged by this work. `tests/conftest.py` already isolates `UNIFI_PROFILE`.

---

## Task 1: Credential store

**Files:**
- Modify: `pyproject.toml:14` (swap `tomli-w` → `tomlkit`)
- Create: `src/unifictl/infrastructure/credential_store.py`
- Test: `tests/test_credential_store.py`

**Interfaces:**
- Produces: `credentials_path() -> Path`; `read_credentials() -> dict[str, dict[str, object]]` (enforces `0600`, `{}` if absent); `get_api_key(credential: str) -> str | None`; `set_credential(name: str, api_key: str) -> None` (writes `0600`); `delete_credential(name: str) -> bool`; `list_credential_names() -> list[str]`. Reuses `ConfigError` from `unifictl.infrastructure.config`.

- [ ] **Step 1: Swap the dependency**

Edit `pyproject.toml`: replace the line `    "tomli-w>=1.0",` with `    "tomlkit>=0.13",`. Then run `uv lock` to update `uv.lock`.

Run: `uv lock && uv sync`
Expected: lock updates, `tomlkit` installed, `tomli-w` gone.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_credential_store.py`:

```python
"""Tests for the credentials.toml store (single 0600 secret file)."""

from __future__ import annotations

import os

import pytest

from unifictl.infrastructure import credential_store
from unifictl.infrastructure.config import ConfigError


def test_read_absent_returns_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert credential_store.read_credentials() == {}


def test_set_then_get_roundtrip(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    credential_store.set_credential("default", "sekret")
    assert credential_store.get_api_key("default") == "sekret"


def test_set_creates_file_0600(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    credential_store.set_credential("default", "sekret")
    mode = credential_store.credentials_path().stat().st_mode & 0o777
    assert mode == 0o600


def test_read_refuses_group_readable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    credential_store.set_credential("default", "sekret")
    os.chmod(credential_store.credentials_path(), 0o644)
    with pytest.raises(ConfigError, match="chmod 600"):
        credential_store.read_credentials()


def test_set_rotates_existing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    credential_store.set_credential("default", "old")
    credential_store.set_credential("default", "new")
    assert credential_store.get_api_key("default") == "new"


def test_list_and_delete(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    credential_store.set_credential("default", "a")
    credential_store.set_credential("work", "b")
    assert credential_store.list_credential_names() == ["default", "work"]
    assert credential_store.delete_credential("work") is True
    assert credential_store.list_credential_names() == ["default"]
    assert credential_store.delete_credential("missing") is False


def test_get_missing_credential_returns_none(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert credential_store.get_api_key("nope") is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_credential_store.py -v`
Expected: FAIL — `ModuleNotFoundError: unifictl.infrastructure.credential_store`.

- [ ] **Step 4: Implement**

Create `src/unifictl/infrastructure/credential_store.py`:

```python
"""The credentials store: a single ``0600`` ``credentials.toml`` of API keys.

Sections are credential names; each holds one ``api_key``. This is the only
unifictl file that stores secrets, and the only one required to be ``0600``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import tomlkit
from xdg_base_dirs import xdg_config_home

from unifictl.infrastructure.config import ConfigError


def credentials_path() -> Path:
    """Return the path to ``credentials.toml``."""
    return xdg_config_home() / "unifictl" / "credentials.toml"


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
        raise ConfigError(
            f"{path} is group/world-readable; run: chmod 600 {path}"
        )
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
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")
    path.chmod(0o600)


def delete_credential(name: str) -> bool:
    """Remove a credential section. Returns ``True`` if it existed."""
    path = credentials_path()
    if not path.exists():
        return False
    doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    if name not in doc:
        return False
    del doc[name]
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")
    path.chmod(0o600)
    return True


def list_credential_names() -> list[str]:
    """Return the credential section names, sorted."""
    return sorted(read_credentials())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_credential_store.py -v`
Expected: PASS (7 tests).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/unifictl/infrastructure/credential_store.py tests/test_credential_store.py
git commit -m "feat: add credentials store and swap tomli-w for tomlkit"
```

---

## Task 2: Profile store

**Files:**
- Create: `src/unifictl/infrastructure/profile_store.py`
- Test: `tests/test_profile_store.py`

**Interfaces:**
- Consumes: `config_file_path`, `ConfigError` from `config`.
- Produces: `PROFILE_KEYS: frozenset[str]`; `profiles_dir() -> Path`; `profile_path(name) -> Path`; `list_profile_names() -> list[str]`; `read_profile(name) -> dict[str, object]` (validates key names, `{}` if file absent); `profile_exists(name) -> bool`; `write_profile(name, doc: dict) -> None`; `delete_profile(name) -> bool`; `default_profile_name() -> str | None`; `set_default_profile(name) -> None`; `PROFILE_TEMPLATE: str`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_profile_store.py`:

```python
"""Tests for the profile store (per-profile files + config.toml selection)."""

from __future__ import annotations

import pytest

from unifictl.infrastructure import profile_store
from unifictl.infrastructure.config import ConfigError


def _write_profile(tmp_path, name: str, body: str) -> None:
    d = tmp_path / "unifictl" / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.toml").write_text(body, encoding="utf-8")


def test_profiles_dir_default(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert profile_store.profiles_dir() == tmp_path / "unifictl" / "profiles"


def test_profiles_dir_absolute_override(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg = tmp_path / "unifictl"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "config.toml").write_text(f'profiles_dir = "{tmp_path}/custom"\n', encoding="utf-8")
    assert profile_store.profiles_dir() == tmp_path / "custom"


def test_profiles_dir_relative_override(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg = tmp_path / "unifictl"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "config.toml").write_text('profiles_dir = "prof"\n', encoding="utf-8")
    assert profile_store.profiles_dir() == cfg / "prof"


def test_list_and_read(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_profile(tmp_path, "home", 'base_url = "https://h"\nswitch = "aa"\n')
    _write_profile(tmp_path, "lab", 'base_url = "https://l"\n')
    assert profile_store.list_profile_names() == ["home", "lab"]
    assert profile_store.read_profile("home") == {"base_url": "https://h", "switch": "aa"}
    assert profile_store.profile_exists("home") is True
    assert profile_store.read_profile("missing") == {}


def test_read_rejects_api_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_profile(tmp_path, "home", 'api_key = "leak"\n')
    with pytest.raises(ConfigError, match="api_key.*credential set"):
        profile_store.read_profile("home")


def test_read_rejects_unknown_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_profile(tmp_path, "home", 'nope = 1\n')
    with pytest.raises(ConfigError, match="home.*nope"):
        profile_store.read_profile("home")


def test_write_profile_roundtrip_and_delete(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profile_store.write_profile("home", {"base_url": "https://h", "switch": "aa"})
    assert profile_store.read_profile("home") == {"base_url": "https://h", "switch": "aa"}
    assert profile_store.delete_profile("home") is True
    assert profile_store.delete_profile("home") is False


def test_write_preserves_comments(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_profile(tmp_path, "home", '# my note\nbase_url = "https://h"\n')
    doc = profile_store.read_profile_doc("home")
    doc["switch"] = "aa"
    profile_store.write_profile_doc("home", doc)
    text = profile_store.profile_path("home").read_text(encoding="utf-8")
    assert "# my note" in text
    assert 'switch = "aa"' in text


def test_default_profile_read_write(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert profile_store.default_profile_name() is None
    profile_store.set_default_profile("home")
    assert profile_store.default_profile_name() == "home"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_profile_store.py -v`
Expected: FAIL — `ModuleNotFoundError: unifictl.infrastructure.profile_store`.

- [ ] **Step 3: Implement**

Create `src/unifictl/infrastructure/profile_store.py`:

```python
"""The profile store: per-profile ``profiles/<name>.toml`` files + config.toml.

Each file holds one profile's **non-secret** configuration (the filename is the
profile name). The API key lives in the credentials store, never here.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import tomlkit
from xdg_base_dirs import xdg_config_home

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_profile_store.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/infrastructure/profile_store.py tests/test_profile_store.py
git commit -m "feat: add per-profile file store"
```

---

## Task 3: Cutover load_settings + profile read commands to the stores

**Files:**
- Modify: `src/unifictl/infrastructure/config.py` (rewrite `load_settings`; delete superseded helpers; update docstring)
- Modify: `src/unifictl/commands/profile.py` (list/describe on the store; remove `example`, `show`)
- Test: `tests/test_config.py` (rewrite profile tests), `tests/test_cmd_profile.py` (rewrite)

**Interfaces:**
- Consumes: `profile_store.{list_profile_names,read_profile,default_profile_name}`, `credential_store.get_api_key` (Tasks 1-2).
- Produces: rewritten `load_settings() -> Settings`; new `commands/profile.py` with `list_()`, `describe(name)`. Removes `read_config`, `load_profiles`, `_select_profile`, `_profile_str`, `_enforce_secret_permissions` from `config.py`.

- [ ] **Step 1: Write the failing tests (config resolution)**

Replace the profile-related tests in `tests/test_config.py` with these (keep the pre-existing env-only tests like `test_missing_base_url_raises`, `test_env_defaults`; DELETE tests that reference `load_profiles`, `read_config`, `_write_config` writing `[profiles.x]`, and the old `_enforce_secret_permissions` tests):

```python
from unifictl.infrastructure import credential_store, profile_store


def _profile(tmp_path, name: str, body: str) -> None:
    d = tmp_path / "unifictl" / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.toml").write_text(body, encoding="utf-8")


def test_profile_file_supplies_connection(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for v in ("UNIFI_BASE_URL", "UNIFI_API_KEY", "UNIFI_SITE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    _profile(tmp_path, "home", 'base_url = "https://home"\nsite = "s1"\nswitch = "aa:bb"\n')
    credential_store.set_credential("default", "hk")
    s = load_settings()
    assert (s.base_url, s.api_key, s.site, s.switch) == ("https://home", "hk", "s1", "aa:bb")


def test_named_credential(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("UNIFI_API_KEY", raising=False)
    monkeypatch.setenv("UNIFI_BASE_URL", "https://gw")
    monkeypatch.setenv("UNIFI_PROFILE", "office")
    _profile(tmp_path, "office", 'credential = "work"\n')
    credential_store.set_credential("work", "wk")
    assert load_settings().api_key == "wk"


def test_env_api_key_beats_credential(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("UNIFI_BASE_URL", "https://gw")
    monkeypatch.setenv("UNIFI_API_KEY", "envkey")
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    _profile(tmp_path, "home", "")
    credential_store.set_credential("default", "credkey")
    assert load_settings().api_key == "envkey"


def test_missing_credential_names_command(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("UNIFI_API_KEY", raising=False)
    monkeypatch.setenv("UNIFI_BASE_URL", "https://gw")
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    _profile(tmp_path, "home", "")
    with pytest.raises(ConfigError, match="credential set"):
        load_settings()


def test_unknown_profile_lists_available(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("UNIFI_BASE_URL", "https://gw")
    monkeypatch.setenv("UNIFI_API_KEY", "k")
    monkeypatch.setenv("UNIFI_PROFILE", "ghost")
    _profile(tmp_path, "home", "")
    with pytest.raises(ConfigError, match="unknown profile 'ghost'.*home"):
        load_settings()


def test_default_profile_from_config(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("UNIFI_PROFILE", raising=False)
    monkeypatch.delenv("UNIFI_BASE_URL", raising=False)
    monkeypatch.delenv("UNIFI_API_KEY", raising=False)
    _profile(tmp_path, "home", 'base_url = "https://home"\n')
    credential_store.set_credential("default", "hk")
    profile_store.set_default_profile("home")
    assert load_settings().base_url == "https://home"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -k "profile or credential" -v`
Expected: FAIL — `load_settings` still reads `[profiles.*]` from config.toml, so credential/profile-file resolution isn't wired.

- [ ] **Step 3: Rewrite `load_settings` and delete superseded helpers**

In `src/unifictl/infrastructure/config.py`, replace `load_settings` and remove `read_config`, `load_profiles`, `_PROFILE_KEYS`, `_select_profile`, `_profile_str`, `_enforce_secret_permissions`, `_toml_str` (now unused here). Keep `Settings`, `config_file_path`, `_load_toml`, `_optional_path`, `_resolve_bool`, `_resolve_int`, `_toml_leaders`, `DEFAULT_TIMEOUT_MS`, `ConfigError`. Add imports at the top:

```python
from unifictl.infrastructure import credential_store, profile_store
```

New `load_settings` (and small helpers):

```python
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

    return Settings(
        base_url=base_url,
        api_key=api_key,
        site=os.environ.get("UNIFI_SITE") or _pstr(profile, "site", name) or "default",
        ca_cert=_optional_path(os.environ.get("UNIFI_CA_CERT") or _pstr(profile, "ca_cert", name)),
        insecure_tls=_resolve_bool("UNIFI_INSECURE_TLS", profile, "insecure_tls", name),
        timeout_ms=_resolve_int("UNIFI_TIMEOUT_MS", profile, "timeout_ms", name, DEFAULT_TIMEOUT_MS),
        switch=_pstr(profile, "switch", name),
        leaders=_toml_leaders(_load_toml(config_file_path())),
    )


def _selected_profile_name() -> str | None:
    return os.environ.get("UNIFI_PROFILE") or profile_store.default_profile_name()


def _selected_profile(name: str | None) -> dict[str, object]:
    if name is None:
        return {}
    if not profile_store.profile_exists(name):
        available = ", ".join(profile_store.list_profile_names()) or "(none)"
        raise ConfigError(f"unknown profile {name!r}; available: {available}")
    return profile_store.read_profile(name)


def _resolve_api_key(profile: dict[str, object], name: str | None) -> str:
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
    value = profile.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"profile {name!r} key {key!r} must be a string, got {value!r}")
    return value
```

Keep `_missing`, but simplify to the `base_url` case (api_key has its own message now):

```python
def _missing(env_name: str, key: str, name: str | None) -> str:
    if name is None:
        return f"{env_name} is not set"
    return f"{env_name} is not set and profile {name!r} does not define {key!r}"
```

Import-boundary note: `config.py` importing `profile_store`/`credential_store` is `infrastructure → infrastructure`, allowed. But `profile_store`/`credential_store` import `ConfigError`/`config_file_path` from `config` — that's a cycle at module level. Break it: `credential_store`/`profile_store` import `config` lazily is unnecessary if `ConfigError`/`config_file_path` are defined **before** the store imports execute. Because `config.py` imports the stores at top level and the stores import back, move the store import in `config.py` to the **bottom** of the module (after `ConfigError`, `config_file_path`, and all helpers are defined) OR import inside `load_settings`/helpers. Simplest and clean: import the stores **inside** the functions that use them (`_selected_profile_name`, `_selected_profile`, `_resolve_api_key`) — local imports avoid the cycle and keep the read path lazy. Use that.

Update the module docstring (lines 1-13) to describe the new model (env or profile file for connection; api_key from env or credentials.toml; credentials.toml is the 0600 file; leaders from config.toml) and reference `decisions/2026-07-13-separate-credential-store.md`.

- [ ] **Step 4: Rewrite the profile read commands**

Replace `src/unifictl/commands/profile.py` with the read-only subset on the new store (create/edit/set/unset/activate/delete land in Tasks 5-7):

```python
"""``unifictl profile`` sub-app: manage connection profiles."""

from __future__ import annotations

from cyclopts import App
from rich.console import Console

from unifictl.infrastructure import credential_store, profile_store
from unifictl.infrastructure.config import ConfigError

app = App(name="profile", help="Manage connection profiles.")
_console = Console()

_DESCRIBE_ORDER = ("base_url", "site", "switch", "credential", "ca_cert", "insecure_tls", "timeout_ms")


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
```

- [ ] **Step 5: Rewrite the profile command tests**

Replace `tests/test_cmd_profile.py` with tests for `list_`/`describe` on the store (delete the old `list`/`show`/`example` tests):

```python
"""`unifictl profile` list/describe behavior."""

from __future__ import annotations

import pytest

from unifictl.commands import profile
from unifictl.infrastructure import credential_store, profile_store
from unifictl.infrastructure.config import ConfigError


def _profile(tmp_path, name: str, body: str) -> None:
    d = tmp_path / "unifictl" / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.toml").write_text(body, encoding="utf-8")


def test_list_marks_default(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _profile(tmp_path, "home", 'base_url = "https://h"\n')
    _profile(tmp_path, "lab", 'base_url = "https://l"\n')
    profile_store.set_default_profile("home")
    profile.list_()
    out = capsys.readouterr().out
    assert "home (default)" in out
    assert "lab" in out


def test_list_empty(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profile.list_()
    assert "no profiles defined" in capsys.readouterr().out


def test_describe_redacts_key(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _profile(tmp_path, "home", 'base_url = "https://h"\n')
    credential_store.set_credential("default", "supersecret")
    profile.describe("home")
    out = capsys.readouterr().out
    assert "supersecret" not in out
    assert "cret" in out
    assert "https://h" in out


def test_describe_unknown_raises(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(ConfigError, match="unknown profile 'ghost'"):
        profile.describe("ghost")
```

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS. If any test still imports removed symbols (`load_profiles`, `read_config`, `example`), delete/rewrite it — those belong to the retired v1 surface.

- [ ] **Step 7: Commit**

```bash
git add src/unifictl/infrastructure/config.py src/unifictl/commands/profile.py tests/test_config.py tests/test_cmd_profile.py
git commit -m "feat: resolve settings from profile files and credentials store"
```

---

## Task 4: Editor helper

**Files:**
- Create: `src/unifictl/commands/_editor.py`
- Test: `tests/test_editor.py`

**Interfaces:**
- Produces: `edit_toml(initial: str, validate: Callable[[str], None]) -> str | None` — opens `$VISUAL`/`$EDITOR` on a temp file seeded with `initial`, re-opens on `validate` failure, returns the final text or `None` if the user made no change to an invalid/empty buffer (abort). `EditorError(ConfigError)` when no editor is configured.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_editor.py`:

```python
"""Tests for the $EDITOR launch + validate-on-save helper."""

from __future__ import annotations

import pytest

from unifictl.commands import _editor
from unifictl.infrastructure.config import ConfigError


def _fake_editor(script: str, monkeypatch, tmp_path):
    """Install a fake editor that runs `script` (a python snippet) on the file arg."""
    editor = tmp_path / "fake-editor.py"
    editor.write_text(script, encoding="utf-8")
    monkeypatch.setenv("VISUAL", f"python {editor}")
    monkeypatch.delenv("EDITOR", raising=False)


def test_no_editor_configured_raises(monkeypatch) -> None:
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.delenv("EDITOR", raising=False)
    with pytest.raises(ConfigError, match="EDITOR"):
        _editor.edit_toml("x = 1\n", validate=lambda _t: None)


def test_returns_edited_text(monkeypatch, tmp_path) -> None:
    # editor appends a line, then the content validates
    _fake_editor(
        'import sys\n'
        'p = sys.argv[1]\n'
        'open(p, "a").write(\'switch = "aa"\\n\')\n',
        monkeypatch,
        tmp_path,
    )
    out = _editor.edit_toml('base_url = "https://h"\n', validate=lambda _t: None)
    assert 'switch = "aa"' in out


def test_reopens_on_validation_error_then_aborts(monkeypatch, tmp_path) -> None:
    # editor makes no change; validate always fails; helper aborts → None
    _fake_editor("import sys\n", monkeypatch, tmp_path)

    def always_fail(_text: str) -> None:
        raise ConfigError("bad")

    assert _editor.edit_toml("broken\n", validate=always_fail) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_editor.py -v`
Expected: FAIL — `ModuleNotFoundError: unifictl.commands._editor`.

- [ ] **Step 3: Implement**

Create `src/unifictl/commands/_editor.py`:

```python
"""Launch ``$EDITOR`` on a temp file with a validate-on-save loop.

Used by ``profile create``/``edit`` for the non-secret profile file. The API key
never passes through here — it is prompted separately.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from unifictl.infrastructure.config import ConfigError


def _editor_command() -> list[str]:
    raw = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not raw:
        raise ConfigError("no editor configured; set $EDITOR (or $VISUAL)")
    return shlex.split(raw)


def edit_toml(initial: str, validate: Callable[[str], None]) -> str | None:
    """Edit ``initial`` in ``$EDITOR``; re-open on validation failure.

    Args:
        initial: The starting buffer contents.
        validate: Called with the edited text; raises ``ConfigError`` if invalid.

    Returns:
        The validated text, or ``None`` if the user left an invalid buffer
        unchanged (abort).

    Raises:
        ConfigError: if no editor is configured.
    """
    command = _editor_command()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "profile.toml"
        path.write_text(initial, encoding="utf-8")
        previous = initial
        while True:
            subprocess.run([*command, str(path)], check=True)  # noqa: S603
            text = path.read_text(encoding="utf-8")
            try:
                validate(text)
                return text
            except ConfigError as exc:
                if text == previous:
                    return None  # unchanged after an error → abort
                previous = text
                print(f"invalid: {exc}\nre-opening editor…")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_editor.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/commands/_editor.py tests/test_editor.py
git commit -m "feat: add editor launch helper with validate-on-save"
```

---

## Task 5: Credential commands

**Files:**
- Create: `src/unifictl/commands/credential.py`
- Modify: `src/unifictl/cli.py` (register the sub-app)
- Test: `tests/test_cmd_credential.py`

**Interfaces:**
- Consumes: `credential_store.{set_credential,list_credential_names,delete_credential}`; `questionary`.
- Produces: `credential.app` with `set_(name="default", *, stdin=False)`, `list_()`, `delete(name, *, yes=False)`; registered in `cli.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cmd_credential.py`:

```python
"""`unifictl credential` set/list/delete behavior."""

from __future__ import annotations

import io

import pytest

from unifictl.commands import credential
from unifictl.infrastructure import credential_store


def test_set_from_stdin(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr("sys.stdin", io.StringIO("sekret\n"))
    credential.set_(stdin=True)
    assert credential_store.get_api_key("default") == "sekret"


def test_set_hidden_prompt(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(credential, "_prompt_key", lambda: "prompted")
    credential.set_("work")
    assert credential_store.get_api_key("work") == "prompted"


def test_list_shows_names_no_keys(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    credential_store.set_credential("default", "aaaa")
    credential.list_()
    out = capsys.readouterr().out
    assert "default" in out
    assert "aaaa" not in out


def test_delete_with_yes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    credential_store.set_credential("work", "b")
    credential.delete("work", yes=True)
    assert credential_store.list_credential_names() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cmd_credential.py -v`
Expected: FAIL — `ModuleNotFoundError: unifictl.commands.credential`.

- [ ] **Step 3: Implement**

Create `src/unifictl/commands/credential.py`:

```python
"""``unifictl credential`` sub-app: manage API keys in credentials.toml."""

from __future__ import annotations

import sys

import questionary
from cyclopts import App
from rich.console import Console

from unifictl.infrastructure import credential_store
from unifictl.infrastructure.config import ConfigError

app = App(name="credential", help="Manage API keys (credentials.toml, 0600).")
_console = Console()


def _prompt_key() -> str:
    return str(questionary.password("API key:").ask() or "")


@app.command(name="set")
def set_(name: str = "default", /, *, stdin: bool = False) -> None:
    """Set or rotate a credential's API key (written 0600).

    Args:
        name: Credential section name. Defaults to ``default``.
        stdin: Read the key from stdin instead of a hidden prompt.
    """
    key = sys.stdin.readline().strip() if stdin else _prompt_key()
    if not key:
        raise ConfigError("no API key provided")
    credential_store.set_credential(name, key)
    _console.print(f"credential {name!r} set", markup=False)


@app.command(name="list")
def list_() -> None:
    """List credential names (never prints keys)."""
    names = credential_store.list_credential_names()
    if not names:
        _console.print("no credentials defined")
        return
    for name in names:
        _console.print(name, markup=False)


@app.command(name="delete")
def delete(name: str, /, *, yes: bool = False) -> None:
    """Delete a credential section.

    Args:
        name: The credential to remove.
        yes: Skip the confirmation prompt.
    """
    if not yes and not questionary.confirm(f"Delete credential {name!r}?", default=False).ask():
        _console.print("aborted")
        return
    if credential_store.delete_credential(name):
        _console.print(f"credential {name!r} deleted", markup=False)
    else:
        _console.print(f"no such credential {name!r}", markup=False)
```

In `src/unifictl/cli.py`, inside `get_app`, import and register alongside the others:

```python
    from unifictl.commands.credential import app as credential_app
    ...
    app.command(credential_app)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cmd_credential.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/commands/credential.py src/unifictl/cli.py tests/test_cmd_credential.py
git commit -m "feat: add credential set/list/delete commands"
```

---

## Task 6: profile create & edit

**Files:**
- Modify: `src/unifictl/commands/profile.py` (add `create`, `edit`)
- Test: `tests/test_cmd_profile.py`

**Interfaces:**
- Consumes: `_editor.edit_toml`, `profile_store.{read_profile,write_profile_doc,read_profile_doc,PROFILE_TEMPLATE,PROFILE_KEYS,profile_exists}`, `credential_store.get_api_key`, `credential._prompt_key` pattern (`questionary.password`).
- Produces: `create(name, /)`, `edit(name, /)`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cmd_profile.py`:

```python
import tomllib

from unifictl.commands import _editor


def test_create_writes_profile_and_prompts_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    # fake editor: user accepts a valid non-secret profile
    monkeypatch.setattr(
        _editor, "edit_toml", lambda initial, validate: 'base_url = "https://h"\nswitch = "aa"\n'
    )
    monkeypatch.setattr(profile, "_prompt_key", lambda: "newkey")
    profile.create("home")
    body = (tmp_path / "unifictl" / "profiles" / "home.toml").read_text()
    parsed = tomllib.loads(body)
    assert parsed == {"base_url": "https://h", "switch": "aa"}
    assert "api_key" not in body  # secret never in the profile file
    assert credential_store.get_api_key("default") == "newkey"


def test_create_reuses_existing_credential(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    credential_store.set_credential("default", "existing")
    monkeypatch.setattr(_editor, "edit_toml", lambda initial, validate: 'base_url = "https://h"\n')
    called = []
    monkeypatch.setattr(profile, "_prompt_key", lambda: called.append(True) or "x")
    profile.create("home")
    assert called == []  # did not prompt; reused existing credential
    assert credential_store.get_api_key("default") == "existing"


def test_create_aborts_when_editor_returns_none(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(_editor, "edit_toml", lambda initial, validate: None)
    profile.create("home")
    assert not profile_store.profile_exists("home")
    assert "aborted" in capsys.readouterr().out


def test_edit_validates_and_writes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _profile(tmp_path, "home", 'base_url = "https://old"\n')
    monkeypatch.setattr(_editor, "edit_toml", lambda initial, validate: 'base_url = "https://new"\n')
    profile.edit("home")
    assert profile_store.read_profile("home")["base_url"] == "https://new"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cmd_profile.py -k "create or edit" -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'create'`.

- [ ] **Step 3: Implement**

Add these imports at the top of `src/unifictl/commands/profile.py`: `import tomllib`, `import tomlkit`, `import questionary`, and `from unifictl.commands import _editor`. Then add:

```python
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
    profile = profile_store.read_profile(name)
    credential = str(profile.get("credential") or "default")
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cmd_profile.py -v`
Expected: PASS. Then a manual smoke with a real editor: `EDITOR=nano uv run unifictl profile create demo` (write a base_url, save; enter a key at the prompt), then `uv run unifictl profile describe demo`.

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/commands/profile.py tests/test_cmd_profile.py
git commit -m "feat: add profile create and edit commands"
```

---

## Task 7: profile set / unset / activate / delete

**Files:**
- Modify: `src/unifictl/commands/profile.py`
- Test: `tests/test_cmd_profile.py`

**Interfaces:**
- Consumes: `profile_store.{read_profile_doc,write_profile_doc,profile_exists,set_default_profile,delete_profile,PROFILE_KEYS}`, `questionary`.
- Produces: `set_(name, key, value, /)`, `unset(name, key, /)`, `activate(name, /)`, `delete(name, /, *, yes=False)`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cmd_profile.py`:

```python
def test_set_and_unset_preserve_comments(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _profile(tmp_path, "home", '# note\nbase_url = "https://h"\n')
    profile.set_("home", "switch", "aa:bb")
    text = profile_store.profile_path("home").read_text()
    assert "# note" in text and 'switch = "aa:bb"' in text
    profile.unset("home", "switch")
    assert "switch" not in profile_store.read_profile("home")


def test_set_rejects_api_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _profile(tmp_path, "home", 'base_url = "https://h"\n')
    with pytest.raises(ConfigError, match="credential set"):
        profile.set_("home", "api_key", "leak")


def test_set_rejects_unknown_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _profile(tmp_path, "home", 'base_url = "https://h"\n')
    with pytest.raises(ConfigError, match="unknown key"):
        profile.set_("home", "nope", "x")


def test_activate_writes_default(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _profile(tmp_path, "home", 'base_url = "https://h"\n')
    profile.activate("home")
    assert profile_store.default_profile_name() == "home"


def test_activate_unknown_raises(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(ConfigError, match="unknown profile 'ghost'"):
        profile.activate("ghost")


def test_delete_with_yes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _profile(tmp_path, "home", 'base_url = "https://h"\n')
    profile.delete("home", yes=True)
    assert not profile_store.profile_exists("home")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cmd_profile.py -k "set or unset or activate or delete" -v`
Expected: FAIL — attributes `set_`/`unset`/`activate`/`delete` don't exist.

- [ ] **Step 3: Implement**

Add to `src/unifictl/commands/profile.py` (`import questionary` already added in Task 6):

```python
def _require_profile(name: str) -> None:
    if not profile_store.profile_exists(name):
        available = ", ".join(profile_store.list_profile_names()) or "(none)"
        raise ConfigError(f"unknown profile {name!r}; available: {available}")


@app.command(name="set")
def set_(name: str, key: str, value: str, /) -> None:
    """Set a non-secret field on a profile (comments preserved).

    Raises:
        ConfigError: unknown profile, ``key == 'api_key'``, or an unknown key.
    """
    _require_profile(name)
    if key == "api_key":
        raise ConfigError("api_key is not a profile field; run: unifictl credential set")
    if key not in profile_store.PROFILE_KEYS:
        raise ConfigError(f"unknown key {key!r}; allowed: {', '.join(sorted(profile_store.PROFILE_KEYS))}")
    doc = profile_store.read_profile_doc(name)
    doc[key] = value
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cmd_profile.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/commands/profile.py tests/test_cmd_profile.py
git commit -m "feat: add profile set/unset/activate/delete commands"
```

---

## Task 8: Tab-completion for profile & credential trees

**Files:**
- Modify: `src/unifictl/commands/_complete.py:16-24`
- Test: `tests/test_complete.py`, `tests/test_cli.py`

**Interfaces:**
- Produces: `profile <TAB>` → `create/edit/set/unset/list/describe/activate/delete`; `credential <TAB>` → `set/list/delete`; `credential` at top level.

- [ ] **Step 1: Update the failing assertions**

In `tests/test_complete.py`, update the top-level set and the profile sub-commands, and add credential:

```python
def test_top_level_commands() -> None:
    assert set(run("unifictl", "")) == {"set", "list", "show", "completion", "profile", "credential"}


def test_profile_subcommands() -> None:
    assert set(run("unifictl", "profile", "")) == {
        "create", "edit", "set", "unset", "list", "describe", "activate", "delete",
    }


def test_credential_subcommands() -> None:
    assert set(run("unifictl", "credential", "")) == {"set", "list", "delete"}
```

In `tests/test_cli.py::test_main_complete_fast_path`, update the expected set to include `"profile"` and `"credential"`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_complete.py -k "top_level or profile_sub or credential" "tests/test_cli.py::test_main_complete_fast_path" -v`
Expected: FAIL — tables lack `credential` and the new profile sub-commands.

- [ ] **Step 3: Implement**

In `src/unifictl/commands/_complete.py`:

```python
_TOP_LEVEL_COMMANDS: frozenset[str] = frozenset(
    {"set", "list", "show", "completion", "profile", "credential"}
)

_SUB_APP_NAMES: dict[str, frozenset[str]] = {
    "set": frozenset({"lag"}),
    "list": frozenset({"devices"}),
    "show": frozenset({"port"}),
    "completion": frozenset({"bash", "fish", "zsh", "install"}),
    "profile": frozenset(
        {"create", "edit", "set", "unset", "list", "describe", "activate", "delete"}
    ),
    "credential": frozenset({"set", "list", "delete"}),
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_complete.py tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/commands/_complete.py tests/test_complete.py tests/test_cli.py
git commit -m "feat: complete the profile and credential command trees"
```

---

## Task 9: Docs & cleanup

**Files:**
- Modify: `README.md` (rewrite the Profiles section)
- Verify: no stale references to the retired v1 surface remain

**Interfaces:** none (docs).

- [ ] **Step 1: Rewrite the README Profiles section**

Replace the `### Profiles` subsection with content documenting the new model — the three files, `credential`/`[default]` binding, the resolution ladder, and the commands:

````markdown
### Profiles & credentials

Point `unifictl` at different targets with named profiles. Non-secret config lives
one-file-per-profile under `~/.config/unifictl/profiles/`; the API key lives in a
separate `~/.config/unifictl/credentials.toml` (`0600`, the only secret file):

```toml
# ~/.config/unifictl/profiles/home.toml   (safe to share)
base_url = "https://192.168.1.1"
switch   = "aa:bb:cc:dd:ee:ff"
# credential = "default"      # which credentials.toml section holds the key

# ~/.config/unifictl/credentials.toml      (chmod 600)
[default]
api_key = "…"
```

A profile's `credential` defaults to `default`, so one controller/key backs many
per-switch profiles with no duplication. Select a profile with `--profile NAME`,
`UNIFI_PROFILE`, or `profile activate NAME` (writes `default_profile`). Fields
resolve `CLI > env > profile > built-in`; the api_key resolves
`UNIFI_API_KEY > credentials[credential] > error`.

```sh
unifictl profile create home        # opens $EDITOR for the non-secret fields,
                                     # then prompts (hidden) for the API key
unifictl profile list
unifictl profile describe home       # fields + redacted key
unifictl profile set home switch aa:bb:cc:dd:ee:ff
unifictl profile activate home
unifictl credential set default      # rotate the shared key, once
unifictl credential list
```
````

Remove any lingering mention of `[profiles.<name>]` tables in `config.toml`, inline
`api_key`, or `profile example`/`show` (replaced by `create`/`describe`).

- [ ] **Step 2: Verify no stale v1 references**

Run: `rg -n "profiles\.\{?name|profile example|\[profiles\.|load_profiles|profile show" README.md src/ tests/`
Expected: no matches (other than incidental). Fix any that remain.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document the file-per-profile and credential model"
```

---

## Final verification

- [ ] `uv run pytest -q` — all green.
- [ ] `task dev:check` — lint/format/type/import-linter all clean, zero warnings.
- [ ] Manual smoke: `EDITOR=nano uv run unifictl profile create demo` → set base_url + switch, save, enter a key; `uv run unifictl --profile demo profile describe demo`; `uv run unifictl credential list`.
- [ ] Update PR #11's description to describe the final (file-per-profile + credential store) design.
