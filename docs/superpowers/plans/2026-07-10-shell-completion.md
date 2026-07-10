# Shell Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `bash`/`zsh`/`fish` tab-completion to `unifictl`, deployed automatically by the Homebrew formula.

**Architecture:** Bundle three per-shell scripts under `src/unifictl/_completion/` that shell out to a hidden `unifictl __complete <shell> …` handler. The handler (`commands/_complete.py`) walks a small static command tree and, for switch/port arguments, fetches candidates live from the controller behind a bounded, error-swallowing client so a TAB press can never hang or error the shell. A `completion` sub-App (`commands/completion.py`) prints and installs the scripts and self-heals drifted stubs. `cli.py` fast-paths `__complete` before building the full App.

**Tech Stack:** Python 3.11+, cyclopts, httpx, hatchling, pytest, `importlib.resources`.

## Global Constraints

- `requires-python = ">=3.11"` — no 3.12+ syntax.
- Line length 100; ruff `select = ["E","F","I","UP","B","SIM","RUF"]`; double-quote format.
- `ty` static type check must pass; Google-style docstrings on public functions.
- Absolute imports only (`from unifictl.… import …`), no relative imports.
- Import-linter DDD layers: `commands → application → domain`. `commands/_complete.py` and `commands/completion.py` live in the `commands` layer; they may import `infrastructure` (client/config) since infrastructure is outside the layered contract, exactly as existing command modules do (`set.py` imports `unifictl.infrastructure.client`).
- Switch device type string is `"usw"` (confirmed in `list devices` fixture/output).
- Completion network timeout ceiling: `2000` ms.
- FILES sentinel literal: `__UNIFICTL_COMPLETE_FILES__`.
- Bundled script basenames: `unifictl.bash`, `unifictl.zsh`, `unifictl.fish`. Installed destination filenames: bash `unifictl`, zsh `_unifictl`, fish `unifictl.fish`.
- Commit style: Conventional Commits (`feat:`, `test:`, `docs:`, `chore:`), imperative, ≤72-char subject. commitlint runs in pre-commit.
- Run checks via `task dev:check` (or targeted `uv run pytest …`). Never pipe gate commands through `tail`/`head` — it masks exit codes.

---

### Task 1: Bundle the per-shell completion scripts

**Files:**
- Create: `src/unifictl/_completion/__init__.py`
- Create: `src/unifictl/_completion/unifictl.bash`
- Create: `src/unifictl/_completion/unifictl.zsh`
- Create: `src/unifictl/_completion/unifictl.fish`
- Test: `tests/test_completion_scripts.py`

**Interfaces:**
- Consumes: nothing.
- Produces: three bundled scripts readable via `importlib.resources.files("unifictl._completion")`. Each invokes `unifictl __complete <shell> …` and, on receiving the first output line `__UNIFICTL_COMPLETE_FILES__`, defers to native path completion.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_completion_scripts.py
"""The bundled per-shell completion scripts ship and are well-formed."""

from __future__ import annotations

from importlib import resources

import pytest

_FILES_SENTINEL = "__UNIFICTL_COMPLETE_FILES__"


def _read(name: str) -> str:
    return (resources.files("unifictl._completion") / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["unifictl.bash", "unifictl.zsh", "unifictl.fish"])
def test_script_is_present_and_nonempty(name: str) -> None:
    assert _read(name).strip()


def test_bash_invokes_complete_and_handles_sentinel() -> None:
    body = _read("unifictl.bash")
    assert "unifictl __complete bash" in body
    assert _FILES_SENTINEL in body
    assert "complete -F _unifictl_complete unifictl" in body


def test_zsh_is_compdef_and_handles_sentinel() -> None:
    body = _read("unifictl.zsh")
    assert body.startswith("#compdef unifictl")
    assert "unifictl __complete zsh" in body
    assert _FILES_SENTINEL in body


def test_fish_invokes_complete_and_handles_sentinel() -> None:
    body = _read("unifictl.fish")
    assert "unifictl __complete fish" in body
    assert _FILES_SENTINEL in body
    assert "complete -c unifictl" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_completion_scripts.py -q`
Expected: FAIL — `ModuleNotFoundError`/`FileNotFoundError` (package and scripts don't exist yet).

- [ ] **Step 3: Create the package marker**

```python
# src/unifictl/_completion/__init__.py
"""Bundled per-shell completion scripts, read via importlib.resources."""
```

- [ ] **Step 4: Create the bash script**

```bash
# src/unifictl/_completion/unifictl.bash
# Bash completion for unifictl. Install: copy to
# ~/.local/share/bash-completion/completions/unifictl
# Generated and managed by `unifictl completion install`.

_unifictl_complete() {
    local cur prev words cword
    _init_completion -n : || return

    local response_raw
    local -a response_lines

    response_raw="$(unifictl __complete bash "${COMP_WORDS[@]:0:$COMP_CWORD}" "${COMP_WORDS[$COMP_CWORD]}" 2>/dev/null)"

    mapfile -t response_lines <<< "$response_raw"

    if [[ "${response_lines[0]:-}" == "__UNIFICTL_COMPLETE_FILES__" ]]; then
        COMPREPLY=()
        compopt -o default 2>/dev/null || true
        compopt -o filenames 2>/dev/null || true
        return
    fi

    local current="${COMP_WORDS[$COMP_CWORD]}"
    COMPREPLY=()
    local cand
    for cand in "${response_lines[@]}"; do
        [[ -z "$cand" ]] && continue
        [[ "$cand" == "$current"* ]] || continue
        COMPREPLY+=("$(printf '%q' "$cand")")
    done

    compopt -o nospace 2>/dev/null || true
}

