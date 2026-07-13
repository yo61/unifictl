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
        'import sys\np = sys.argv[1]\nopen(p, "a").write(\'switch = "aa"\\n\')\n',
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


def test_editor_nonzero_exit_aborts(monkeypatch, tmp_path) -> None:
    # editor exits non-zero (e.g. vim ":cq") → treated as abort, no traceback
    _fake_editor("import sys\nsys.exit(1)\n", monkeypatch, tmp_path)
    assert _editor.edit_toml("x = 1\n", validate=lambda _t: None) is None


def test_uses_editor_env_fallback(monkeypatch, tmp_path) -> None:
    # VISUAL unset, EDITOR set: helper falls back to $EDITOR
    editor = tmp_path / "fake-editor.py"
    editor.write_text(
        'import sys\np = sys.argv[1]\nopen(p, "a").write(\'switch = "aa"\\n\')\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.setenv("EDITOR", f"python {editor}")
    out = _editor.edit_toml('base_url = "https://h"\n', validate=lambda _t: None)
    assert out is not None
    assert 'switch = "aa"' in out


def test_reopens_on_validation_error_then_succeeds(monkeypatch, tmp_path) -> None:
    # editor makes a change each invocation; validate fails once, then passes
    _fake_editor(
        'import sys\np = sys.argv[1]\nopen(p, "a").write("\\n# edited\\n")\n',
        monkeypatch,
        tmp_path,
    )
    calls = []

    def fail_once_then_pass(text: str) -> None:
        calls.append(text)
        if len(calls) == 1:
            raise ConfigError("bad")

    out = _editor.edit_toml("base_url = 1\n", validate=fail_once_then_pass)
    assert out is not None
    assert len(calls) == 2
