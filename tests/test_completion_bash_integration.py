"""Drive the bundled bash completion through a real interactive bash.

The bash script's job is to hand ``__complete`` the words the user actually
typed. That contract cannot be checked by reading the script: bash splits
``COMP_WORDS`` on ``COMP_WORDBREAKS`` (which contains ``:``), so a partially
typed MAC arrives fragmented unless ``_init_completion``'s repaired ``words``
are used. Only a real readline session exercises that.

Requires bash 4+ (for ``mapfile``) and bash-completion; skipped otherwise, so
the suite still runs on a machine without them.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

pexpect = pytest.importorskip("pexpect", reason="pexpect drives the interactive bash")

_SCRIPT = Path(__file__).parent.parent / "src" / "unifictl" / "_completion" / "unifictl.bash"

# Candidates the stub emits, standing in for the Python fast path (unit-tested
# separately in test_complete.py). Colons are the point: they are what bash
# splits on.
_MACS = ("70:a7:41:90:82:dd", "70:a7:41:90:82:ee")

_STUB = """\
#!/bin/bash
[[ "$1" == "__complete" ]] || exit 0
shift 2
args=("$@")
n=${#args[@]}
last=""; prev=""
((n >= 1)) && last="${args[n-1]}"
((n >= 2)) && prev="${args[n-2]}"
case "$prev" in
  --switch) printf '%s\\n' "70:a7:41:90:82:dd" "70:a7:41:90:82:ee"; exit ;;
  --dest) echo "__UNIFICTL_COMPLETE_FILES__"; exit ;;
  --shell) printf '%s\\n' bash fish zsh; exit ;;
esac
case "$last" in
  -*) printf '%s\\n' "--switch" "--json"; exit ;;
esac
printf '%s\\n' set list show completion profile credential
"""


def _find_bash() -> str | None:
    """A bash with ``mapfile`` (4.0+); macOS ships 3.2 at /bin/bash."""
    candidates = [shutil.which("bash"), "/opt/homebrew/bin/bash", "/usr/local/bin/bash"]
    for path in candidates:
        if not path or not os.path.exists(path):
            continue
        probe = subprocess.run(
            [path, "-c", "declare -F mapfile > /dev/null || type -t mapfile"],
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            return path
    return None


def _find_bash_completion() -> str | None:
    """The bash-completion loader, if this machine has one installed."""
    known = [
        "/opt/homebrew/etc/profile.d/bash_completion.sh",
        "/usr/local/etc/profile.d/bash_completion.sh",
        "/usr/share/bash-completion/bash_completion",
        "/etc/bash_completion",
    ]
    return next((p for p in known if os.path.exists(p)), None)


_BASH = _find_bash()
_BASH_COMPLETION = _find_bash_completion()

pytestmark = pytest.mark.skipif(
    _BASH is None or _BASH_COMPLETION is None,
    reason="needs bash 4+ and bash-completion",
)


@pytest.fixture(scope="module")
def rcfile(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A bashrc that puts the stub on PATH and sources the bundled script."""
    root = tmp_path_factory.mktemp("bashrc")
    bindir = root / "bin"
    bindir.mkdir()
    stub = bindir / "unifictl"
    stub.write_text(_STUB, encoding="utf-8")
    stub.chmod(0o755)
    rc = root / "bashrc"
    rc.write_text(
        textwrap.dedent(f"""\
            PS1='@@ '
            export PATH="{bindir}:$PATH"
            source {_BASH_COMPLETION}
            source {_SCRIPT}
            """),
        encoding="utf-8",
    )
    return rc


@pytest.fixture
def complete(rcfile: Path):
    """Type a line, press TAB, and return what bash put on the screen.

    A fresh bash per case: sharing one session desynchronises, because the
    marker used to detect "readline has finished" also appears in bash's echo
    of the command that prints it, so screens leak between cases.
    """

    def _run(line: str) -> str:
        child = pexpect.spawn(
            str(_BASH),
            ["--rcfile", str(rcfile), "-i"],
            timeout=15,
            encoding="utf-8",
            dimensions=(40, 220),
        )
        try:
            child.expect("@@ ")
            child.send(line + "\t")
            # No deterministic end-of-completion signal exists: readline redraws
            # the line in place and prints nothing to mark it done.
            child.expect(pexpect.TIMEOUT, timeout=1.5)
            return child.before or ""
        finally:
            child.close(force=True)

    return _run


def test_top_level_commands_are_offered(complete) -> None:
    screen = complete("unifictl ")
    assert "credential" in screen
    assert "completion" in screen


def test_flag_names_are_offered(complete) -> None:
    assert "--switch" in complete("unifictl show port -")


def test_mac_candidates_offered_for_empty_value(complete) -> None:
    screen = complete("unifictl show port --switch ")
    assert all(mac in screen for mac in _MACS)


def test_partial_mac_still_offers_candidates(complete) -> None:
    # The regression: bash splits `70:a7` into `70 : a7`, so filtering against
    # COMP_WORDS[COMP_CWORD] ('a7') discarded every candidate and rang the bell.
    screen = complete("unifictl show port --switch 70:a7")
    assert "\x07" not in screen, "bell: no candidates survived filtering"
    # Displayed trimmed to the segment after the last colon, as bash does for
    # any colon-bearing word.
    assert "a7:41:90:82:dd" in screen


def test_partial_mac_completes_to_the_full_value(complete) -> None:
    screen = complete("unifictl show port --switch 70:a7:41:90:82:d")
    assert "\x07" not in screen
    assert "70:a7:41:90:82:dd" in screen


def test_fixed_flag_values_are_offered(complete) -> None:
    screen = complete("unifictl completion install --shell ")
    assert "fish" in screen and "zsh" in screen


def test_files_sentinel_defers_to_native_path_completion(complete) -> None:
    assert "/tmp/" in complete("unifictl completion install --dest /tm")