complete -F _unifictl_complete unifictl
```

- [ ] **Step 5: Create the zsh script**

```zsh
# src/unifictl/_completion/unifictl.zsh
#compdef unifictl
# Zsh completion for unifictl. Install: copy to a dir in $fpath as `_unifictl`,
# then `autoload -U compinit; compinit`. Default install location is
# ~/.zfunc/_unifictl (unifictl completion install will set this up).
# Generated and managed by `unifictl completion install`.

_unifictl() {
    local -a candidates
    candidates=("${(@f)$(unifictl __complete zsh "${(@)words[1,$CURRENT-1]}" "${words[$CURRENT]}" 2>/dev/null)}")

    if [[ "${candidates[1]:-}" == "__UNIFICTL_COMPLETE_FILES__" ]]; then
        _files
        return
    fi

    compadd -a candidates
}

_unifictl "$@"
```

- [ ] **Step 6: Create the fish script**

```fish
# src/unifictl/_completion/unifictl.fish
# Fish completion for unifictl. Install: copy to
# ~/.config/fish/completions/unifictl.fish (auto-loaded by fish).
# Generated and managed by `unifictl completion install`.

function __unifictl_complete
    set -l prev (commandline -opc)
    set -l current (commandline -ct)
    set -l result (unifictl __complete fish $prev "$current" 2>/dev/null)
    if test (count $result) -gt 0; and test $result[1] = "__UNIFICTL_COMPLETE_FILES__"
        __fish_complete_path "$current"
        return
    end
    for line in $result
        echo $line
    end
end

complete -c unifictl -f -a "(__unifictl_complete)"
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_completion_scripts.py -q`
Expected: PASS (6 tests).

- [ ] **Step 8: Commit**

```bash
git add src/unifictl/_completion tests/test_completion_scripts.py
git commit -m "feat: bundle per-shell completion scripts"
```

---

### Task 2: `__complete` handler — static command tree and fixed values

**Files:**
- Create: `src/unifictl/commands/_complete.py`
- Test: `tests/test_complete.py`

**Interfaces:**
- Consumes: nothing (static tables only in this task).
- Produces:
  - `run(shell: str, /, *words: str) -> None` — prints one candidate per line to stdout. `words` are the tokens typed so far; first is always `unifictl`, last is the partial being completed (possibly empty).
  - `FILES_SENTINEL: str = "__UNIFICTL_COMPLETE_FILES__"`.
  - Internal `_walk_static(words: list[str]) -> tuple[tuple[str, ...], list[str]]` and `_visible_at(cmd_path: tuple[str, ...]) -> Iterable[str]` (used by later tasks' tests too).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_complete.py
"""The hidden `__complete` candidate emitter."""

from __future__ import annotations

import pytest

from unifictl.commands import _complete


@pytest.fixture()
def run(capsys: pytest.CaptureFixture[str]):
    def _call(*words: str, shell: str = "zsh") -> list[str]:
        _complete.run(shell, *words)
        out = capsys.readouterr().out
        return [line for line in out.splitlines() if line]

    return _call


def test_top_level_commands(run) -> None:
    assert set(run("unifictl", "")) == {"set", "list", "show", "completion"}


def test_set_subcommands(run) -> None:
    assert set(run("unifictl", "set", "")) == {"lag"}


def test_completion_subcommands(run) -> None:
    assert set(run("unifictl", "completion", "")) == {"bash", "fish", "zsh", "install"}


def test_set_lag_state_values(run) -> None:
    assert run("unifictl", "set", "lag", "") == ["on", "off"]


def test_completion_install_shell_values(run) -> None:
    assert run("unifictl", "completion", "install", "--shell", "") == ["bash", "fish", "zsh"]


def test_completion_install_dest_emits_files_sentinel(run) -> None:
    assert run("unifictl", "completion", "install", "--dest", "") == [
        _complete.FILES_SENTINEL
    ]


def test_empty_words_is_noop(run) -> None:
    assert run() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_complete.py -q`
Expected: FAIL — `ModuleNotFoundError: unifictl.commands._complete`.

- [ ] **Step 3: Write the static handler**

