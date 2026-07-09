# unifictl — proposal

> Status: proposal / not yet built. This file is a hand-off summary; the repo
> will be scaffolded and built out separately following the house Python
> standards (see **Template** below).

A small Python CLI for **imperative** UniFi homelab actions that the official
Integration API can't express. First job: toggle switch-port link aggregation
(LACP LAG) off and on around PXE-booting the Talos k8s nodes.

Working command name: `unifictl` (kubectl/systemctl-style "control" CLI; pairs
with the existing `unifi-mcp`). Short alias TBD — cf. jobhound's `jh`.

## Why it exists (and how it relates to existing tooling)

- **`unifi-mcp`** already covers the *read* side via the official **Integration
  API** (`/proxy/network/integration/v1`), OpenAPI-driven, read-only for now.
- The LAG toggle is a **write to per-port `port_overrides`**, which is **not in
  the Integration API** — and won't be covered by unifi-mcp's future gated
  writes either, because the field simply isn't in that API surface. It lives
  only on the **private/session controller API**
  (`/proxy/network/api/s/<site>/rest/device/<id>`).
- So `unifictl` is the imperative companion to `unifi-mcp`: same gateway, same
  API key, but it hits the private API to *do* things the Integration API can't
  describe. Reads → `unifi-mcp`; actions → `unifictl`.

## First feature: `lag`

```
unifictl lag set off    # dissolve the node LAGs so nodes can PXE boot
unifictl lag set on     # restore the LACP bonds once nodes are in Talos maintenance mode
unifictl lag set off --dry-run   # print the computed port_overrides change, don't apply
```

Bootstrap flow: `lag set off` → PXE the nodes into Talos maintenance mode →
`lag set on`.

**Why the toggle is needed:** an aggregated port runs LACP (802.3ad). During
PXE the NIC firmware brings the link up as a plain access port with no LACP
negotiation, so a port sitting in an active LAG never joins the bundle and
DHCP/TFTP stalls. Breaking the LAG for the boot, then restoring it, is a
time-ordered procedure — which is exactly why it's an imperative CLI action and
not Terraform (see **Deferred**).

## Mechanics (the domain knowledge worth not rediscovering)

- Aggregation is expressed on the LAG **leader** port only:
  `op_mode = "aggregate"` + `aggregate_num_ports = N` (valid 2–8; the group is
  contiguous from the leader). Breaking a LAG = set the leader's
  `op_mode = "switch"`; the member port(s) revert to normal switching.
- `port_overrides` is stored as a **single array on the device**. There is no
  per-port PATCH — you must **read-modify-write**: GET the device, change only
  the target ports in that array, and PUT the whole array back. Any override you
  omit is reset to controller default, so preserve the array.
- Endpoints (private API, UniFi OS proxied under `/proxy/network`):
  - `GET  /proxy/network/api/s/<site>/stat/device/<mac>` → device `_id` + `port_overrides`
  - `PUT  /proxy/network/api/s/<site>/rest/device/<id>`  → `{ "port_overrides": [ ... ] }`
- **Auth:** on UniFi OS the Integration API key also authenticates these session
  HTTP endpoints, so reuse `UNIFI_API_KEY` — no separate login needed. Fallback
  if ever required: username/password session login (cookie + CSRF token).

## Config & secrets (reuse `unifi-mcp` conventions)

Connection/secrets via env (never in git), matching unifi-mcp so both tools
share one setup:

- `UNIFI_BASE_URL` — gateway, e.g. `https://192.168.1.1`
- `UNIFI_API_KEY` — Integration API key (also authenticates the private endpoints)
- `UNIFI_CA_CERT` — optional path to the controller CA cert (PEM)
- `UNIFI_INSECURE_TLS` — last-resort TLS bypass
- `UNIFI_TIMEOUT_MS`, `UNIFI_SITE` (default `default`)

