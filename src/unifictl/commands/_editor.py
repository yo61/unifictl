"""Launch ``$EDITOR`` on a temp file with a validate-on-save loop.

Used by ``profile create``/``edit`` for the non-secret profile file. The API key
never passes through here — it is prompted separately.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from unifictl.infrastructure.config import ConfigError


def _editor_command() -> list[str]:
    raw = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not raw:
        raise ConfigError("no editor configured; set $EDITOR (or $VISUAL)")
    return shlex.split(raw)


def edit_toml(initial: str, validate: Callable[[str], None]) -> str | None:
    """Edit ``initial`` in ``$EDITOR``; re-open on validation failure.

    Args:
        initial: The starting buffer contents.
        validate: Called with the edited text; raises ``ConfigError`` if invalid.

    Returns:
        The validated text, or ``None`` if the user left an invalid buffer
        unchanged (abort).

    Raises:
        ConfigError: if no editor is configured.
    """
    command = _editor_command()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "profile.toml"
        path.write_text(initial, encoding="utf-8")
        previous = initial
        while True:
            subprocess.run([*command, str(path)], check=True)
            text = path.read_text(encoding="utf-8")
            try:
                validate(text)
                return text
            except ConfigError as exc:
                if text == previous:
                    return None  # unchanged after an error → abort
                previous = text
                print(f"invalid: {exc}\nre-opening editor…")