```python
# src/unifictl/commands/_complete.py
"""Hidden `__complete` subcommand — emits completion candidates to stdout.

Invoked by the per-shell scripts under ``unifictl/_completion/``. Output is one
candidate per line; the shell scripts handle quoting and prefix filtering.
"""

from __future__ import annotations

from collections.abc import Iterable

# Top-level visible commands (the hidden __complete is intentionally absent).
_TOP_LEVEL_COMMANDS: frozenset[str] = frozenset({"set", "list", "show", "completion"})

# Sub-command names under each grouping command.
_SUB_APP_NAMES: dict[str, frozenset[str]] = {
    "set": frozenset({"lag"}),
    "list": frozenset({"devices"}),
    "show": frozenset({"port"}),
    "completion": frozenset({"bash", "fish", "zsh", "install"}),
}

# cmd_path -> fixed positional-0 candidates (e.g. `set lag on|off`).
_POSITIONAL_FIXED_VALUES: dict[tuple[str, ...], tuple[str, ...]] = {
    ("set", "lag"): ("on", "off"),
}

# (cmd_path, flag) -> fixed value candidates.
_FLAG_FIXED_VALUES: dict[tuple[tuple[str, ...], str], tuple[str, ...]] = {
    (("completion", "install"), "--shell"): ("bash", "fish", "zsh"),
}

# (cmd_path, flag) pairs whose value is a local-disk path; deferred to the shell.
_LOCAL_PATH_FLAGS: frozenset[tuple[tuple[str, ...], str]] = frozenset(
    {
        (("completion", "install"), "--dest"),
        (("completion", "install"), "-d"),
    }
)

# Sole candidate signalling the shell to run native path completion.
FILES_SENTINEL = "__UNIFICTL_COMPLETE_FILES__"


def _walk_static(words: list[str]) -> tuple[tuple[str, ...], list[str]]:
    """Walk the static command tree following ``words``.

    Returns ``(matched_path, remaining_words)``. Matches a known top-level
    command at depth 1, then optionally a depth-2 sub-command.
    """
    if not words or words[0] not in _TOP_LEVEL_COMMANDS:
        return (), list(words)
    sub_commands = _SUB_APP_NAMES.get(words[0])
    if sub_commands is None or len(words) < 2:
        return (words[0],), list(words[1:])
    if words[1] in sub_commands:
        return (words[0], words[1]), list(words[2:])
    return (words[0],), list(words[1:])


def _visible_at(cmd_path: tuple[str, ...]) -> Iterable[str]:
    """Return the visible command names at the given tree depth."""
    if len(cmd_path) == 0:
        return _TOP_LEVEL_COMMANDS
    if len(cmd_path) == 1:
        return _SUB_APP_NAMES.get(cmd_path[0], frozenset())
    return frozenset()


def run(shell: str, /, *words: str) -> None:
    """Print completion candidates for the tokens typed so far.

    Args:
        shell: 'bash' | 'zsh' | 'fish'. Reserved for future per-shell output;
            unused today.
        words: Command-line tokens typed so far. The first is always
            'unifictl'; the last is the partial being completed (may be empty).
    """
    del shell  # reserved for later
    if not words:
        return

    word_list = list(words)
    completed = word_list[1:-1] if len(word_list) > 1 else []
    cmd_path, leftover = _walk_static(completed)
    in_positionals = leftover

    if in_positionals:
        prev = in_positionals[-1]
        if prev.startswith("-"):
            if (cmd_path, prev) in _LOCAL_PATH_FLAGS:
                print(FILES_SENTINEL)
                return
            fixed = _FLAG_FIXED_VALUES.get((cmd_path, prev))
            if fixed is not None:
                for value in fixed:
                    print(value)
                return

    if len(in_positionals) == 0 and cmd_path in _POSITIONAL_FIXED_VALUES:
        for value in _POSITIONAL_FIXED_VALUES[cmd_path]:
            print(value)
        return

    if not leftover:
        for name in sorted(_visible_at(cmd_path)):
            print(name)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_complete.py -q`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/commands/_complete.py tests/test_complete.py
git commit -m "feat: add static __complete candidate handler"
```

---

### Task 3: `__complete` — dynamic switch MAC and port-index completion

**Files:**
- Modify: `src/unifictl/commands/_complete.py`
- Test: `tests/test_complete.py` (append)

**Interfaces:**
- Consumes: `run`, `_walk_static` from Task 2; `unifictl.infrastructure.client.UnifiClient`, `unifictl.infrastructure.config.load_settings`/`ConfigError`/`Settings`.
- Produces:
  - `_completion_devices() -> list[dict[str, object]]` — bounded, error-swallowing device fetch (returns `[]` on missing config or any failure).
  - `_switch_macs() -> list[str]` — MACs of `type == "usw"` devices.
  - `_resolve_switch(tokens: list[str]) -> str | None` — the `--switch` value already typed, else the config default.
  - `_port_indices(switch_mac: str) -> list[str]` — `port_idx` strings from the switch's `port_table`.
  - `COMPLETION_TIMEOUT_MS: int = 2000`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_complete.py  (append)

from unifictl.infrastructure.config import Settings

_DEVICES = [
    {"type": "usw", "mac": "70:a7:41:90:82:dd", "port_table": [
        {"port_idx": 1}, {"port_idx": 2}, {"port_idx": 17},
    ]},
    {"type": "ugw", "mac": "aa:bb:cc:dd:ee:ff", "port_table": [{"port_idx": 1}]},
]


@pytest.fixture()
def fake_devices(monkeypatch: pytest.MonkeyPatch):
    def _install(devices: list[dict]) -> None:
        monkeypatch.setattr(_complete, "_completion_devices", lambda: list(devices))

    return _install


def test_switch_mac_completion_lists_only_switches(run, fake_devices) -> None:
    fake_devices(_DEVICES)
    assert run("unifictl", "show", "port", "--switch", "") == ["70:a7:41:90:82:dd"]


def test_switch_mac_completion_on_set_lag(run, fake_devices) -> None:
    fake_devices(_DEVICES)
    assert run("unifictl", "set", "lag", "off", "--switch", "") == ["70:a7:41:90:82:dd"]


def test_port_index_completion_uses_typed_switch(run, fake_devices) -> None:
    fake_devices(_DEVICES)
    out = run("unifictl", "show", "port", "--switch", "70:a7:41:90:82:dd", "")
    assert out == ["1", "2", "17"]


def test_leader_flag_completes_port_indices(run, fake_devices) -> None:
    fake_devices(_DEVICES)
    out = run("unifictl", "set", "lag", "off", "--switch", "70:a7:41:90:82:dd", "--leader", "")
    assert out == ["1", "2", "17"]


def test_port_index_falls_back_to_config_switch(run, fake_devices, monkeypatch) -> None:
    fake_devices(_DEVICES)
    settings = Settings(base_url="https://c", api_key="k", switch="70:a7:41:90:82:dd")
    monkeypatch.setattr(_complete, "load_settings", lambda: settings)
    assert run("unifictl", "show", "port", "") == ["1", "2", "17"]


def test_port_index_no_switch_yields_nothing(run, fake_devices, monkeypatch) -> None:
    fake_devices(_DEVICES)
    from unifictl.infrastructure.config import ConfigError

    def _raise() -> Settings:
        raise ConfigError("no config")

    monkeypatch.setattr(_complete, "load_settings", _raise)
    assert run("unifictl", "show", "port", "") == []


def test_completion_devices_swallows_client_errors(monkeypatch) -> None:
    settings = Settings(base_url="https://c", api_key="k", timeout_ms=30000)
    monkeypatch.setattr(_complete, "load_settings", lambda: settings)

    class _BoomClient:
        def __init__(self, s: Settings) -> None:
            assert s.timeout_ms == _complete.COMPLETION_TIMEOUT_MS  # clamped
            self.closed = False

        def get_devices(self):
            raise RuntimeError("controller unreachable")

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(_complete, "UnifiClient", _BoomClient)
    assert _complete._completion_devices() == []


def test_completion_devices_no_config_returns_empty(monkeypatch) -> None:
    from unifictl.infrastructure.config import ConfigError

    def _raise() -> Settings:
        raise ConfigError("no config")

    monkeypatch.setattr(_complete, "load_settings", _raise)
    assert _complete._completion_devices() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_complete.py -q`
