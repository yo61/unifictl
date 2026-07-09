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
  the Integration API** — it lives only on the **private/legacy session
  controller API** (`/proxy/network/api/s/<site>/rest/device/<id>`).
- `unifi-mcp` plans to reach that legacy API too, but for **reads**. So the line
  between the two tools is *reads vs. imperative actions*, not *which API each
  one touches* — both end up speaking the legacy API. Reads → `unifi-mcp`;
  actions → `unifictl`.
- So `unifictl` is the imperative companion to `unifi-mcp`: same gateway, same
  API key, but it hits the private API to *do* things the Integration API can't
  describe.

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

## Shared library with `unifi-mcp`

Once `unifi-mcp` also speaks the legacy REST API, the client code stops being
unifictl-specific: connection + `UNIFI_*` settings, API-key/session auth,
TLS/CA handling, timeouts, and the read-modify-write device primitives are
identical on both sides. That overlap is exact enough to justify a **shared
library** (working name `unifi-core`, TBD) that both tools depend on.

- **In the library** — `UnifiClient` (httpx): settings, auth, TLS/CA, and the
  low-level Integration + legacy REST calls; plus shared `Device` /
  `PortOverride` models.
- **Stays in `unifictl`** — the LAG domain rule (the pure `port_overrides`
  transform), the `set_aggregation` use-case, and the cyclopts `lag` command.
- **Stays in `unifi-mcp`** — the MCP server, tool definitions, read models.

**Minimum commitment now: keep the client isolated so the shared library can be
swapped in later.** The `infrastructure/` layer already draws that boundary —
build unifictl's own `UnifiClient` there as a self-contained module (settings +
auth + HTTP + shared models) with no domain/application code leaking in, behind
an interface the rest of the app depends on. Then extracting it into
`unifi-core` — or swapping in unifi-mcp's version — is a *move*, not a rewrite.

Defer the actual extraction until `unifi-mcp`'s legacy-API work is concrete
enough to pin the shared surface: a third package adds cross-repo version
coordination and a release step the single-repo plan avoids, so it's only worth
paying once the interface is stable on both sides.

## ADRs to capture

1. "Use the private/legacy session API for `port_overrides` because the official
   Integration API (used by `unifi-mcp`) does not expose per-port aggregation."
   Records why unifictl is deliberately *not* just another Integration API
   client.
2. "Isolate the UniFi client behind the `infrastructure/` boundary so it can be
   extracted into a shared `unifi-core` library once `unifi-mcp` adopts the
   legacy REST API." Records the reads-vs-actions split and the deferred
   extraction.

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
- Shared library timing: extract `unifi-core` up front, or ship unifictl's own
  isolated `UnifiClient` first and extract once `unifi-mcp`'s legacy-REST work
  pins the shared surface (recommended — keep the boundary, defer the package).

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
