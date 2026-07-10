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
