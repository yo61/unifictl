# Configuration Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `unifictl` be pointed at different target UniFi controllers/switches via named, optional configuration profiles in `~/.config/unifictl/config.toml`.

**Architecture:** A profile is a `[profiles.<name>]` TOML table holding the stable target identity (`base_url`, `api_key`, `site`, TLS, `switch`). `load_settings()` resolves each field `env > selected profile > top-level TOML default > built-in default`, selecting the profile from `UNIFI_PROFILE` or the TOML `default_profile`. A global `--profile` flag (a cyclopts `app.meta` launcher) just sets `UNIFI_PROFILE`, so the five existing commands are untouched. A read-only `profile` sub-app (`list`/`show`/`example`) aids discovery.

**Tech Stack:** Python 3.14, cyclopts (CLI), rich (output), `tomllib` (stdlib), `xdg-base-dirs`, pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-12-config-profiles-design.md`. Decision: `decisions/2026-07-12-config-profiles-inline-secrets.md`.
- TDD: write the failing test, watch it fail, implement, watch it pass, commit. One logical change per commit; imperative <=72-char subject.
- Field resolution ladder: `CLI flag > UNIFI_* env > selected profile > top-level TOML default > built-in default`.
- Profile selection: `--profile NAME > UNIFI_PROFILE env > default_profile in config > none`.
- Allowed profile keys: `base_url`, `api_key`, `site`, `ca_cert`, `insecure_tls`, `timeout_ms`, `switch`. Any other key inside a `[profiles.*]` table (including `leaders`) is **rejected** with a `ConfigError`.
- `leaders` is **not** a profile field — it stays `--leader` flag + top-level TOML default, unchanged.
- Zero profiles + no `default_profile` ⇒ `load_settings()` behaves exactly as today (backward compatible).
- Secrets stored inline; when the file holds an inline `api_key` and is group/world-readable, refuse with a `chmod 600` hint.
- `profile show` redacts `api_key`; `profile example` prints to stdout and never writes the file.
- Code style: absolute imports only, `from __future__ import annotations`, Google-style docstrings on public APIs, functions ≤100 lines / ≤5 positional params, 100-char lines. Run `ruff`/`ty` clean (prek runs them on commit).

**Every task's requirements implicitly include this section.**

---

## File Structure

- `src/unifictl/infrastructure/config.py` — MODIFY. Add `read_config()`, `load_profiles()`, profile selection, per-field resolution, and permission enforcement; rewrite `load_settings()`.
- `src/unifictl/commands/profile.py` — CREATE. The `profile` sub-app: `list`, `show`, `example`.
- `src/unifictl/cli.py` — MODIFY. Register the `profile` sub-app; add the `--profile` global flag via `app.meta`.
- `src/unifictl/commands/_complete.py` — MODIFY. Add `profile` and its sub-commands to the static completion tables.
- `tests/test_config.py` — MODIFY. Profile parsing, resolution ladder, selection, permissions.
- `tests/test_cmd_profile.py` — CREATE. The three `profile` commands.
- `tests/test_cli.py` — MODIFY. The `--profile` flag sets `UNIFI_PROFILE`; update the `__complete` top-level assertion.
- `tests/test_complete.py` — MODIFY. Update the top-level command set; add `profile` sub-command completion.
- `README.md` — MODIFY. Document profiles.

**Verified during planning:** cyclopts 4.11.2 exposes `App.meta`/`@app.meta.default`; a meta launcher forwarding `*tokens` to `app(tokens)` preserves `--help`/`--version` (exit 0), runs sub-commands, and lets a command-raised `ConfigError` propagate unchanged (so `test_main_maps_config_error_to_exit_1` still holds). The `__complete` fast-path is a hardcoded static table, independent of the real app — new commands must be added there explicitly to tab-complete.

---

## Task 1: Parse and validate `[profiles.*]` tables

**Files:**
- Modify: `src/unifictl/infrastructure/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `read_config() -> dict[str, object]` (parsed `config.toml`, `{}` if absent). `load_profiles(data: dict[str, object]) -> dict[str, dict[str, object]]` (name → validated table; rejects non-table `profiles`, non-table profile, and unknown keys). Module constant `_PROFILE_KEYS: frozenset[str]`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
from unifictl.infrastructure.config import load_profiles, read_config


def test_load_profiles_empty_when_absent() -> None:
    assert load_profiles({}) == {}


def test_load_profiles_returns_named_tables() -> None:
    data = {"profiles": {"home": {"base_url": "https://gw", "switch": "aa:bb"}}}
    assert load_profiles(data) == {"home": {"base_url": "https://gw", "switch": "aa:bb"}}


