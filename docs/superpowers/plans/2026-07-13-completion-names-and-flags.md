# Completion of Names and Option Flags — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `unifictl` shell completion offer profile/credential names, profile keys, and option flags — e.g. `unifictl profile delete <TAB>` lists profiles and `unifictl set lag -<TAB>` lists that command's flags.

**Architecture:** All logic lives in `src/unifictl/commands/_complete.py`, the hidden `__complete` handler. It mirrors the command tree as static data (so the completion fast-path never imports `cyclopts`/`rich`/`questionary`) and calls small dynamic providers for live data (profile/credential names). A new test builds the real cyclopts app and asserts the static tables match it, so the hand-mirrored data cannot silently drift. The per-shell scripts already forward every token and do prefix filtering — they are not touched.

**Tech Stack:** Python 3.14, cyclopts, pytest. Package manager `uv`; lint `ruff`, types `ty`.

## Global Constraints

- The `__complete` fast-path must stay fast: `_complete.py` must NOT import command modules or `cyclopts`/`rich`/`questionary` at module scope. New providers import `profile_store`/`credential_store` **lazily inside the function body** (as `_completion_devices` already does with its local `from dataclasses import replace`).
- Every dynamic provider swallows all exceptions and degrades to `[]` — a TAB press must never hang or raise (same discipline as `_completion_devices`).
- Flag completion offers **primary long forms only**: `--` + param name with `_`→`-`, or the first `--`-prefixed name in a `Parameter(name=[…])` override. No negative boolean forms (`--no-yes`), no short aliases (`-d`), no `--help`/`--version`.
- `profile create` gets **no** name completion (it takes a new name).
- Line length ≤100 chars. Absolute imports only.
- Run all completion tests with: `.venv/bin/pytest tests/test_complete.py -q` (and the new drift test file where noted). Full check before final commit: `.venv/bin/ruff check src tests && .venv/bin/ty check && .venv/bin/pytest -q`.

---

### Task 1: Flag-name completion

Add a static per-command flag map and make `run()` emit it when the partial word starts with `-`.

**Files:**
- Modify: `src/unifictl/commands/_complete.py`
- Test: `tests/test_complete.py`

**Interfaces:**
- Produces: module-level `_FLAG_NAMES: dict[tuple[str, ...], tuple[str, ...]]`, keyed by command path (`()` = global). Consumed only within `_complete.py`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_complete.py`:

```python
def test_set_lag_flag_names(run) -> None:
    assert run("unifictl", "set", "lag", "-") == [
        "--switch",
        "--leader",
        "--dry-run",
        "--yes",
    ]


def test_list_devices_flag_names(run) -> None:
    assert run("unifictl", "list", "devices", "-") == ["--json"]


def test_global_profile_flag_name(run) -> None:
    assert run("unifictl", "-") == ["--profile"]


def test_command_without_flags_yields_no_flag_names(run) -> None:
    # `set` is a group with no flags of its own.
    assert run("unifictl", "set", "-") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_complete.py -q -k "flag_name"`
Expected: FAIL (the four tests return `[]` or unrelated output because `run()` does not yet special-case `-`).

- [ ] **Step 3: Add the `_FLAG_NAMES` map**

In `src/unifictl/commands/_complete.py`, after the `_PORT_IDX_FLAGS` definition (around line 75), add:

```python
# cmd_path -> primary long-form flag names, in signature order. `()` is global.
# Guarded against drift by tests/test_completion_tree_drift.py.
_FLAG_NAMES: dict[tuple[str, ...], tuple[str, ...]] = {
    (): ("--profile",),
    ("set", "lag"): ("--switch", "--leader", "--dry-run", "--yes"),
    ("show", "port"): ("--switch", "--json"),
    ("list", "devices"): ("--json",),
    ("completion", "install"): ("--shell", "--dest"),
    ("profile", "delete"): ("--yes",),
    ("credential", "set"): ("--stdin",),
    ("credential", "delete"): ("--yes",),
}
```

- [ ] **Step 4: Emit flag names when the partial starts with `-`**

In `run()`, immediately after the `cmd_path, leftover = _walk_static(completed)` line and before `in_positionals = leftover`, insert:

```python
    partial = word_list[-1] if len(word_list) > 1 else ""
    if partial.startswith("-"):
        for flag in _FLAG_NAMES.get(cmd_path, ()):
            print(flag)
        return

```

This runs before all positional/value logic, so it takes precedence. It is safe because no value we complete (MAC, port index, name, key) begins with `-`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_complete.py -q`
Expected: PASS (new flag-name tests plus all pre-existing tests).

- [ ] **Step 6: Commit**

```bash
git add src/unifictl/commands/_complete.py tests/test_complete.py
git commit -m "feat(completion): complete option flag names"
```

---