Expected: FAIL — `AttributeError: module … has no attribute '_completion_devices'` / `UnifiClient`.

- [ ] **Step 3: Add module-level imports for the dynamic path**

At the top of `src/unifictl/commands/_complete.py`, below the existing imports, add the names the tests monkeypatch (they must be module attributes):

```python
from unifictl.infrastructure.client import UnifiClient
from unifictl.infrastructure.config import ConfigError, load_settings
```

- [ ] **Step 4: Add the dynamic helpers**

Add to `src/unifictl/commands/_complete.py` (after the static tables, before `run`):

```python
# Hard ceiling on the completion network call so an unreachable controller
# fails fast instead of freezing the shell on TAB.
COMPLETION_TIMEOUT_MS = 2000

# Flags whose value is a switch MAC.
_SWITCH_MAC_FLAGS: frozenset[tuple[tuple[str, ...], str]] = frozenset(
    {
        (("set", "lag"), "--switch"),
        (("show", "port"), "--switch"),
    }
)

# cmd_path -> positional index that is a port index.
_PORT_IDX_AT_POSITION: dict[tuple[str, ...], int] = {
    ("show", "port"): 0,
}

# Flags whose value is a port index.
_PORT_IDX_FLAGS: frozenset[tuple[tuple[str, ...], str]] = frozenset(
    {
        (("set", "lag"), "--leader"),
    }
)


def _completion_devices() -> list[dict[str, object]]:
    """Fetch raw devices for completion, or ``[]`` on any problem.

    Bounded by ``COMPLETION_TIMEOUT_MS`` and swallows every error so a TAB
    press never hangs or fails: missing config, an unreachable controller, or
    a malformed response all degrade to no candidates.
    """
    from dataclasses import replace

    try:
        settings = load_settings()
    except ConfigError:
        return []
    settings = replace(settings, timeout_ms=min(settings.timeout_ms, COMPLETION_TIMEOUT_MS))
    client = None
    try:
        client = UnifiClient(settings)
        return client.get_devices()
    except Exception:  # noqa: BLE001 — completion must never surface errors
        return []
    finally:
        if client is not None:
            client.close()


def _switch_macs() -> list[str]:
    """MACs of adopted switches (``type == 'usw'``)."""
    macs: list[str] = []
    for device in _completion_devices():
        if device.get("type") == "usw":
            mac = device.get("mac")
            if isinstance(mac, str) and mac:
                macs.append(mac)
    return macs


def _resolve_switch(tokens: list[str]) -> str | None:
    """The ``--switch`` value already typed in ``tokens``, else the config default."""
    for index, token in enumerate(tokens):
        if token == "--switch" and index + 1 < len(tokens):
            return tokens[index + 1]
    try:
        return load_settings().switch
    except ConfigError:
        return None


def _port_indices(switch_mac: str) -> list[str]:
    """The ``port_idx`` values (as strings) from ``switch_mac``'s ``port_table``."""
    for device in _completion_devices():
        if device.get("mac") == switch_mac:
            table = device.get("port_table", [])
            indices: list[str] = []
            if isinstance(table, list):
                for entry in table:
                    if isinstance(entry, dict) and "port_idx" in entry:
                        indices.append(str(entry["port_idx"]))
            return indices
    return []
```

- [ ] **Step 5: Wire the dynamic branches into `run`**

In `run`, inside the `if prev.startswith("-"):` block, after the `_FLAG_FIXED_VALUES` branch and before it returns to the outer flow, add the switch/port flag branches:

```python
            if (cmd_path, prev) in _SWITCH_MAC_FLAGS:
                for mac in _switch_macs():
                    print(mac)
                return
            if (cmd_path, prev) in _PORT_IDX_FLAGS:
                switch_mac = _resolve_switch(in_positionals[:-1])
                if switch_mac:
                    for port in _port_indices(switch_mac):
                        print(port)
                return
```

