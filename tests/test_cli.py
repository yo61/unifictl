"""Smoke tests for the unifictl CLI wiring."""

from __future__ import annotations

import os
import sys

import pytest

from unifictl.cli import _apply_profile, app, get_app, main
from unifictl.infrastructure.config import ConfigError


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        app(["--help"])
    assert exc.value.code == 0
    assert "unifictl" in capsys.readouterr().out


def test_set_lag_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        app(["set", "lag", "--help"])
    assert exc.value.code == 0


def test_set_lag_without_config_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UNIFI_BASE_URL", raising=False)
    monkeypatch.delenv("UNIFI_API_KEY", raising=False)
    with pytest.raises(ConfigError):
        app(["set", "lag", "off"])


def test_main_maps_config_error_to_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UNIFI_BASE_URL", raising=False)
    monkeypatch.delenv("UNIFI_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["unifictl", "set", "lag", "off"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


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
    assert set(capsys.readouterr().out.split()) == {
        "set",
        "list",
        "show",
        "completion",
        "profile",
        "credential",
    }


def test_main_refreshes_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[bool] = []
    from unifictl.commands import completion

    monkeypatch.setattr(completion, "maybe_refresh_installed_stubs", lambda: called.append(True))
    monkeypatch.setattr(sys, "argv", ["unifictl", "--help"])
    with pytest.raises(SystemExit):
        main()
    assert called == [True]


def test_apply_profile_sets_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UNIFI_PROFILE", raising=False)
    _apply_profile("lab")
    assert os.environ["UNIFI_PROFILE"] == "lab"


def test_apply_profile_none_leaves_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNIFI_PROFILE", "keep")
    _apply_profile(None)
    assert os.environ["UNIFI_PROFILE"] == "keep"


def test_profile_flag_selects_before_dispatch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # NB: do NOT use `--help`/`--version` here — cyclopts intercepts those before
    # the meta launcher runs, so they bypass _apply_profile. Use a real, no-network
    # command (`completion zsh` just prints a script) so the launcher actually runs.
    monkeypatch.delenv("UNIFI_PROFILE", raising=False)
    with pytest.raises(SystemExit):
        get_app().meta(["--profile", "lab", "completion", "zsh"])
    assert os.environ["UNIFI_PROFILE"] == "lab"
    capsys.readouterr()  # swallow the emitted completion script


def test_importing_cli_does_not_pull_questionary() -> None:
    import subprocess
    import sys

    # A fresh interpreter: importing the CLI module must not transitively
    # import questionary (it lives behind the lazy get_app()), so the
    # __complete fast-path stays cheap.
    code = "import unifictl.cli, sys; assert 'questionary' not in sys.modules"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