### Task 2: Profile & credential name completion

Complete existing profile/credential names at the name positional, and as the value of the global `--profile` flag.

**Files:**
- Modify: `src/unifictl/commands/_complete.py`
- Test: `tests/test_complete.py`

**Interfaces:**
- Consumes: `_positional_index` (existing), `_FLAG_NAMES` / `partial` handling from Task 1.
- Produces:
  - `_profile_names() -> list[str]`
  - `_credential_names() -> list[str]`
  - `_PROFILE_NAME_COMMANDS: frozenset[tuple[str, ...]]` (name at positional 0)
  - `_CREDENTIAL_NAME_COMMANDS: frozenset[tuple[str, ...]]` (name at positional 0)
  - `_PROFILE_NAME_FLAGS: frozenset[tuple[tuple[str, ...], str]]` (flag whose value is a profile name)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_complete.py`:

```python
@pytest.fixture()
def fake_profiles(monkeypatch: pytest.MonkeyPatch):
    def _install(names: list[str]) -> None:
        monkeypatch.setattr(_complete, "_profile_names", lambda: list(names))

    return _install


@pytest.fixture()
def fake_credentials(monkeypatch: pytest.MonkeyPatch):
    def _install(names: list[str]) -> None:
        monkeypatch.setattr(_complete, "_credential_names", lambda: list(names))

    return _install


def test_profile_delete_completes_profile_names(run, fake_profiles) -> None:
    fake_profiles(["home", "work"])
    assert run("unifictl", "profile", "delete", "") == ["home", "work"]


def test_profile_describe_completes_profile_names(run, fake_profiles) -> None:
    fake_profiles(["home", "work"])
    assert run("unifictl", "profile", "describe", "") == ["home", "work"]


def test_credential_delete_completes_credential_names(run, fake_credentials) -> None:
    fake_credentials(["default", "lab"])
    assert run("unifictl", "credential", "delete", "") == ["default", "lab"]


def test_credential_set_completes_existing_credential_names(run, fake_credentials) -> None:
    fake_credentials(["default", "lab"])
    assert run("unifictl", "credential", "set", "") == ["default", "lab"]


def test_global_profile_flag_completes_names(run, fake_profiles) -> None:
    fake_profiles(["home", "work"])
    assert run("unifictl", "--profile", "") == ["home", "work"]


def test_profile_names_swallows_store_errors(monkeypatch) -> None:
    # The provider imports profile_store lazily; patch the real call site.
    import unifictl.infrastructure.profile_store as ps

    def _boom() -> list[str]:
        raise RuntimeError("store unreadable")

    monkeypatch.setattr(ps, "list_profile_names", _boom)
    assert _complete._profile_names() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_complete.py -q -k "profile or credential"`
Expected: FAIL (`_profile_names`/`_credential_names` do not exist yet; name completion is not wired).

- [ ] **Step 3: Add the providers and static maps**

In `src/unifictl/commands/_complete.py`, add the providers next to `_completion_devices` (with lazy imports inside):

```python
def _profile_names() -> list[str]:
    """Defined profile names, or ``[]`` on any problem (TAB must never fail)."""
    try:
        from unifictl.infrastructure import profile_store

        return profile_store.list_profile_names()
    except Exception:
        return []


def _credential_names() -> list[str]:
    """Defined credential names, or ``[]`` on any problem (TAB must never fail)."""
    try:
        from unifictl.infrastructure import credential_store

        return credential_store.list_credential_names()
    except Exception:
        return []
```

Add the static maps after `_PORT_IDX_FLAGS` (near `_FLAG_NAMES`):

```python
# Commands whose positional 0 is an existing profile name (`create` is excluded:
# it takes a NEW name).
_PROFILE_NAME_COMMANDS: frozenset[tuple[str, ...]] = frozenset(
    {
        ("profile", "describe"),
        ("profile", "edit"),
        ("profile", "set"),
        ("profile", "unset"),
        ("profile", "activate"),
        ("profile", "delete"),
    }
)

# Commands whose positional 0 is an existing credential name.
_CREDENTIAL_NAME_COMMANDS: frozenset[tuple[str, ...]] = frozenset(
    {("credential", "set"), ("credential", "delete")}
)

# (cmd_path, flag) pairs whose value is a profile name (the global --profile).
_PROFILE_NAME_FLAGS: frozenset[tuple[tuple[str, ...], str]] = frozenset(
    {((), "--profile")}
)
```

- [ ] **Step 4: Teach `--profile` to the value-flag machinery**

Add `--profile` to `_VALUE_FLAGS` so positional counting skips its value:

```python
_VALUE_FLAGS: frozenset[str] = frozenset(
    {"--switch", "--leader", "--shell", "--dest", "-d", "--profile"}
)
```

In `run()`, inside the existing `if prev.startswith("-"):` block (alongside `_SWITCH_MAC_FLAGS` / `_PORT_IDX_FLAGS`), add:

```python
            if (cmd_path, prev) in _PROFILE_NAME_FLAGS:
                for name in _profile_names():
                    print(name)
                return
