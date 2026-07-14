## Decision: Keep the shell-completion command tree hardcoded in `_complete.py`, and guard it against drift with an app-introspection test.

## Context: Adding name/key/flag completion (`unifictl profile delete <TAB>`, `set lag -<TAB>`, etc.) needed the completer to know every command, sub-command, and flag. The obvious alternative is to build the real cyclopts app at completion time and read them from it.

## Alternatives considered:
- **Introspect cyclopts at completion time.** Always accurate, zero drift. But building the app imports `rich`/`questionary`/all command modules on every TAB press, defeating the `__complete` fast-path (which today dispatches before importing any command module).
- **Hardcode with no guard.** Fast, but the static tables silently diverge from the real commands over time.

## Reasoning: The fast-path is the whole reason `_complete.py` exists as a separate, dependency-light module. Hardcoding preserves it. The drift risk is neutralised by `tests/test_completion_tree_drift.py`, which builds the real app (imports allowed — it is a test, not the fast-path) and asserts `_TOP_LEVEL_COMMANDS`, `_SUB_APP_NAMES`, `_FLAG_NAMES`, `_PROFILE_NAME_COMMANDS`, and `_CREDENTIAL_NAME_COMMANDS` all match it. Flags are derived from the leaf functions' keyword-only params (via `get_type_hints(..., include_extras=True)`, since `from __future__ import annotations` makes signatures string-typed). The test was verified to actually fail on simulated drift.

## Trade-offs accepted: Adding or renaming a command/flag requires a manual edit to `_complete.py`. That edit is not optional — the drift test fails until it is made. This is deliberate: a loud test failure beats a slow, fast import on every keystroke.

## Supersedes: none. Extends the completion architecture established in `docs/superpowers/specs/2026-07-10-shell-completion-design.md`.
