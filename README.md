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

Connection and secrets come from the environment or a selected profile (see
Profiles & credentials below); env vars are never committed and take precedence
over profile values. Matching `unifi-mcp`:

| Variable | Purpose |
| --- | --- |
| `UNIFI_BASE_URL` | Gateway address, e.g. `https://192.168.1.1` |
| `UNIFI_API_KEY` | Integration API key (also authenticates the private endpoints) |
| `UNIFI_SITE` | Controller site (default `default`) |
| `UNIFI_CA_CERT` | Optional path to the controller CA certificate (PEM) |
| `UNIFI_INSECURE_TLS` | Last-resort TLS bypass |
| `UNIFI_TIMEOUT_MS` | Per-request timeout (default `30000`) |

LAG leader ports live in an XDG TOML file at `~/.config/unifictl/config.toml`
(`leaders = [1, 2]`); CLI flags override them. The switch MAC is a profile field
(see below), not a `config.toml` setting.

### Profiles & credentials

Point `unifictl` at different targets with named profiles. Non-secret config lives
one-file-per-profile under `~/.config/unifictl/profiles/`; the API key lives in a
separate `~/.config/unifictl/credentials.toml` (`0600`, the only secret file):

```toml
# ~/.config/unifictl/profiles/home.toml   (safe to share)
base_url = "https://192.168.1.1"
switch   = "aa:bb:cc:dd:ee:ff"
# credential = "default"      # which credentials.toml section holds the key
```

```toml
# ~/.config/unifictl/credentials.toml      (chmod 600)
[default]
api_key = "…"
```

A profile's `credential` defaults to `default`, so one controller/key backs many
per-switch profiles with no duplication. Select a profile with `--profile NAME`,
`UNIFI_PROFILE`, or `profile activate NAME` (writes `default_profile`). Fields
resolve `CLI > env > profile > built-in`; the api_key resolves
`UNIFI_API_KEY > credentials[credential] > error`.

```sh
unifictl profile create home        # opens $VISUAL or $EDITOR for the non-secret
                                     # fields, then prompts (hidden) for the API key
unifictl profile list
unifictl profile describe home       # fields + redacted key
unifictl profile set home switch aa:bb:cc:dd:ee:ff
unifictl profile activate home
unifictl credential set default      # rotate the shared key, once
unifictl credential list
```

## Development

```sh
uv sync                 # create the venv and install deps
task dev:check          # lint, format-check, typecheck, import boundaries, tests
task dev:hooks-install  # install git hooks (prek)
```

See `SPEC.md` for the build reference and `decisions/` for the architecture
decision records.
