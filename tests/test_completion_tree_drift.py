"""Guard the hand-mirrored command tree in `_complete` against the real app.

The completion fast-path deliberately hardcodes commands and flags (so it never
imports cyclopts/rich). These tests build the real app and fail if the static
tables drift from it.
"""

from __future__ import annotations

import inspect
from typing import get_type_hints

import pytest
from cyclopts import App, Parameter

from unifictl.cli import get_app
from unifictl.commands import _complete
from unifictl.infrastructure.config import Settings


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


def _leaves_taking_leading_name(app, group: str) -> set:
    """Leaf commands under `group` whose first positional parameter is `name`."""
    result = set()
    for leaf in _command_names(app[group]):
        func = app[group][leaf].default_command
        params = list(inspect.signature(func).parameters.values())
        if (
            params
            and params[0].name == "name"
            and params[0].kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ):
            result.add((group, leaf))
    return result


def test_profile_name_commands_match() -> None:
    app = get_app()
    # `create` takes a NEW name, so it is intentionally excluded from completion.
    expected = _leaves_taking_leading_name(app, "profile") - {("profile", "create")}
    assert set(_complete._PROFILE_NAME_COMMANDS) == expected


def test_credential_name_commands_match() -> None:
    assert set(_complete._CREDENTIAL_NAME_COMMANDS) == _leaves_taking_leading_name(
        get_app(), "credential"
    )


# Every spelling cyclopts accepts for a value-taking flag. Only the first keeps
# the value in a token of its own; the rest attach it to the flag token, which
# the completion fast path has to unpack for itself.
_VALUE_FLAG_SPELLINGS: tuple[tuple[str, ...], ...] = (
    ("--switch", "70:a7:41:90:82:dd"),
    ("--switch=70:a7:41:90:82:dd",),
)

_SHORT_FLAG_SPELLINGS: tuple[tuple[str, ...], ...] = (
    ("-d", "/tmp/x"),
    ("-d/tmp/x",),
    ("-d=/tmp/x",),
    ("--dest", "/tmp/x"),
    ("--dest=/tmp/x",),
)

_DRIFT_DEVICES = [
    {
        "type": "usw",
        "mac": "70:a7:41:90:82:dd",
        "port_table": [{"port_idx": 1}, {"port_idx": 2}, {"port_idx": 17}],
    },
    {"type": "usw", "mac": "aa:bb:cc:dd:ee:ff", "port_table": [{"port_idx": 9}]},
]


@pytest.fixture
def _drift_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_complete, "_completion_devices", lambda: list(_DRIFT_DEVICES))
    monkeypatch.setattr(
        _complete,
        "load_settings",
        lambda: Settings(base_url="https://c", api_key="k", switch="aa:bb:cc:dd:ee:ff"),
    )


def _candidates(capsys: pytest.CaptureFixture[str], *words: str) -> list[str]:
    _complete.run("zsh", *words)
    return [line for line in capsys.readouterr().out.splitlines() if line]


@pytest.mark.parametrize("spelling", _SHORT_FLAG_SPELLINGS, ids=lambda s: " ".join(s))
def test_app_accepts_every_dest_spelling(spelling: tuple[str, ...]) -> None:
    # Guards the matrix itself: a form listed here that the CLI rejects would
    # make the completion tests below assert against an impossible command line.
    _, bound, _ = get_app().parse_args(
        ["completion", "install", *spelling], exit_on_error=False, verbose=False
    )
    assert bound.arguments["dest"] == "/tmp/x"


@pytest.mark.parametrize("spelling", _VALUE_FLAG_SPELLINGS, ids=lambda s: " ".join(s))
def test_app_accepts_every_switch_spelling(spelling: tuple[str, ...]) -> None:
    _, bound, _ = get_app().parse_args(
        ["show", "port", "3", *spelling], exit_on_error=False, verbose=False
    )
    assert bound.arguments["switch"] == "70:a7:41:90:82:dd"


@pytest.mark.parametrize("spelling", _VALUE_FLAG_SPELLINGS, ids=lambda s: " ".join(s))
def test_typed_switch_drives_port_completion_in_every_spelling(
    spelling: tuple[str, ...], _drift_devices: None, capsys: pytest.CaptureFixture[str]
) -> None:
    # The config default switch is aa:bb:cc:dd:ee:ff, whose only port is 9. A
    # spelling the fast path fails to read silently offers that switch's ports.
    assert _candidates(capsys, "unifictl", "show", "port", *spelling, "") == ["1", "2", "17"]


@pytest.mark.parametrize("spelling", _VALUE_FLAG_SPELLINGS, ids=lambda s: " ".join(s))
def test_typed_switch_drives_leader_completion_in_every_spelling(
    spelling: tuple[str, ...], _drift_devices: None, capsys: pytest.CaptureFixture[str]
) -> None:
    out = _candidates(capsys, "unifictl", "set", "lag", "off", *spelling, "--leader", "")
    assert out == ["1", "2", "17"]


@pytest.mark.parametrize(
    "spelling", (("--profile", "home"), ("--profile=home",)), ids=lambda s: " ".join(s)
)
def test_app_accepts_every_global_profile_spelling(spelling: tuple[str, ...]) -> None:
    _, bound, _ = get_app().meta.parse_args(
        [*spelling, "set", "lag", "on"], exit_on_error=False, verbose=False
    )
    assert bound.arguments["profile"] == "home"


@pytest.mark.parametrize(
    "spelling", (("--profile", "home"), ("--profile=home",)), ids=lambda s: " ".join(s)
)
def test_leading_global_profile_does_not_derail_the_walk(
    spelling: tuple[str, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    assert _candidates(capsys, "unifictl", *spelling, "set", "lag", "") == ["on", "off"]


@pytest.mark.parametrize("spelling", _SHORT_FLAG_SPELLINGS, ids=lambda s: " ".join(s))
def test_attached_flag_values_are_not_counted_as_positionals(spelling: tuple[str, ...]) -> None:
    # `completion install` takes no positionals, so every spelling must leave
    # the positional cursor at 0.
    assert _complete._positional_index(list(spelling)) == 0