Operational params (safe to commit) via an XDG TOML config (`xdg-base-dirs`,
as in jobhound): switch MAC, leader ports, ports-per-LAG. cyclopts' built-in
Env + TOML config sources resolve these automatically; explicit flags override.

## Proposed shape — mirror `jobhound`

jobhound is the reference: cyclopts CLI, `uv` + `hatchling`, `src/` layout, and
DDD layering. Map this feature onto those layers:

- **domain/** — pure model + rules, no I/O. A `Device`/`PortOverride` model and
  a pure function: given current `port_overrides` + target leader ports + desired
  state, return the new overrides array. Trivially unit-testable (hypothesis).
- **application/** — the `set_aggregation(state, switch, ports)` use-case:
  fetch → transform (domain) → apply, plus the `--dry-run` path.
- **infrastructure/** — `UnifiClient` (httpx) implementing the two private-API
  calls above, API-key auth, TLS/CA handling; settings loaded from env + XDG.
- **commands/** — the cyclopts `lag` command wiring CLI → application, following
  jobhound's `app.command(fn, name=..., group=...)` registration pattern.

Stack to match jobhound exactly: cyclopts (pin, as jobhound pins `4.11.2`),
httpx, rich, xdg-base-dirs, tomli-w; ruff (line-length 100, double quotes,
`E,F,I,UP,B,SIM,RUF`) + `ty` + pytest/pytest-cov/hypothesis; Taskfile
(`dev:lint|fmt|typecheck|test|check`), pre-commit, commitlint, release-please,
mise, `decisions/`, `docs/`, `[project.scripts]` entrypoint.

## First ADR to capture

"Use the private session API for `port_overrides` because the official
Integration API (used by `unifi-mcp`) does not expose per-port aggregation."
Records why unifictl is deliberately *not* just another Integration API client.

## Deferred — Terraform for steady state

Declarative baseline device/port config belongs in Terraform via the
**`filipowm/unifi`** provider (paultyng's is archived; filipowm is the active
fork and manages APs/gateways too, not just switches). Aggregation there is a
`port_override` block: `op_mode = "aggregate"` + `aggregate_num_ports = N` on the
leader — the same underlying fields. Split of responsibility: **Terraform owns
the declarative steady state; `unifictl` owns the imperative bootstrap toggle.**
Not on the critical path now.

## Open decisions for build-out

- Command name/alias: `unifictl` vs a short alias in the `jh` spirit.
- Auth: API key (recommended, matches unifi-mcp) vs session login — build API
  key first, add session only if a needed endpoint rejects the key.
- `lag set on|off` (sub-app) vs a flatter action verb, per jobhound's
  action-based style.
- Distribution: `uv tool` / `pipx` vs a Homebrew formula in `yo61/tap`.

## Reference cyclopts sketch (starting point, not final)

```python
from typing import Literal
import cyclopts
from cyclopts import App

app = App(
    name="unifictl",
    help="Imperative UniFi homelab actions.",
    config=[cyclopts.config.Env("UNIFI_")],  # + XDG TOML source
)

lag = App(name="lag", help="LACP aggregation control (PXE bootstrap helper).")
app.command(lag)

@lag.command
def set(
    state: Literal["on", "off"],
    *,
    switch: str,          # from config/env or --switch
    ports: list[int],     # LAG leader ports, e.g. --ports 11 --ports 13
    num_ports: int = 2,
    dry_run: bool = False,
):
    """Break or restore LAGs so cluster nodes can PXE boot.

    Parameters
    ----------
    state
        ``off`` dissolves the LAGs (nodes PXE as plain access ports);
        ``on`` restores the LACP bonds.
    switch
        MAC of the switch (e.g. the USW 24 PoE).
    ports
        Leader port of each LAG.
    dry_run
        Show the computed port_overrides change without applying.
    """
    op = "aggregate" if state == "on" else "switch"
    # application.set_aggregation(state, switch, ports, num_ports, dry_run=dry_run)
```