def test_load_profiles_rejects_unknown_key() -> None:
    data = {"profiles": {"home": {"leaders": [1, 3]}}}
    with pytest.raises(ConfigError, match="home.*leaders"):
        load_profiles(data)


def test_load_profiles_rejects_non_table_profile() -> None:
    with pytest.raises(ConfigError, match="home.*table"):
        load_profiles({"profiles": {"home": "nope"}})


def test_read_config_absent_returns_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert read_config() == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -k "load_profiles or read_config" -v`
Expected: FAIL with `ImportError` / `cannot import name 'load_profiles'`.

- [ ] **Step 3: Implement**

In `src/unifictl/infrastructure/config.py`, after `_load_toml`, add:

```python
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
        profiles[name] = dict(table)
    return profiles
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -k "load_profiles or read_config" -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/infrastructure/config.py tests/test_config.py
git commit -m "feat: parse and validate config profile tables"
```

---

## Task 2: Resolve settings from the selected profile

**Files:**
- Modify: `src/unifictl/infrastructure/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: `load_profiles`, `read_config`, `_PROFILE_KEYS` (Task 1); existing `Settings`, `_load_toml`, `config_file_path`, `_optional_path`, `_toml_str`, `_toml_leaders`, `DEFAULT_TIMEOUT_MS`.
- Produces: rewritten `load_settings() -> Settings` resolving `env > profile > top-level > default`; helpers `_select_profile`, `_profile_str`, `_resolve_bool`, `_resolve_int`, `_missing`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py` (`_base_env` and `_write_config` helpers; reuse the existing `_base_env`):

```python
def _write_config(tmp_path, body: str) -> None:
    cfg = tmp_path / "unifictl"
    cfg.mkdir(exist_ok=True)
    (cfg / "config.toml").write_text(body, encoding="utf-8")


