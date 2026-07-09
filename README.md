# unifictl

Imperative UniFi homelab actions that the official Integration API can't
express. Companion to [`unifi-mcp`](https://github.com/yo61/unifi-mcp) (reads):
same gateway, same API key, but `unifictl` hits the private controller API to
*do* things — starting with toggling switch-port link aggregation around
PXE-booting cluster nodes.

> **Status: scaffold.** The project structure, tooling, and CLI wiring are in
> place; the `set lag` feature logic is stubbed and built next (see `SPEC.md`).

## Install

```sh
uv tool install unifictl        # or: pipx install unifictl
```

## Usage

```sh
unifictl set lag off            # dissolve the LAGs so nodes can PXE boot
unifictl set lag on             # restore the LACP bonds
unifictl set lag off --dry-run  # print the computed change, apply nothing
```

A real apply prints the diff, prompts for confirmation, and snapshots the
switch's current `port_overrides` to a timestamped backup before writing.

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

Operational parameters (switch MAC, LAG leader ports, ports-per-LAG) live in an
XDG TOML file at `~/.config/unifictl/config.toml`; CLI flags override them.

## Development

```sh
uv sync                 # create the venv and install deps
task dev:check          # lint, format-check, typecheck, import boundaries, tests
task dev:hooks-install  # install git hooks (prek)
```

See `SPEC.md` for the build reference and `decisions/` for the architecture
decision records.