Then, after the `_POSITIONAL_FIXED_VALUES` block and before the final `_visible_at` block, add the positional port-index branch:

```python
    port_position = _PORT_IDX_AT_POSITION.get(cmd_path)
    if port_position is not None and len(in_positionals) == port_position:
        switch_mac = _resolve_switch(in_positionals)
        if switch_mac:
            for port in _port_indices(switch_mac):
                print(port)
        return
```

> **Plan amendment (applied during execution):** `len(in_positionals)` counts
> interleaved flags and the values they consume, so `show port --switch <mac>
> <TAB>` (zero positionals typed) failed to match `== 0`. Fix: add a module-level
> `_VALUE_FLAGS = frozenset({"--switch", "--leader", "--shell", "--dest", "-d"})`
> and a `_positional_index(tokens)` helper that counts positionals while skipping
> flags and their consumed values, then replace `len(in_positionals)` with
> `_positional_index(in_positionals)` in **both** positional branches (the
> `_POSITIONAL_FIXED_VALUES` check above and this port-index check). Two
> regression tests were added: `set lag --switch aa:bb <TAB>` → `on off`, and a
> direct `_positional_index` unit test. Also: the brief's `# noqa: BLE001` is
> dropped (ruff `select` excludes `BLE`, so it is a dead/unused noqa flagged by
> RUF100) and `entry["port_idx"]` becomes `entry.get("port_idx")` for `ty`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_complete.py -q`
Expected: PASS (all Task 2 + Task 3 tests).

- [ ] **Step 7: Run ruff and ty on the module**

Run: `uv run ruff check src/unifictl/commands/_complete.py && uv run ty check src/unifictl/commands/_complete.py`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add src/unifictl/commands/_complete.py tests/test_complete.py
git commit -m "feat: complete switch MACs and port indices from the controller"
```

---

### Task 4: `completion` sub-App — print, install, self-heal

**Files:**
- Create: `src/unifictl/commands/completion.py`
- Test: `tests/test_cmd_completion.py`

**Interfaces:**
- Consumes: bundled scripts from Task 1 via `importlib.resources`.
- Produces:
  - `app: cyclopts.App` (name `"completion"`) with commands `bash`, `zsh`, `fish`, `install`.
  - `install(*, shell: str | None = None, dest: str | None = None) -> None`.
  - `maybe_refresh_installed_stubs() -> None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cmd_completion.py
"""`unifictl completion` print/install/refresh behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from unifictl.commands import completion


def test_print_zsh_emits_compdef(capsys: pytest.CaptureFixture[str]) -> None:
    completion.zsh()
    assert capsys.readouterr().out.startswith("#compdef unifictl")


def test_print_bash_emits_complete(capsys: pytest.CaptureFixture[str]) -> None:
    completion.bash()
    assert "complete -F _unifictl_complete unifictl" in capsys.readouterr().out


def test_install_writes_zsh_stub(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    completion.install(shell="zsh", dest=str(tmp_path))
    target = tmp_path / "_unifictl"
    assert target.read_text(encoding="utf-8").startswith("#compdef unifictl")
    assert "wrote" in capsys.readouterr().out


def test_install_bash_uses_plain_filename(tmp_path: Path) -> None:
    completion.install(shell="bash", dest=str(tmp_path))
    assert (tmp_path / "unifictl").is_file()


def test_install_fish_uses_dot_fish_filename(tmp_path: Path) -> None:
    completion.install(shell="fish", dest=str(tmp_path))
    assert (tmp_path / "unifictl.fish").is_file()


def test_install_idempotent_second_run_is_noop(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    completion.install(shell="zsh", dest=str(tmp_path))
    capsys.readouterr()
    completion.install(shell="zsh", dest=str(tmp_path))
    out = capsys.readouterr().out
    assert "up to date" in out
    assert not (tmp_path / "_unifictl.bak").exists()


def test_install_backs_up_existing(tmp_path: Path) -> None:
    target = tmp_path / "_unifictl"
    target.write_text("old content", encoding="utf-8")
    completion.install(shell="zsh", dest=str(tmp_path))
    assert (tmp_path / "_unifictl.bak").read_text(encoding="utf-8") == "old content"
    assert target.read_text(encoding="utf-8").startswith("#compdef unifictl")


def test_install_unknown_shell_exits_1(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        completion.install(shell="tcsh", dest=str(tmp_path))
    assert exc.value.code == 1


def test_default_install_dir_zsh_honors_zdotdir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZDOTDIR", "/tmp/zdot")
    assert completion._default_install_dir("zsh") == Path("/tmp/zdot/completions")


def test_refresh_rewrites_drifted_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZDOTDIR", str(tmp_path))
    stub_dir = tmp_path / "completions"
    stub_dir.mkdir()
    stale = stub_dir / "_unifictl"
    stale.write_text("stale", encoding="utf-8")
    completion.maybe_refresh_installed_stubs()
    assert stale.read_text(encoding="utf-8").startswith("#compdef unifictl")
    assert (stub_dir / "_unifictl.bak").read_text(encoding="utf-8") == "stale"


def test_refresh_ignores_absent_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZDOTDIR", str(tmp_path))
    completion.maybe_refresh_installed_stubs()  # no dir -> no error, no write
    assert not (tmp_path / "completions").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cmd_completion.py -q`
Expected: FAIL — `ModuleNotFoundError: unifictl.commands.completion`.