```

- [ ] **Step 5: Wire name completion at positional 0**

In `run()`, after the existing `_POSITIONAL_FIXED_VALUES` block and before the `port_position = ...` block, add:

```python
    if _positional_index(in_positionals) == 0:
        if cmd_path in _PROFILE_NAME_COMMANDS:
            for name in _profile_names():
                print(name)
            return
        if cmd_path in _CREDENTIAL_NAME_COMMANDS:
            for name in _credential_names():
                print(name)
            return
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_complete.py -q`
Expected: PASS (all name tests plus every pre-existing test).

- [ ] **Step 7: Commit**

```bash
git add src/unifictl/commands/_complete.py tests/test_complete.py
git commit -m "feat(completion): complete profile and credential names"
```

---

### Task 3: Profile key completion

Complete the key positional: `profile set <name> <TAB>` → all valid keys; `profile unset <name> <TAB>` → only the keys that profile actually has.

**Files:**
- Modify: `src/unifictl/commands/_complete.py`
- Test: `tests/test_complete.py`

**Interfaces:**
- Consumes: `_VALUE_FLAGS`, `_positional_index` (existing).
- Produces:
  - `_nth_positional(tokens: list[str], index: int) -> str | None` — the value of the Nth positional argument in `tokens`, skipping flags and their values.
  - `_profile_existing_keys(name: str) -> list[str]` — keys present in profile `name`'s document, or `[]` on any problem.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_complete.py`:

```python
def test_profile_set_completes_all_keys(run) -> None:
    from unifictl.infrastructure.profile_store import PROFILE_KEYS

    assert run("unifictl", "profile", "set", "home", "") == sorted(PROFILE_KEYS)


def test_profile_unset_completes_existing_keys(run, monkeypatch) -> None:
    monkeypatch.setattr(
        _complete, "_profile_existing_keys", lambda name: ["switch", "site"]
    )
    assert run("unifictl", "profile", "unset", "home", "") == ["switch", "site"]


def test_nth_positional_skips_flags_and_values() -> None:
    assert _complete._nth_positional(["home"], 0) == "home"
    assert _complete._nth_positional(["--switch", "aa:bb", "home"], 0) == "home"
    assert _complete._nth_positional(["home", "switch"], 1) == "switch"
    assert _complete._nth_positional(["home"], 1) is None


def test_profile_existing_keys_swallows_errors(monkeypatch) -> None:
    import unifictl.infrastructure.profile_store as ps

    def _boom(name: str) -> object:
        raise RuntimeError("no such profile")

    monkeypatch.setattr(ps, "read_profile", _boom)
    assert _complete._profile_existing_keys("ghost") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_complete.py -q -k "key or nth_positional"`
Expected: FAIL (`_nth_positional`/`_profile_existing_keys` do not exist; key completion is not wired).

- [ ] **Step 3: Add the helper and the provider**

In `src/unifictl/commands/_complete.py`, add `_nth_positional` next to `_positional_index`:

```python
def _nth_positional(tokens: list[str], index: int) -> str | None:
    """Return the value of positional-``index`` in ``tokens``, or ``None``.

    Flags and the values consumed by value-taking flags are skipped, matching
    :func:`_positional_index`'s accounting.
    """
    count = 0
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token.startswith("-"):
            if token in _VALUE_FLAGS:
                skip_next = True
            continue
        if count == index:
            return token
        count += 1
    return None
```

Add the provider next to `_profile_names`:

```python
def _profile_existing_keys(name: str) -> list[str]:
    """Keys present in profile ``name``'s document, or ``[]`` on any problem."""
    try:
        from unifictl.infrastructure import profile_store

        return list(profile_store.read_profile(name).keys())
    except Exception:
        return []
```

- [ ] **Step 4: Wire key completion at positional 1**

In `run()`, directly after the positional-0 name block from Task 2, add:

```python
    if _positional_index(in_positionals) == 1:
        if cmd_path == ("profile", "set"):
            from unifictl.infrastructure.profile_store import PROFILE_KEYS

            for key in sorted(PROFILE_KEYS):
                print(key)
            return
        if cmd_path == ("profile", "unset"):
            name = _nth_positional(in_positionals, 0)
            if name:
                for key in _profile_existing_keys(name):
                    print(key)
            return
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_complete.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/unifictl/commands/_complete.py tests/test_complete.py
git commit -m "feat(completion): complete profile keys for set and unset"
```

---

### Task 4: Drift-guard test

