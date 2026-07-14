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
    assert func is not None
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