- [ ] **Step 3: Write the completion command module**

```python
# src/unifictl/commands/completion.py
"""`unifictl completion` — print or install per-shell completion scripts."""

from __future__ import annotations

import os
import shutil
import sys
from importlib import resources
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

app = App(name="completion", help="Print or install unifictl shell completion scripts.")

# Destination filename per shell (differs from the bundled `unifictl.<shell>`).
_SHELL_FILENAMES: dict[str, str] = {
    "bash": "unifictl",
    "zsh": "_unifictl",
    "fish": "unifictl.fish",
}

# Legacy zsh install dir, probed on refresh so existing installs keep updating.
_LEGACY_ZSH_DIR = "~/.zfunc"


def _default_install_dir(shell: str) -> Path:
    """Return the default install directory for ``shell``.

    For zsh, honors ``$ZDOTDIR`` (XDG-style layouts expose their dir this way)
    and falls back to ``~/.zfunc``.
    """
    if shell == "bash":
        return Path("~/.local/share/bash-completion/completions").expanduser()
    if shell == "fish":
        return Path("~/.config/fish/completions").expanduser()
    if shell == "zsh":
        zdotdir = os.environ.get("ZDOTDIR")
        if zdotdir:
            return Path(zdotdir) / "completions"
        return Path(_LEGACY_ZSH_DIR).expanduser()
    raise KeyError(shell)


def _refresh_candidate_paths(shell: str) -> list[Path]:
    """Paths that may host a previously-installed stub for ``shell``."""
    filename = _SHELL_FILENAMES[shell]
    if shell != "zsh":
        return [_default_install_dir(shell) / filename]
    paths = [Path(_LEGACY_ZSH_DIR).expanduser() / filename]
    zdotdir = os.environ.get("ZDOTDIR")
    if zdotdir:
        xdg = Path(zdotdir) / "completions" / filename
        if xdg != paths[0]:
            paths.append(xdg)
    return paths


def _read(shell: str) -> str:
    """Read the bundled shell script for ``shell`` ('bash' | 'zsh' | 'fish')."""
    name = f"unifictl.{shell}"
    return (resources.files("unifictl._completion") / name).read_text(encoding="utf-8")


def _detect_shell() -> str | None:
    """Detect the user's shell from ``$SHELL``. Return bash/zsh/fish, or None."""
    name = Path(os.environ.get("SHELL", "")).name
    return name if name in _SHELL_FILENAMES else None


@app.command(name="bash")
def bash() -> None:
    """Print the bash completion script to stdout."""
    print(_read("bash"))


@app.command(name="zsh")
def zsh() -> None:
    """Print the zsh completion script to stdout."""
    print(_read("zsh"))


@app.command(name="fish")
def fish() -> None:
    """Print the fish completion script to stdout."""
    print(_read("fish"))


@app.command(name="install")
def install(
    *,
    shell: Annotated[str | None, Parameter(name=["--shell"])] = None,
    dest: Annotated[str | None, Parameter(name=["--dest", "-d"])] = None,
) -> None:
    """Install the unifictl completion script for the current shell.

    Args:
        shell: Override shell detection. One of 'bash', 'zsh', 'fish'.
        dest: Override the default install directory. The filename inside the
            dir is still determined by shell.
    """
    detected = shell or _detect_shell()
    if detected is None or detected not in _SHELL_FILENAMES:
        print("ERROR: could not detect shell. Pass --shell bash|zsh|fish.", flush=True)
        raise SystemExit(1)

    filename = _SHELL_FILENAMES[detected]
    target_dir = Path(dest) if dest else _default_install_dir(detected)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    new_content = _read(detected)

    if target.exists() and target.read_text(encoding="utf-8") == new_content:
        print(f"unifictl completion: {target} is already up to date.")
        return

    if target.exists():
        backup = target.parent / (target.name + ".bak")
        shutil.copy2(target, backup)
        print(f"unifictl completion: backed up existing {target} -> {backup}")

    target.write_text(new_content, encoding="utf-8")
    print(f"unifictl completion: wrote {target}")

    if detected == "zsh":
        print("Add this to your ~/.zshrc if you haven't already:")
        print(f"  fpath+={target_dir}")
        print("  autoload -U compinit && compinit")
    elif detected == "bash":
        print("Reload your shell or `source ~/.bashrc` to activate.")
    elif detected == "fish":
        print("Reload fish (functions auto-discover; usually no action needed).")


def maybe_refresh_installed_stubs() -> None:
    """Rewrite any installed completion stub that has drifted from the bundled one.

    Only touches stubs that already exist — never installs for users who never
    ran ``completion install``. Read/write errors are swallowed so a hostile
    filesystem can't make every ``unifictl`` invocation noisy.
    """
    for shell in _SHELL_FILENAMES:
        bundled = _read(shell)
        for target in _refresh_candidate_paths(shell):
            if not target.is_file():
                continue
            try:
                installed = target.read_text(encoding="utf-8")
            except OSError:
                continue
            if installed == bundled:
                continue
            try:
                backup = target.parent / (target.name + ".bak")
                shutil.copy2(target, backup)
                target.write_text(bundled, encoding="utf-8")
            except OSError:
                continue
            print(f"unifictl: refreshed {shell} completion stub at {target}", file=sys.stderr)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cmd_completion.py -q`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/commands/completion.py tests/test_cmd_completion.py
