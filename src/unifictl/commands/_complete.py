"""Hidden `__complete` subcommand — emits completion candidates to stdout.

Invoked by the per-shell scripts under ``unifictl/_completion/``. Output is one
candidate per line; the shell scripts handle quoting and prefix filtering.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable, Iterator

from unifictl.infrastructure.client import UnifiClient
from unifictl.infrastructure.config import load_settings

# Top-level visible commands (the hidden __complete is intentionally absent).
_TOP_LEVEL_COMMANDS: frozenset[str] = frozenset(
    {"set", "list", "show", "completion", "profile", "credential"}
)

# Sub-command names under each grouping command.
_SUB_APP_NAMES: dict[str, frozenset[str]] = {
    "set": frozenset({"lag"}),
    "list": frozenset({"devices"}),
    "show": frozenset({"port"}),
    "completion": frozenset({"bash", "fish", "zsh", "install"}),
    "profile": frozenset(
        {"create", "edit", "set", "unset", "list", "describe", "activate", "delete"}
    ),
    "credential": frozenset({"set", "list", "delete"}),
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

# Hard ceiling on the completion network call so an unreachable controller
# fails fast instead of freezing the shell on TAB.
COMPLETION_TIMEOUT_MS = 2000

# Flags whose value is a switch MAC.
_SWITCH_MAC_FLAGS: frozenset[tuple[tuple[str, ...], str]] = frozenset(
    {
        (("set", "lag"), "--switch"),
        (("show", "port"), "--switch"),
    }
)

# cmd_path -> positional index that is a port index.
_PORT_IDX_AT_POSITION: dict[tuple[str, ...], int] = {
    ("show", "port"): 0,
}

# Flags whose value is a port index.
_PORT_IDX_FLAGS: frozenset[tuple[tuple[str, ...], str]] = frozenset(
    {
        (("set", "lag"), "--leader"),
    }
)

# Commands whose positional 0 is an existing profile name (`create` is excluded:
# it takes a NEW name).
_PROFILE_NAME_COMMANDS: frozenset[tuple[str, ...]] = frozenset(
    {
        ("profile", "describe"),
        ("profile", "edit"),
        ("profile", "set"),
        ("profile", "unset"),
        ("profile", "activate"),
        ("profile", "delete"),
    }
)

# Commands whose positional 0 is an existing credential name.
_CREDENTIAL_NAME_COMMANDS: frozenset[tuple[str, ...]] = frozenset(
    {("credential", "set"), ("credential", "delete")}
)

# (cmd_path, flag) pairs whose value is a profile name (the global --profile).
_PROFILE_NAME_FLAGS: frozenset[tuple[tuple[str, ...], str]] = frozenset({((), "--profile")})

# cmd_path -> primary long-form flag names, in signature order. `()` is global.
# Guarded against drift by tests/test_completion_tree_drift.py.
_FLAG_NAMES: dict[tuple[str, ...], tuple[str, ...]] = {
    (): ("--profile",),
    ("set", "lag"): ("--switch", "--leader", "--dry-run", "--yes"),
    ("show", "port"): ("--switch", "--json"),
    ("list", "devices"): ("--json", "--wan"),
    ("completion", "install"): ("--shell", "--dest"),
    ("profile", "delete"): ("--yes",),
    ("credential", "set"): ("--stdin",),
    ("credential", "delete"): ("--yes",),
}


# Flags that consume the following token as their value, so that token is not
# a positional. Used to locate positional slots when flags are interleaved.
# Invariant: no flag name is value-taking in one command and boolean in
# another, so a flat set (not keyed by command) suffices to skip flag values.
_VALUE_FLAGS: frozenset[str] = frozenset(
    {"--switch", "--leader", "--shell", "--dest", "-d", "--profile"}
)


def _split_flag_token(token: str) -> tuple[str, str | None]:
    """Split a flag token into ``(flag, attached_value)``.

    Cyclopts accepts four spellings for a value-taking flag: ``--switch MAC``,
    ``--switch=MAC``, ``-d PATH`` and the attached short forms ``-dPATH`` and
    ``-d=PATH``. Only the first keeps the value in a token of its own; the rest
    carry it inside the flag token. Completion must unpack them or it will
    mistake the value for a positional and miss the value the user typed.

    Returns ``(token, None)`` for anything that is not a flag carrying a value.

    Args:
        token: A single command-line token.

    Returns:
        The flag name and its attached value, or ``(token, None)``.
    """
    if not token.startswith("-"):
        return token, None
    flag, separator, value = token.partition("=")
    if separator:
        return flag, value
    if token.startswith("--"):
        return token, None
    short = token[:2]
    if len(token) > 2 and short in _VALUE_FLAGS:
        return short, token[2:]
    return token, None


def _iter_positionals(tokens: list[str]) -> Iterator[str]:
    """Yield the true positional arguments in ``tokens``, in order.

    Flags are dropped along with their values, whether the value sits in the
    next token or is attached to the flag itself.
    """
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token.startswith("-"):
            flag, attached = _split_flag_token(token)
            skip_next = attached is None and flag in _VALUE_FLAGS
            continue
        yield token


def _flag_value(tokens: list[str], flag: str) -> str | None:
    """Return the value typed for ``flag``, in any spelling cyclopts accepts.

    Cyclopts rejects a repeated flag, so the first occurrence is the only one.
    """
    for index, token in enumerate(tokens):
        name, attached = _split_flag_token(token)
        if name != flag:
            continue
        if attached is not None:
            return attached
        return tokens[index + 1] if index + 1 < len(tokens) else None
    return None


def _completion_devices() -> list[dict[str, object]]:
    """Fetch raw devices for completion, or ``[]`` on any problem.

    Bounded by ``COMPLETION_TIMEOUT_MS`` and swallows every error so a TAB
    press never hangs or fails: missing config, an unreachable controller, or
    a malformed response all degrade to no candidates.
    """
    from dataclasses import replace

    try:
        settings = load_settings()
    except Exception:
        return []
    settings = replace(settings, timeout_ms=min(settings.timeout_ms, COMPLETION_TIMEOUT_MS))
    client = None
    try:
        client = UnifiClient(settings)
        return client.get_devices()
    except Exception:  # completion must never surface errors: swallow and return []
        return []
    finally:
        if client is not None:
            with contextlib.suppress(Exception):
                client.close()


def _profile_names() -> list[str]:
    """Defined profile names, or ``[]`` on any problem (TAB must never fail)."""
    try:
        from unifictl.infrastructure import profile_store

        return profile_store.list_profile_names()
    except Exception:
        return []


def _profile_existing_keys(name: str) -> list[str]:
    """Keys present in profile ``name``'s document, or ``[]`` on any problem."""
    try:
        from unifictl.infrastructure import profile_store

        return list(profile_store.read_profile(name).keys())
    except Exception:
        return []


