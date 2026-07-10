# Shell completion for `unifictl` — design

**Date:** 2026-07-10
**Status:** Approved design, pre-implementation
**Related:** `jobhound` (the reference implementation this mirrors),
`docs/superpowers/specs/2026-07-10-read-commands-design.md` (the command tree
being completed), `yo61/homebrew-tap` `Formula/unifictl.rb` (deployment).

## Summary

Add `bash`/`zsh`/`fish` tab-completion to `unifictl`, deployed automatically by
the Homebrew formula. Completion covers the static command tree plus dynamic
values fetched live from the UniFi controller (switch MACs, port indices). The
approach mirrors the completion machinery already shipping in `jobhound`.

## Context

`unifictl` is a `*ctl` CLI with a verb-first tree (`set` / `list` / `show`).
`jobhound` — the sibling project that sets the tooling conventions for this repo
and shares the `yo61/homebrew-tap` — already ships a completion system: bundled
per-shell scripts, a `completion` sub-command that prints/installs them, and a
hidden `__complete` handler that emits candidates. We port that system, scaled
to `unifictl`'s smaller tree, and wire completion generation into the formula.

## Architecture

Three new pieces inside `src/unifictl/`:

| Piece | Path | Role |
|---|---|---|
| Bundled shell scripts | `_completion/unifictl.{bash,zsh,fish}` | Static generators that shell out to `unifictl __complete <shell> …` and defer path completion to the shell on a sentinel |
| `completion` sub-App | `commands/completion.py` | `unifictl completion bash\|zsh\|fish` (print) + `install` (write) + `maybe_refresh_installed_stubs()` |
| Hidden `__complete` handler | `commands/_complete.py` | The completion engine — emits candidates for the tokens typed so far |

Plus wiring in `cli.py` and one manual edit to `Formula/unifictl.rb` in the
`yo61/homebrew-tap` repo.

## The completion surface

The full static tree:

```
top-level:  set   list   show   completion            (+ --help / --version)
set  → lag                  set lag <state>            state: on | off
list → devices
show → port                 show port <port_idx>
completion → bash  fish  zsh  install
```

Candidate rules:

- **Command tree** — at any node with no leftover tokens, emit the visible
  sub-command names at that depth.
- **Fixed positional** — `set lag <TAB>` → `on` `off`.
- **Fixed flag value** — `completion install --shell <TAB>` → `bash` `fish` `zsh`.
- **Local-path flag** — `completion install --dest <TAB>` → emit the
  `__UNIFICTL_COMPLETE_FILES__` sentinel; the shell stub translates it into
  native directory completion (bash `compopt -o default`, zsh `_files`, fish
  `__fish_complete_path`).
- **Dynamic switch MACs** (network) — `--switch <TAB>` on `("set","lag")` and
  `("show","port")` → MACs of devices whose `type == "usw"` (switch).
- **Dynamic port indices** (network) — `show port <TAB>` (positional 0) and
  `set lag --leader <TAB>` → `port_idx` values from the resolved switch's
  `port_table`. The switch is resolved from an already-typed `--switch` value,
  falling back to `settings.switch` (config/env default). Unresolvable switch →
  no candidates.

## Data flow

```
$ unifictl show port --switch AA:BB <TAB>
  → shell stub runs:  unifictl __complete zsh unifictl show port --switch AA:BB ''
  → cli.main() fast-path sees argv[1] == "__complete"
      → dispatches to _complete.run() BEFORE building the cyclopts App
        (skips the questionary import; keeps TAB instant)
  → _complete.run() walks the static tree → ("show","port"), positional 0
  → port-index branch → resolve switch (AA:BB from --switch) → fetch port_table
  → prints one port_idx per line → stub feeds them to the completion system
```

The `__complete` first argument is the shell name (reserved for future per-shell
output differences); the remaining tokens are the command line typed so far,
where the first is always `unifictl` and the last is the partial being completed
(possibly empty).

## Safety: network completion must never hang or error the shell

