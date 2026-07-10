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

    # Unlike maybe_refresh_installed_stubs (a silent background hook), install is
    # user-invoked and foreground: let a read error (e.g. permissions) surface as
    # actionable feedback rather than swallowing it here.
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
            print(
                f"unifictl: refreshed {shell} completion stub at {target}",
                file=sys.stderr,
            )