def _credential_names() -> list[str]:
    """Defined credential names, or ``[]`` on any problem (TAB must never fail)."""
    try:
        from unifictl.infrastructure import credential_store

        return credential_store.list_credential_names()
    except Exception:
        return []


def _switch_macs() -> list[str]:
    """MACs of adopted switches (``type == 'usw'``)."""
    macs: list[str] = []
    for device in _completion_devices():
        if device.get("type") == "usw":
            mac = device.get("mac")
            if isinstance(mac, str) and mac:
                macs.append(mac)
    return macs


def _resolve_switch(tokens: list[str]) -> str | None:
    """The ``--switch`` value already typed in ``tokens``, else the config default."""
    typed = _flag_value(tokens, "--switch")
    if typed:
        return typed
    try:
        return load_settings().switch
    except Exception:
        return None


def _port_indices(switch_mac: str) -> list[str]:
    """The ``port_idx`` values (as strings) from ``switch_mac``'s ``port_table``."""
    for device in _completion_devices():
        if device.get("mac") == switch_mac:
            table = device.get("port_table", [])
            indices: list[str] = []
            if isinstance(table, list):
                for entry in table:
                    if isinstance(entry, dict) and "port_idx" in entry:
                        indices.append(str(entry.get("port_idx")))
            return indices
    return []


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