Live controller completion is only acceptable if a slow, unreachable, or
unconfigured controller degrades to *no candidates* rather than a frozen or
noisy shell. The device-fetch helper:

1. `load_settings()`; on `ConfigError` (missing creds) → return `[]` silently.
2. Build the client from
   `dataclasses.replace(settings, timeout_ms=min(settings.timeout_ms, 2000))` —
   a hard 2s ceiling so an unreachable controller fails fast regardless of the
   configured timeout.
3. `try: client.get_devices() … except Exception: return []`, always
   `client.close()` in a `finally`.

`get_devices()` is a read-only GET, so completion has no side effects. Worst
case on a down controller: ≤2s wait, empty candidate list.

## Installation, detection, and self-heal

`completion install` mirrors jobhound:

- Detect the shell from `$SHELL` (`--shell` overrides).
- Default install dirs: bash
  `~/.local/share/bash-completion/completions/unifictl`; fish
  `~/.config/fish/completions/unifictl.fish`; zsh honors `$ZDOTDIR`
  (`$ZDOTDIR/completions/_unifictl`) and falls back to `~/.zfunc/_unifictl`.
  `--dest` overrides the directory.
- No-op when the target already matches the bundled script; otherwise back up an
  existing file to `<name>.bak` and write the new one.
- Print a per-shell activation hint.

`maybe_refresh_installed_stubs()` runs on every normal (non-`__complete`)
invocation from `main()`: for each shell whose stub already exists at a
conventional path, rewrite it (with a `.bak` backup) if it has drifted from the
bundled copy. It never installs for users who never ran `install`, and swallows
`OSError` so a hostile filesystem can't make every `unifictl` run noisy. This
keeps uv-tool/pip installs current after an upgrade; Homebrew installs are
refreshed by `brew upgrade` regenerating the completions.

## Packaging

hatchling with `packages = ["src/unifictl"]` bundles the non-`.py` scripts under
the package directory automatically — jobhound relies on the same default with
no package-data configuration. A resources-readability test guards against a
packaging regression, and `uv build` + wheel inspection confirms the scripts
ship in the sdist and wheel.

## Homebrew deployment (repo: `yo61/homebrew-tap`)

One manual edit to `Formula/unifictl.rb`. It survives every future auto-bump:
the tap's `bump-unifictl` workflow only runs `brew bump-formula-pr`
(url/sha256) and `brew update-python-resources` (resource blocks), neither of
which touches `def install` or `test do`.

```ruby
def install
  virtualenv_install_with_resources
  # `unifictl completion <shell>` takes the shell positionally, matching the
  # default shell_parameter_format (nil) that passes the bare shell name.
  generate_completions_from_executable(bin/"unifictl", "completion")
end

test do
  assert_equal version.to_s, shell_output("#{bin}/unifictl --version").strip
  assert_match "#compdef unifictl", shell_output("#{bin}/unifictl completion zsh")
end
```

This edit lands only after a `unifictl` release that *contains* the `completion`
command is published to PyPI, so it is sequenced as a distinct final step.

## Testing (TDD)

- `tests/test_complete.py` — the `__complete` handler: tree emission at each
  depth; fixed positional/flag value sets; the `--dest` FILES sentinel; switch
  MAC and port-index completion with a mocked client; and the
  unreachable/unconfigured-controller → empty path.
- `tests/test_cmd_completion.py` — install/refresh: shell detection, `$ZDOTDIR`
  zsh path, backup-on-overwrite, idempotent no-op, drift refresh.
- `tests/test_completion_scripts.py` — bundled scripts are present and readable
  via `importlib.resources`, contain `#compdef unifictl`, and reference the
  FILES sentinel.

## Non-goals

- Completing non-switch device MACs, or values requiring more than one network
  round-trip.
- Descriptions/rich columns in zsh completion (the `shell` arg is reserved for
  this but unused).
- Reimplementing glob/tilde expansion in Python — path completion defers to the
  shell via the sentinel.