def test_profile_supplies_connection(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for var in ("UNIFI_BASE_URL", "UNIFI_API_KEY", "UNIFI_SITE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    _write_config(
        tmp_path,
        '[profiles.home]\n'
        'base_url = "https://home"\napi_key = "hk"\nsite = "s1"\nswitch = "aa:bb"\n',
    )
    settings = load_settings()
    assert (settings.base_url, settings.api_key, settings.site, settings.switch) == (
        "https://home",
        "hk",
        "s1",
        "aa:bb",
    )


def test_env_overrides_profile(monkeypatch, tmp_path) -> None:
    _base_env(monkeypatch, tmp_path)  # sets UNIFI_BASE_URL=https://gw, UNIFI_API_KEY=secret
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    _write_config(tmp_path, '[profiles.home]\nbase_url = "https://home"\napi_key = "hk"\n')
    settings = load_settings()
    assert settings.base_url == "https://gw"  # env wins over profile
    assert settings.api_key == "secret"


def test_default_profile_used_when_unifi_profile_absent(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for var in ("UNIFI_BASE_URL", "UNIFI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("UNIFI_PROFILE", raising=False)
    _write_config(
        tmp_path,
        'default_profile = "home"\n[profiles.home]\nbase_url = "https://home"\napi_key = "hk"\n',
    )
    assert load_settings().base_url == "https://home"


def test_unknown_profile_raises(monkeypatch, tmp_path) -> None:
    _base_env(monkeypatch, tmp_path)
    monkeypatch.setenv("UNIFI_PROFILE", "ghost")
    _write_config(tmp_path, '[profiles.home]\nbase_url = "https://home"\napi_key = "hk"\n')
    with pytest.raises(ConfigError, match="unknown profile 'ghost'.*home"):
        load_settings()


def test_missing_secret_names_profile(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("UNIFI_API_KEY", raising=False)
    monkeypatch.setenv("UNIFI_BASE_URL", "https://gw")
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    _write_config(tmp_path, '[profiles.home]\nbase_url = "https://home"\n')
    with pytest.raises(ConfigError, match="UNIFI_API_KEY.*home.*api_key"):
        load_settings()


def test_profile_switch_type_error_names_profile(monkeypatch, tmp_path) -> None:
    _base_env(monkeypatch, tmp_path)
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    _write_config(tmp_path, '[profiles.home]\nswitch = 42\n')
    with pytest.raises(ConfigError, match="home.*switch.*string"):
        load_settings()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -k "profile or default_profile or missing_secret" -v`
Expected: FAIL (profile not consulted; `UNIFI_PROFILE` ignored).

- [ ] **Step 3: Implement**

In `src/unifictl/infrastructure/config.py`, replace the body of `load_settings` and add the helpers. New `load_settings`:

```python
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
```

Add these helpers (and delete the now-unused `_env_bool` and `_env_int`):

```python
def _select_profile(
    profiles: dict[str, dict[str, object]], data: dict[str, object]
) -> tuple[str | None, dict[str, object]]:
    name = os.environ.get("UNIFI_PROFILE") or _toml_str(data, "default_profile")
    if name is None:
        return None, {}
    if name not in profiles:
        available = ", ".join(sorted(profiles)) or "(none)"
        raise ConfigError(f"unknown profile {name!r}; available: {available}")
    return name, profiles[name]


def _missing(env_name: str, key: str, name: str | None) -> str:
    if name is None:
        return f"{env_name} is not set"
    return f"{env_name} is not set and profile {name!r} does not define {key!r}"


def _profile_str(profile: dict[str, object], key: str, name: str | None) -> str | None:
    value = profile.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(
            f"config.toml: profile {name!r} key {key!r} must be a string, got {value!r}"
        )
    return value


def _resolve_bool(env_name: str, profile: dict[str, object], key: str, name: str | None) -> bool:
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
```

Note: `_enforce_secret_permissions` is added in Task 3. For this task, add a temporary no-op so the module imports cleanly:

```python
def _enforce_secret_permissions(path: Path, profiles: dict[str, dict[str, object]]) -> None:
    """Placeholder; real check added in the permissions task."""
    return
```

- [ ] **Step 4: Run the full config test module**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS — the new tests **and** all pre-existing tests (backward compatibility).

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/infrastructure/config.py tests/test_config.py
git commit -m "feat: resolve settings from the selected profile"
```

---

## Task 3: Enforce 0600 when a profile holds an inline secret

**Files:**
- Modify: `src/unifictl/infrastructure/config.py:_enforce_secret_permissions`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: `load_settings`, `_write_config`, `_base_env` (Task 2).
- Produces: real `_enforce_secret_permissions(path, profiles)` — raises `ConfigError` when the file is group/world-readable and any profile has an inline `api_key`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
import os as _os


def test_world_readable_secret_refused(monkeypatch, tmp_path) -> None:
    _base_env(monkeypatch, tmp_path)
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    _write_config(tmp_path, '[profiles.home]\nbase_url = "https://home"\napi_key = "hk"\n')
    _os.chmod(tmp_path / "unifictl" / "config.toml", 0o644)
    with pytest.raises(ConfigError, match="chmod 600"):
        load_settings()


def test_world_readable_without_secret_is_allowed(monkeypatch, tmp_path) -> None:
    _base_env(monkeypatch, tmp_path)  # secrets come from env, not the file
    _write_config(tmp_path, 'switch = "aa:bb"\n[profiles.home]\nbase_url = "https://home"\n')
    _os.chmod(tmp_path / "unifictl" / "config.toml", 0o644)
    assert load_settings().switch == "aa:bb"  # no refusal


def test_secret_with_0600_is_allowed(monkeypatch, tmp_path) -> None:
    _base_env(monkeypatch, tmp_path)
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    _write_config(tmp_path, '[profiles.home]\nbase_url = "https://home"\napi_key = "hk"\n')
    _os.chmod(tmp_path / "unifictl" / "config.toml", 0o600)
    assert load_settings().api_key == "secret"  # env still wins; no refusal
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -k "readable or 0600" -v`
Expected: `test_world_readable_secret_refused` FAILS (no refusal yet); the other two PASS.

- [ ] **Step 3: Implement**

Replace the placeholder `_enforce_secret_permissions`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/infrastructure/config.py tests/test_config.py
git commit -m "feat: refuse world-readable config holding an inline secret"
```

---

## Task 4: Global `--profile` flag

**Files:**
- Modify: `src/unifictl/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: existing `get_app`, `app`, `main`.
- Produces: module-level `_apply_profile(profile: str | None) -> None` (sets `os.environ["UNIFI_PROFILE"]` when given); an `app.meta` launcher exposing `--profile`; `app()` now dispatches through `get_app().meta(...)`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
import os

import pytest

from unifictl.cli import _apply_profile, get_app


def test_apply_profile_sets_env(monkeypatch) -> None:
    monkeypatch.delenv("UNIFI_PROFILE", raising=False)
    _apply_profile("lab")
    assert os.environ["UNIFI_PROFILE"] == "lab"


def test_apply_profile_none_leaves_env(monkeypatch) -> None:
    monkeypatch.setenv("UNIFI_PROFILE", "keep")
    _apply_profile(None)
    assert os.environ["UNIFI_PROFILE"] == "keep"


def test_profile_flag_selects_before_dispatch(
    monkeypatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # NB: do NOT use `--help`/`--version` here — cyclopts intercepts those before
    # the meta launcher runs, so they bypass _apply_profile. Use a real, no-network
    # command (`completion zsh` just prints a script) so the launcher actually runs.
    monkeypatch.delenv("UNIFI_PROFILE", raising=False)
    with pytest.raises(SystemExit):
        get_app().meta(["--profile", "lab", "completion", "zsh"])
    assert os.environ["UNIFI_PROFILE"] == "lab"
    capsys.readouterr()  # swallow the emitted completion script
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -k "profile" -v`
Expected: FAIL with `cannot import name '_apply_profile'`.

Note: `--profile X --help` does NOT set the profile (cyclopts short-circuits help
before the launcher). That is fine — with `--help` the user wants help, not a
target. Real invocations (`--profile X <command>`) run the launcher and set it.

- [ ] **Step 3: Implement**

In `src/unifictl/cli.py`, add `import os` and `from typing import Annotated`; import `Parameter` from cyclopts (`from cyclopts import App, Parameter`). Add the helper at module scope:

```python
def _apply_profile(profile: str | None) -> None:
    """Set ``UNIFI_PROFILE`` from the ``--profile`` flag (flag beats env)."""
    if profile is not None:
        os.environ["UNIFI_PROFILE"] = profile
```

At the end of `get_app`, before `return app`, register the meta launcher:

```python
    @app.meta.default
    def _launcher(
        *tokens: Annotated[str, Parameter(show=False, allow_leading_hyphen=True)],
        profile: Annotated[
            str | None, Parameter(help="Configuration profile to use (sets UNIFI_PROFILE).")
        ] = None,
    ) -> None:
        _apply_profile(profile)
        app(tokens)
```

Change the `app` dispatch function to route through the meta app:

```python
def app(*args: Any, **kwargs: Any) -> Any:
    """Invoke the CLI through the meta launcher so ``--profile`` is global."""
    return get_app().meta(*args, **kwargs)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS. Then confirm help/version still work: `uv run unifictl --help` and `uv run unifictl --version` (both exit 0 and print as before).

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/cli.py tests/test_cli.py
git commit -m "feat: add global --profile flag"
```

---

## Task 5: `profile list` command

**Files:**
- Create: `src/unifictl/commands/profile.py`
- Modify: `src/unifictl/cli.py`
- Test: `tests/test_cmd_profile.py`

**Interfaces:**
- Consumes: `read_config`, `load_profiles` (Task 1); `config_file_path`, `ConfigError`.
- Produces: `profile.app` (cyclopts sub-app) with `list_()` bound to command name `list`, registered in `cli.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cmd_profile.py`:

```python
"""`unifictl profile` list/show/example behavior."""

from __future__ import annotations

import pytest

from unifictl.commands import profile


def _write_config(tmp_path, body: str) -> None:
    cfg = tmp_path / "unifictl"
    cfg.mkdir(exist_ok=True)
    (cfg / "config.toml").write_text(body, encoding="utf-8")


def test_list_shows_names_and_default(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_config(
        tmp_path,
        'default_profile = "home"\n'
        '[profiles.home]\nbase_url = "https://home"\n'
        '[profiles.lab]\nbase_url = "https://lab"\n',
    )
    profile.list_()
    out = capsys.readouterr().out
    assert "home (default): https://home" in out
    assert "lab: https://lab" in out


def test_list_empty(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profile.list_()
    assert "no profiles defined" in capsys.readouterr().out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cmd_profile.py -v`
Expected: FAIL with `ModuleNotFoundError: unifictl.commands.profile`.

- [ ] **Step 3: Implement**

Create `src/unifictl/commands/profile.py`:

```python
"""``unifictl profile`` sub-app: inspect and scaffold connection profiles."""

from __future__ import annotations

from cyclopts import App
from rich.console import Console

from unifictl.infrastructure.config import (
    ConfigError,
    config_file_path,
    load_profiles,
    read_config,
)

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
```

In `src/unifictl/cli.py`, inside `get_app`, import and register the sub-app alongside the others:

```python
    from unifictl.commands.profile import app as profile_app
    ...
    app.command(profile_app)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cmd_profile.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/commands/profile.py src/unifictl/cli.py tests/test_cmd_profile.py
git commit -m "feat: add profile list command"
```

---

## Task 6: `profile show NAME` command

**Files:**
- Modify: `src/unifictl/commands/profile.py`
- Test: `tests/test_cmd_profile.py`

**Interfaces:**
- Consumes: `profile.app`, `read_config`, `load_profiles`, `ConfigError`.
- Produces: `show(name: str, /)` bound to command name `show`; `_redact(value: str) -> str`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cmd_profile.py`:

```python
def test_show_redacts_api_key(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_config(
        tmp_path,
        '[profiles.home]\nbase_url = "https://home"\napi_key = "supersecret"\n',
    )
    profile.show("home")
    out = capsys.readouterr().out
    assert "supersecret" not in out
    assert "cret" in out  # last-4 shown
    assert "https://home" in out


def test_show_unknown_name_raises(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_config(tmp_path, '[profiles.home]\nbase_url = "https://home"\n')
    with pytest.raises(ConfigError, match="unknown profile 'ghost'.*home"):
        profile.show("ghost")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cmd_profile.py -k show -v`
Expected: FAIL with `AttributeError: module ... has no attribute 'show'`.

- [ ] **Step 3: Implement**

Add to `src/unifictl/commands/profile.py`:

```python
_SHOW_ORDER = ("base_url", "api_key", "site", "switch", "ca_cert", "insecure_tls", "timeout_ms")


@app.command(name="show")
def show(name: str, /) -> None:
    """Show a profile's fields, redacting ``api_key``.

    Args:
        name: The profile to display.

    Raises:
        ConfigError: if ``name`` is not a defined profile.
    """
    data = read_config()
    profiles = load_profiles(data)
    if name not in profiles:
        available = ", ".join(sorted(profiles)) or "(none)"
        raise ConfigError(f"unknown profile {name!r}; available: {available}")
    table = profiles[name]
    for key in _SHOW_ORDER:
        if key not in table:
            continue
        value = table[key]
        if key == "api_key" and isinstance(value, str):
            value = _redact(value)
        _console.print(f"{key} = {value!r}")


def _redact(value: str) -> str:
    return f"…{value[-4:]}" if len(value) > 4 else "****"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cmd_profile.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/commands/profile.py tests/test_cmd_profile.py
git commit -m "feat: add profile show command"
```

---

## Task 7: `profile example [NAME]` command

**Files:**
- Modify: `src/unifictl/commands/profile.py`
- Test: `tests/test_cmd_profile.py`

**Interfaces:**
- Consumes: `profile.app`, `config_file_path`.
- Produces: `example(name: str = "example", /)` bound to command name `example`; prints a commented `[profiles.<name>]` block to stdout.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cmd_profile.py`:

```python
import tomllib


def test_example_prints_valid_toml_block(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profile.example("home")
    out = capsys.readouterr().out
    assert "[profiles.home]" in out
    assert "chmod 600" in out
    parsed = tomllib.loads(out)  # the emitted block must round-trip
    assert set(parsed["profiles"]["home"]) <= {
        "base_url",
        "api_key",
        "site",
        "switch",
    }  # only uncommented keys parse; commented ones are absent


def test_example_defaults_name(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profile.example()
    assert "[profiles.example]" in capsys.readouterr().out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cmd_profile.py -k example -v`
Expected: FAIL with `AttributeError: ... has no attribute 'example'`.

- [ ] **Step 3: Implement**

Add to `src/unifictl/commands/profile.py`:

```python
_EXAMPLE = """\
# Append to {path}, then run: chmod 600 {path}
[profiles.{name}]
base_url = "https://192.168.1.1"   # controller URL
api_key  = "REPLACE_ME"            # Integration API key
site     = "default"               # controller site
switch   = "aa:bb:cc:dd:ee:ff"     # MAC of the switch to operate on
# ca_cert      = "/path/to/controller-ca.pem"
# insecure_tls = false
# timeout_ms   = 30000
"""


@app.command(name="example")
def example(name: str = "example", /) -> None:
    """Print a commented profile block to stdout (does not write the file).

    Args:
        name: The profile name to scaffold. Defaults to ``example``.
    """
    print(_EXAMPLE.format(name=name, path=config_file_path()))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cmd_profile.py -v`
Expected: PASS. Then eyeball it: `uv run unifictl profile example home`.

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/commands/profile.py tests/test_cmd_profile.py
git commit -m "feat: add profile example command"
```

---

## Task 8: Tab-completion for the `profile` command tree

**Files:**
- Modify: `src/unifictl/commands/_complete.py:16-24`
- Test: `tests/test_complete.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: the static completion tables `_TOP_LEVEL_COMMANDS`, `_SUB_APP_NAMES`.
- Produces: `profile` completes at top level; `profile <TAB>` → `list`/`show`/`example`.

Scope note: this wires the **command names** only. Completing a profile *name* value
for `profile show <TAB>` / `profile example <TAB>` is deliberately out of scope for v1
(it would add a config-reading candidate source); left as a future enhancement.

- [ ] **Step 1: Update the completion assertions (failing)**

In `tests/test_complete.py`, change the top-level assertion (line ~22) and add a
profile sub-command test:

```python
def test_top_level_commands() -> None:
    assert set(run("unifictl", "")) == {"set", "list", "show", "completion", "profile"}


def test_profile_subcommands() -> None:
    assert set(run("unifictl", "profile", "")) == {"list", "show", "example"}
```

In `tests/test_cli.py`, update `test_main_complete_fast_path` (line ~54):

```python
    assert set(capsys.readouterr().out.split()) == {
        "set",
        "list",
        "show",
        "completion",
        "profile",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_complete.py::test_top_level_commands tests/test_complete.py::test_profile_subcommands "tests/test_cli.py::test_main_complete_fast_path" -v`
Expected: FAIL (sets lack `profile` / `profile` sub-commands unknown).

- [ ] **Step 3: Implement**

In `src/unifictl/commands/_complete.py`:

```python
_TOP_LEVEL_COMMANDS: frozenset[str] = frozenset(
    {"set", "list", "show", "completion", "profile"}
)

_SUB_APP_NAMES: dict[str, frozenset[str]] = {
    "set": frozenset({"lag"}),
    "list": frozenset({"devices"}),
    "show": frozenset({"port"}),
    "completion": frozenset({"bash", "fish", "zsh", "install"}),
    "profile": frozenset({"list", "show", "example"}),
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_complete.py tests/test_cli.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/commands/_complete.py tests/test_complete.py tests/test_cli.py
git commit -m "feat: complete the profile command tree"
```

---

## Task 9: Document profiles

**Files:**
- Modify: `README.md:52-67` (the Configuration section)

**Interfaces:** none (docs only).

- [ ] **Step 1: Update the Configuration section**

Replace the paragraph at `README.md:66-67` ("Operational parameters … CLI flags override them.") with:

````markdown
Operational parameters (switch MAC and LAG leader ports) live in an XDG TOML file
at `~/.config/unifictl/config.toml`; CLI flags override them.

### Profiles

To point `unifictl` at different targets, define named profiles in the same file.
A profile holds the connection identity — `base_url`, `api_key`, `site`, TLS
settings, and the `switch` to operate on:

```toml
default_profile = "home"           # optional; used when --profile is omitted

[profiles.home]
base_url = "https://192.168.1.1"
api_key  = "…"
switch   = "aa:bb:cc:dd:ee:ff"

[profiles.lab]
base_url = "https://10.0.0.1"
api_key  = "…"
```

Select a profile with `--profile NAME` (global flag), the `UNIFI_PROFILE`
environment variable, or `default_profile`. Each field resolves
`CLI flag > env var > profile > built-in default`, so an explicit `--switch` or
`UNIFI_*` still overrides the profile. `leaders` is not a profile field — it stays
a `--leader` flag with the top-level `leaders` default, because LAG membership
changes over time.

Because a profile stores an API key, `config.toml` must be `chmod 600` when it
holds one; `unifictl` refuses a group/world-readable file in that case. Scaffold a
block with:

```sh
unifictl profile example home >> ~/.config/unifictl/config.toml && chmod 600 ~/.config/unifictl/config.toml
unifictl profile list          # names + default + base_url
unifictl profile show home     # fields, api_key redacted
```
````

- [ ] **Step 2: Verify the docs render and match behavior**

Run: `uv run unifictl profile example home` and confirm the printed block matches the README example (same keys). Re-read the section for accuracy against the resolution ladder.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document configuration profiles"
```

---

## Final verification

- [ ] Run the whole suite and quality gate: `uv run pytest -q` then `task dev:check` (lint, format-check, typecheck, import boundaries, tests). Expected: all green, zero warnings.
- [ ] Manual smoke: with a `~/.config/unifictl/config.toml` holding a `[profiles.home]` (chmod 600), run `unifictl --profile home profile show home` and `unifictl profile list`.
```