def _strip_leading_global_flags(completed: list[str]) -> list[str]:
    """Drop a leading global ``--profile`` and its value before the command walk.

    ``--profile`` is the meta launcher's flag and may precede the subcommand
    (``unifictl --profile home set lag``). Left in place it would derail
    :func:`_walk_static`, which expects a command as the first token. The value
    may be a separate token or attached (``--profile=home``); both are dropped.
    A lone trailing ``--profile`` whose value is being completed is left
    untouched, so the value-completion branch can still offer profile names.
    """
    tokens = list(completed)
    while tokens:
        flag, attached = _split_flag_token(tokens[0])
        if flag != "--profile":
            break
        if attached is not None:
            tokens = tokens[1:]
        elif len(tokens) >= 2:
            tokens = tokens[2:]
        else:
            break
    return tokens


def _visible_at(cmd_path: tuple[str, ...]) -> Iterable[str]:
    """Return the visible command names at the given tree depth."""
    if len(cmd_path) == 0:
        return _TOP_LEVEL_COMMANDS
    if len(cmd_path) == 1:
        return _SUB_APP_NAMES.get(cmd_path[0], frozenset())
    return frozenset()


def _positional_index(tokens: list[str]) -> int:
    """Return the index of the next positional slot in ``tokens``."""
    return sum(1 for _ in _iter_positionals(tokens))


def _nth_positional(tokens: list[str], index: int) -> str | None:
    """Return the value of positional-``index`` in ``tokens``, or ``None``."""
    for count, value in enumerate(_iter_positionals(tokens)):
        if count == index:
            return value
    return None


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
    completed = _strip_leading_global_flags(completed)
    cmd_path, leftover = _walk_static(completed)
    partial = word_list[-1] if len(word_list) > 1 else ""
    if partial.startswith("-"):
        for flag in _FLAG_NAMES.get(cmd_path, ()):
            print(flag)
        return

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
            if (cmd_path, prev) in _SWITCH_MAC_FLAGS:
                for mac in _switch_macs():
                    print(mac)
                return
            if (cmd_path, prev) in _PORT_IDX_FLAGS:
                switch_mac = _resolve_switch(in_positionals[:-1])
                if switch_mac:
                    for port in _port_indices(switch_mac):
                        print(port)
                return
            if (cmd_path, prev) in _PROFILE_NAME_FLAGS:
                for name in _profile_names():
                    print(name)
                return

    if _positional_index(in_positionals) == 0 and cmd_path in _POSITIONAL_FIXED_VALUES:
        for value in _POSITIONAL_FIXED_VALUES[cmd_path]:
            print(value)
        return

    if _positional_index(in_positionals) == 0:
        if cmd_path in _PROFILE_NAME_COMMANDS:
            for name in _profile_names():
                print(name)
            return
        if cmd_path in _CREDENTIAL_NAME_COMMANDS:
            for name in _credential_names():
                print(name)
            return

    if _positional_index(in_positionals) == 1:
        if cmd_path == ("profile", "set"):
            from unifictl.infrastructure.profile_store import PROFILE_KEYS

            for key in sorted(PROFILE_KEYS):
                print(key)
            return
        if cmd_path == ("profile", "unset"):
            name = _nth_positional(in_positionals, 0)
            if name:
                for key in _profile_existing_keys(name):
                    print(key)
            return

    port_position = _PORT_IDX_AT_POSITION.get(cmd_path)
    if port_position is not None and _positional_index(in_positionals) == port_position:
        switch_mac = _resolve_switch(in_positionals)
        if switch_mac:
            for port in _port_indices(switch_mac):
                print(port)
        return

    if not leftover:
        for name in sorted(_visible_at(cmd_path)):
            print(name)