A test that builds the real cyclopts app and asserts the static tables in `_complete.py` match it — so adding or renaming a command or flag without updating `_complete.py` fails loudly.

**Files:**
- Create: `tests/test_completion_tree_drift.py`

**Interfaces:**
- Consumes: `unifictl.cli.get_app`; `_complete._TOP_LEVEL_COMMANDS`, `_complete._SUB_APP_NAMES`, `_complete._FLAG_NAMES`.

- [ ] **Step 1: Write the test file**

Create `tests/test_completion_tree_drift.py`:

```python
"""Guard the hand-mirrored command tree in `_complete` against the real app.

The completion fast-path deliberately hardcodes commands and flags (so it never
imports cyclopts/rich). These tests build the real app and fail if the static
tables drift from it.
"""

from __future__ import annotations

import inspect
from typing import get_type_hints

from cyclopts import App, Parameter

from unifictl.cli import get_app
from unifictl.commands import _complete


def _command_names(app: App) -> set[str]:
    """Registered sub-command names, excluding auto-added --help/-h/--version."""
    return {name for name in app if not name.startswith("-")}


def _primary_flags(leaf: App) -> tuple[str, ...]:
    """Primary long-form flags for a leaf command, in signature order."""
    func = leaf.default_command
    hints = get_type_hints(func, include_extras=True)
    flags: list[str] = []
    for name, param in inspect.signature(func).parameters.items():
        if param.kind is not inspect.Parameter.KEYWORD_ONLY:
            continue
        hint = hints.get(name)
        override: list[str] | None = None
        if hasattr(hint, "__metadata__"):
            for meta in hint.__metadata__:
                if isinstance(meta, Parameter) and meta.name:
                    override = [meta.name] if isinstance(meta.name, str) else list(meta.name)
        if override:
            flags.append(next((n for n in override if n.startswith("--")), override[0]))
        else:
            flags.append("--" + name.replace("_", "-"))
    return tuple(flags)


def test_top_level_commands_match() -> None:
    assert _command_names(get_app()) == set(_complete._TOP_LEVEL_COMMANDS)


def test_sub_app_names_match() -> None:
    app = get_app()
    for top in _command_names(app):
        assert _command_names(app[top]) == set(_complete._SUB_APP_NAMES[top]), top


def test_flag_names_match() -> None:
    app = get_app()
    for top in _command_names(app):
        for leaf in _command_names(app[top]):
            cmd_path = (top, leaf)
            expected = _primary_flags(app[top][leaf])
            assert _complete._FLAG_NAMES.get(cmd_path, ()) == expected, cmd_path


def test_global_profile_flag_present() -> None:
    assert _primary_flags(get_app().meta) == ("--profile",)
    assert "--profile" in _complete._FLAG_NAMES[()]
```

- [ ] **Step 2: Run the drift test**

Run: `.venv/bin/pytest tests/test_completion_tree_drift.py -q`
Expected: PASS (all four tests). If any fail, the static tables in `_complete.py` are out of sync with the app — fix the table, not the test.

- [ ] **Step 3: Full check**

Run: `.venv/bin/ruff check src tests && .venv/bin/ty check && .venv/bin/pytest -q`
Expected: no lint/type errors; all tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_completion_tree_drift.py
git commit -m "test(completion): guard static command tree against drift"
```

---

## Self-Review

**Spec coverage:**
- Name completion (profile describe/edit/set/unset/activate/delete, credential set/delete, global --profile) → Task 2. ✓
- Profile key completion (set → PROFILE_KEYS, unset → existing keys) → Task 3. ✓
- Flag-name completion + primary-forms-only rule → Task 1. ✓
- Fast-path preserved via lazy imports in providers → Global Constraints + Task 2/3 provider bodies. ✓
- `profile create` excluded → `_PROFILE_NAME_COMMANDS` omits it (Task 2). ✓
- Drift-guard test → Task 4. ✓
- Error-swallowing providers → tested in Tasks 2 and 3. ✓

**Placeholder scan:** none — every code step contains full code and exact commands.

**Type consistency:** `_profile_names`/`_credential_names`/`_profile_existing_keys` return `list[str]`; `_nth_positional` returns `str | None`; `_FLAG_NAMES` value tuples are in signature order, matching `_primary_flags`' signature-order output so tuple equality holds in Task 4.

## Notes on design fidelity

The design doc named `_PROFILE_NAME_AT_POSITION` / `_CREDENTIAL_NAME_AT_POSITION` / `_PROFILE_KEY_AT_POSITION` dicts. Because every name is at positional 0 and only two commands take a key (with different providers — static vs dynamic), this plan uses `frozenset` command sets plus explicit `set`/`unset` branches instead. This is the same static-dispatch approach with less indirection, consistent with the "no premature abstraction" rule. Behaviour and drift-guard coverage are unchanged.
