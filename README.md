# unifictl

Imperative UniFi homelab actions that the official Integration API can't
express. Companion to [`unifi-mcp`](https://github.com/yo61/unifi-mcp) (reads):
same gateway, same API key, but `unifictl` hits the private controller API to
*do* things — starting with toggling switch-port link aggregation (LACP LAGs).

> **Status: `set lag` implemented.** The first feature works end-to-end against
> the private controller API (API-key auth). See `SPEC.md` for the design and
> `decisions/` for the architecture decision records.

## Install

```sh
uv tool install unifictl        # or: pipx install unifictl
```

## Usage

```sh
unifictl set lag off            # dissolve the LAGs on the leader ports
unifictl set lag on             # restore the LACP bonds
unifictl set lag off --dry-run  # print the computed change, apply nothing
```

A real apply prints the diff, prompts for confirmation, and snapshots the
switch's current `port_overrides` to a timestamped backup before writing.

## Shell completion

`unifictl` ships bash, zsh, and fish completion. The Homebrew formula installs
it automatically. For `uv tool`/`pipx` installs, run:

```sh
unifictl completion install          # detects your shell from $SHELL
unifictl completion install --shell zsh
```

Or print a script to wire up manually. For zsh, write it as `_unifictl` into a
directory on your `$fpath` — the default is `~/.zfunc`:

```sh
unifictl completion zsh > ~/.zfunc/_unifictl
# then in ~/.zshrc:  fpath+=~/.zfunc && autoload -U compinit && compinit
```

Completion covers the command tree, `set lag on|off`, and — when your
controller is reachable — switch MACs (`--switch`) and port indices
(`show port`, `set lag --leader`). A slow or unreachable controller yields no
candidates rather than blocking your shell.

## Configuration

Connection and secrets come from the environment (never committed), matching
`unifi-mcp`:

| Variable | Purpose |
| --- | --- |
| `UNIFI_BASE_URL` | Gateway address, e.g. `https://192.168.1.1` |
| `UNIFI_API_KEY` | Integration API key (also authenticates the private endpoints) |
| `UNIFI_SITE` | Controller site (default `default`) |
| `UNIFI_CA_CERT` | Optional path to the controller CA certificate (PEM) |
| `UNIFI_INSECURE_TLS` | Last-resort TLS bypass |
| `UNIFI_TIMEOUT_MS` | Per-request timeout (default `30000`) |

Operational parameters (switch MAC and LAG leader ports) live in an
XDG TOML file at `~/.config/unifictl/config.toml`; CLI flags override them.

## Development

```sh
uv sync                 # create the venv and install deps
task dev:check          # lint, format-check, typecheck, import boundaries, tests
task dev:hooks-install  # install git hooks (prek)
```

See `SPEC.md` for the build reference and `decisions/` for the architecture
decision records.