git commit -m "feat: add completion command with install and self-heal"
```

---

### Task 5: Wire completion into the CLI

**Files:**
- Modify: `src/unifictl/cli.py`
- Test: `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `_complete.run` (Task 2/3), `completion.app` + `completion.maybe_refresh_installed_stubs` (Task 4).
- Produces: `unifictl completion …` registered on the top App; `unifictl __complete …` handled via `main()` fast-path before the App is built; `maybe_refresh_installed_stubs()` called on every normal `main()` run.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py  (append)

def test_completion_zsh_registered(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        app(["completion", "zsh"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.startswith("#compdef unifictl")


def test_main_complete_fast_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["unifictl", "__complete", "zsh", "unifictl", ""])
    main()
    assert set(capsys.readouterr().out.split()) == {"set", "list", "show", "completion"}


def test_main_refreshes_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[bool] = []
    from unifictl.commands import completion

    monkeypatch.setattr(completion, "maybe_refresh_installed_stubs", lambda: called.append(True))
    monkeypatch.setattr(sys, "argv", ["unifictl", "--help"])
    with pytest.raises(SystemExit):
        main()
    assert called == [True]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -q`
Expected: FAIL — `completion` command unknown / fast-path prints nothing.

> **Plan amendment (applied during execution):** registering the completion
> sub-App beside the existing eager module-level command imports (Steps 3–4 as
> originally written) defeats the fast-path — `import unifictl.cli` (which the
> `unifictl.cli:main` entry point always runs) would pull in `set.py` →
> `questionary` before `main()`'s `__complete` branch fires, so TAB completion
> pays the heavy-import cost the fast-path exists to avoid. Fix: restructure
> cli.py to build the App lazily (mirroring jobhound) — move ALL command-module
> imports and `App` construction into a `get_app()` function, register
> `completion_app` there too, and expose `app` as a thin shim
> (`def app(*a, **k): return get_app()(*a, **k)`) so `from unifictl.cli import
> app; app([...])` still works. A regression test asserts a fresh
> `import unifictl.cli` leaves `questionary` out of `sys.modules`. Steps 3–4
> below are superseded by this lazy structure.

- [ ] **Step 3: Register the completion sub-App**

In `src/unifictl/cli.py`, add the import beside the other command imports and register it:

```python
from unifictl.commands.completion import app as completion_app
```

```python
app.command(set_app)
app.command(list_app)
app.command(show_app)
app.command(completion_app)
```

- [ ] **Step 4: Add the fast-path and stub refresh to `main`**

Replace the body of `main()` in `src/unifictl/cli.py` with:

```python
def main() -> None:
    """Entry point: dispatch to cyclopts, mapping known errors to clean exits.

    Fast-path: ``unifictl __complete …`` dispatches straight to the completion
    handler, skipping the full App build (and its ``questionary`` import).

    Cyclopts raises ``SystemExit`` for ``--help``/``--version`` and usage
    errors. Configuration problems (:class:`ConfigError`) and private-API
    failures (:class:`UnifiClientError`) are converted to a single stderr line
    rather than a traceback.
    """
    if len(sys.argv) >= 2 and sys.argv[1] == "__complete":
        from unifictl.commands._complete import run as complete_run

        complete_run(*sys.argv[2:])
        return

    from unifictl.commands import completion

    completion.maybe_refresh_installed_stubs()

    from unifictl.application.device_service import PortNotFoundError
    from unifictl.infrastructure.client import UnifiClientError
    from unifictl.infrastructure.config import ConfigError

    try:
        app()
    except (ConfigError, UnifiClientError, PortNotFoundError) as exc:
        print(f"unifictl: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
```

- [ ] **Step 5: Run the CLI test suite**

Run: `uv run pytest tests/test_cli.py -q`
Expected: PASS (existing + 3 new tests).

- [ ] **Step 6: Run the full check gate**

Run: `task dev:check`
Expected: lint, type-check, import-linter, and all tests pass. (The import-linter `DDD layers` contract must stay green — `commands` importing `infrastructure` is allowed; importing `application`/`domain` downward is fine.)

- [ ] **Step 7: Commit**

```bash
git add src/unifictl/cli.py tests/test_cli.py
git commit -m "feat: wire completion command and __complete fast-path into cli"
```

---

### Task 6: Verify the scripts ship in the built artifacts

**Files:**
- None (verification + potential `pyproject.toml` fix only if the build omits the scripts).

**Interfaces:**
- Consumes: the built wheel/sdist.
- Produces: confidence that `_completion/*.{bash,zsh,fish}` are packaged (this is what Homebrew builds from).

- [ ] **Step 1: Build the distributions**

Run: `uv build`
Expected: `dist/unifictl-*.tar.gz` and `dist/unifictl-*.whl` created.

- [ ] **Step 2: Assert the scripts are in the wheel**

Run: `uv run python -c "import zipfile,glob; z=zipfile.ZipFile(sorted(glob.glob('dist/*.whl'))[-1]); names=z.namelist(); assert all(f'unifictl/_completion/unifictl.{s}' in names for s in ('bash','zsh','fish')), names; print('wheel OK')"`
Expected: `wheel OK`.

- [ ] **Step 3: Assert the scripts are in the sdist**

Run: `uv run python -c "import tarfile,glob; t=tarfile.open(sorted(glob.glob('dist/*.tar.gz'))[-1]); names=t.getnames(); assert any(n.endswith('unifictl/_completion/unifictl.zsh') for n in names), names; print('sdist OK')"`
Expected: `sdist OK`.

- [ ] **Step 4 (only if a build assertion failed): force-include the scripts**

If either assertion fails, add to `pyproject.toml` under the wheel target and re-run Steps 1–3:

```toml
[tool.hatch.build.targets.wheel.force-include]
"src/unifictl/_completion" = "unifictl/_completion"
```

Then commit:

```bash
git add pyproject.toml
git commit -m "build: ensure completion scripts ship in the wheel"
```

If the assertions passed, no commit is needed for this task — hatchling's defaults already package the scripts.

- [ ] **Step 5: Clean up build artifacts**

Run: `trash dist` (or `rm -rf dist` is *not* allowed per repo rules; use `trash`).

---

### Task 7: Document completion in the README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: the `completion` command from Task 4.
- Produces: user-facing install instructions.

- [ ] **Step 1: Add a completion section to the README**

Insert a section (after the install/usage sections) documenting:

```markdown
## Shell completion

`unifictl` ships bash, zsh, and fish completion. The Homebrew formula installs
it automatically. For `uv tool`/`pipx` installs, run:

```sh
unifictl completion install          # detects your shell from $SHELL
unifictl completion install --shell zsh
```

Or print a script to wire up manually:

```sh
unifictl completion zsh > "${ZDOTDIR:-$HOME/.zfunc}/completions/_unifictl"
```

Completion covers the command tree, `set lag on|off`, and — when your
controller is reachable — switch MACs (`--switch`) and port indices
(`show port`, `set lag --leader`). A slow or unreachable controller yields no
candidates rather than blocking your shell.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document shell completion"
```

---

### Task 8: Deploy completion via the Homebrew formula (repo: `yo61/homebrew-tap`)

> **Sequencing:** Do this **after** a `unifictl` release containing the `completion` command is published to PyPI and the tap's auto-bump PR has landed that version. `generate_completions_from_executable` runs the installed binary at build time, so the formula must point at a version that *has* the command. This is a separate git repo — branch and PR there, not in `unifictl`.
>
> **Cross-repo dependency (see `decisions/2026-07-10-homebrew-bump-cooldown-gotcha.md`):** the tap's `bump-unifictl.yaml` dispatches `brew update-python-resources` seconds after a release, but Homebrew's hardcoded 24h release cooldown (`RELEASE_COOLDOWN_DAYS = 1`) makes that resolve step **fail** for any PyPI upload younger than a day. `bump-unifictl.yaml` still has this latent bug (jobhound already hit it on 0.17.0 and got the fix). So the completion release will not auto-deploy to Homebrew until `bump-unifictl.yaml` gets the jobhound-style self-heal (schedule trigger + cooldown gate + `skip_cooldown` emergency input, mirroring `bump-jobhound.yaml`). Fold that workflow fix into the same tap PR as this formula edit (or land it first), otherwise the bump that would carry these completions goes red. This is orthogonal to the formula's `install`/`test` blocks — it is a workflow fix, not a formula edit.

**Files:**
- Modify: `~/code/github.com/yo61/homebrew-tap/Formula/unifictl.rb` (`def install` and `test do` blocks only).

**Interfaces:**
- Consumes: the published `unifictl` binary's `completion` command.
- Produces: bash/zsh/fish completions installed into the Homebrew prefix on `brew install`/`brew upgrade`.

- [ ] **Step 1: Branch the tap repo**

```bash
cd ~/code/github.com/yo61/homebrew-tap
git checkout -b feat/unifictl-completions
```

- [ ] **Step 2: Add completion generation to the install block**

In `Formula/unifictl.rb`, change:

```ruby
  def install
    virtualenv_install_with_resources
  end
```

to:

```ruby
  def install
    virtualenv_install_with_resources

    # `unifictl completion <shell>` takes the shell positionally, matching the
    # default shell_parameter_format (nil) that passes the bare shell name.
    generate_completions_from_executable(bin/"unifictl", "completion")
  end
```

- [ ] **Step 3: Add a completion assertion to the test block**

Change:

```ruby
  test do
    assert_equal version.to_s, shell_output("#{bin}/unifictl --version").strip
  end
```

to:

```ruby
  test do
    assert_equal version.to_s, shell_output("#{bin}/unifictl --version").strip
    assert_match "#compdef unifictl", shell_output("#{bin}/unifictl completion zsh")
  end
```

- [ ] **Step 4: Validate the formula locally**

Run: `brew style Formula/unifictl.rb && brew audit --formula Formula/unifictl.rb`
Expected: no offenses. (If `brew` is unavailable locally, rely on the tap's `tests.yaml` CI, which builds bottles and runs `brew test`.)

- [ ] **Step 5: Commit and open a PR**

```bash
git add Formula/unifictl.rb
git commit -m "feat(unifictl): install shell completions"
git push -u origin feat/unifictl-completions
gh pr create --base main --title "feat(unifictl): install shell completions" \
  --body "Adds generate_completions_from_executable so bash/zsh/fish completions install with the formula. Survives future auto-bumps (bump workflow only rewrites url/sha256 + resources)."
```

---

## Notes for the implementer

- **Repo boundary:** Tasks 1–7 are in `unifictl`; Task 8 is in `yo61/homebrew-tap` and is time-sequenced after a release. Do not mix their commits.
- **Never let completion raise:** every network path in `_complete.py` funnels through `_completion_devices()`, which swallows all exceptions. If you add a new dynamic branch, route it through that helper — do not call the client directly.
- **The `shell` arg is deliberately unused** in `_complete.run`; it is reserved for future per-shell output (e.g. zsh description columns). Keep it in the signature.
