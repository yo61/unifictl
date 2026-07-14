# Design: name & option completion for unifictl

Date: 2026-07-13

## Goal

Extend shell completion so that:

1. **Commands that take a name complete the name.** `unifictl profile delete <TAB>`
   lists existing profiles; `unifictl credential delete <TAB>` lists credentials;
   the global `unifictl --profile <TAB>` lists profiles.
2. **Options complete too.** `unifictl set lag -<TAB>` lists the flags that
   command accepts (`--switch --leader --dry-run --yes`).

## Constraints

The `__complete` handler is a **fast-path**: `cli.py:main` dispatches it before
importing any command module, so completion never pays for `questionary`/`rich`.
Consequently the command tree is hand-mirrored as static data in
`commands/_complete.py` rather than introspected from the cyclopts `App`. This
design keeps that property: the new flag/name data is static too, and a new test
guards it against drift.

The per-shell scripts (`_completion/unifictl.{bash,zsh,fish}`) forward every
typed token plus the partial and do prefix filtering themselves. **No shell-script
changes are required** — all logic lives in `_complete.py`.

## Inventory (source of truth)

| cmd_path | positional-0 | positional-1 | flags (primary) |
|---|---|---|---|
| `set lag` | on/off *(exists)* | — | `--switch --leader --dry-run --yes` |
| `show port` | port idx *(exists)* | — | `--switch --json` |
| `list devices` | — | — | `--json` |
| `completion install` | — | — | `--shell --dest` |
| `profile describe/edit/activate` | profile name | — | — |
| `profile set` | profile name | profile key (`PROFILE_KEYS`) | — |
| `profile unset` | profile name | profile's existing keys | — |
| `profile delete` | profile name | — | `--yes` |
| `profile create` | *(new name — no completion)* | — | — |
| `credential set` | credential name | — | `--stdin` |
| `credential delete` | credential name | — | `--yes` |
| *(global)* | — | — | `--profile` |

`PROFILE_KEYS` = `base_url, site, switch, ca_cert, insecure_tls, timeout_ms,
credential`.

Decisions confirmed with the user:

- `credential set <name>` completes **existing** names (rotation is the common
  case) even though it can also create a new credential.
- `profile create <name>` gets **no** completion — it takes a new name.

## Feature 1 — name/key completion (positional dynamic values)

New dynamic providers in `_complete.py`, each swallowing all errors → `[]`
(matching the existing `_completion_devices` discipline so a TAB never hangs or
errors):

- `_profile_names()` → `profile_store.list_profile_names()`
- `_credential_names()` → `credential_store.list_credential_names()`
- `_profile_existing_keys(name)` → keys present in that profile's doc (for `unset`)

`profile set`'s key positional uses the static `PROFILE_KEYS`; `profile unset`'s
key positional uses `_profile_existing_keys` (only what is actually set).

New static maps, mirroring the existing `_PORT_IDX_AT_POSITION` /
`_SWITCH_MAC_FLAGS` patterns:

- `_PROFILE_NAME_AT_POSITION: dict[tuple[str,...], int]`
  → `{("profile","describe"):0, ("profile","edit"):0, ("profile","set"):0,
     ("profile","unset"):0, ("profile","activate"):0, ("profile","delete"):0}`
- `_CREDENTIAL_NAME_AT_POSITION: dict[tuple[str,...], int]`
  → `{("credential","set"):0, ("credential","delete"):0}`
- `_PROFILE_KEY_AT_POSITION: dict[tuple[str,...], int]`
  → `{("profile","set"):1, ("profile","unset"):1}`
- Global `--profile` value: an entry keyed `((), "--profile")` resolving to
  `_profile_names()`, handled in the existing "prev is a flag" value branch.
  `--profile` is added to `_VALUE_FLAGS` so positional counting skips it.

The positional dispatch in `run()` gains branches for these maps alongside the
existing port-index-at-position branch, resolving the already-typed name for the
`unset` key case the same way `_resolve_switch` resolves `--switch`.

## Feature 2 — flag-name completion

New static map:

```python
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

"Primary" = the long form only: `--` + param name with `_`→`-`, or the first
`--`-prefixed name in a `Parameter(name=[…])` override. Negative boolean forms
(`--no-dry-run`), short aliases (`-d`), and `--help`/`--version` are omitted.

Trigger in `run()`: compute the partial (`word_list[-1]`). **If it starts with
`-`, emit `_FLAG_NAMES.get(cmd_path, ())` and return**, placed before all
positional-value logic so it takes precedence. This is safe because no value we
complete (MAC, port index, name, key) starts with `-`, so nothing is shadowed.
This is the one place `run()` inspects the partial; today the shell does all
prefix filtering.

## Drift-guard test

`tests/test_completion_tree_drift.py` builds the real `get_app()` and asserts the
static tables match reality:

- top-level command names (excluding `--help`, `-h`, `--version`) ==
  `_TOP_LEVEL_COMMANDS`
- for each top-level command, its sub-app's command names (same exclusions) ==
  `_SUB_APP_NAMES[cmd]`
- for each leaf command, the primary flags derived from its keyword-only
  parameters == `_FLAG_NAMES.get(cmd_path, ())`
- the meta launcher's `--profile` ∈ `_FLAG_NAMES[()]`

Leaf parameters are read via each leaf `App`'s `default_command` and
`inspect.signature`. This test imports cyclopts/rich (it is not the fast-path)
and fails loudly whenever a command or flag is added or renamed without updating
`_complete.py`.

## Behavior tests (extend `tests/test_complete.py`)

- `profile delete <TAB>` → profile names (monkeypatched provider)
- `credential set <TAB>` → credential names
- `unifictl --profile <TAB>` → profile names
- `profile set foo <TAB>` → sorted `PROFILE_KEYS`
- `profile unset foo <TAB>` → that profile's existing keys
- `set lag -<TAB>` → the four `set lag` flags
- `list devices -<TAB>` → `--json`
- name completion swallows store errors → `[]`

## Out of scope

- Introspecting cyclopts at completion time (would defeat the fast-path).
- Negative boolean flags, short aliases, and `--help`/`--version` in flag
  completion.
- Value completion for `--shell` beyond the existing fixed list.
