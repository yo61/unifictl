# Read commands: `list devices` and `show port` — design

**Date:** 2026-07-10
**Status:** Approved design, pre-implementation
**Related:** `SPEC.md` (the `set lag` feature this mirrors),
`decisions/2026-07-09-lag-toggle-model.md` (the aggregation model these reads
reuse).

## Summary

Add two read-only commands to `unifictl`:

- `unifictl list devices` — every adopted device with its MAC.
- `unifictl show port <n> --switch <mac>` — one port's configuration, and if the
  port is aggregated, which port leads the LAG.

## Context — a deliberate scope shift

The original proposal split responsibilities as *reads → `unifi-mcp`, actions →
`unifictl`*. These commands are reads, so they cross that line **on purpose**:
`unifi-mcp` is an MCP server for agents, not a CLI a human can run at a terminal,
and the goal is for `unifictl` to grow into a fuller UniFi device CLI (see the
`unifi-cli-device-setup-goal` project memory). So `unifictl` becomes
reads-*and*-actions. These two also close a usability gap in the imperative tool:
`list devices` surfaces the `--switch` MAC, and `show port` finds leaders before
you run `set lag`.

## Commands

Verb-first sub-apps, exactly like `set lag`. The verb vocabulary becomes
`set` / `list` / `show`.

```sh
unifictl list devices                    # table: NAME MODEL TYPE MAC IP
unifictl list devices --json             # raw device objects for jq

unifictl show port 18 --switch <mac>     # member -> reports leader 17
unifictl show port 17 --switch <mac>     # leader -> lists members
unifictl show port 3  --switch <mac>     # standalone
unifictl show port 17 --switch <mac> --json
```

`--switch` falls back to config/env, same as `set lag`.

### `list devices` output

Lean default table; `--json` carries everything.

```
NAME            MODEL   TYPE  MAC                IP
USW 24 PoE      USL24P  usw   70:a7:41:90:82:dd  192.168.1.x
UDM Pro         ...     ugw   ...                ...
```

### `show port` output

Pretty-printed port override plus one aggregation line; `--json` for raw.

```
port 18: member of LAG — leader 17, members [17, 18]
  overrides: (none; controller defaults)

port 17: LAG leader — members [17, 18]
  overrides: op_mode=aggregate, name="Port 17", poe_mode=auto, ...
```

## Architecture (DDD, mirrors the `set lag` feature)

- **commands/list.py** — `list` sub-app + `devices` command. Thin adapter:
  fetch via service, render a `rich` table or `--json`.
- **commands/show.py** — `show` sub-app + `port` command. Thin adapter: render
  the port override + aggregation line, or `--json`.
- **application/device_service.py** —
  - `list_devices(client) -> list[DeviceSummary]`
  - `describe_switch_port(client, switch_mac, port_idx) -> PortDescription`

  Thin fetch → domain-map orchestration; no cyclopts/httpx types leak in.
- **domain/** — the pure, testable heart:
  - `device_summary(raw_device) -> DeviceSummary(name, model, type, mac, ip)` —
    extraction from a raw device dict.
  - `describe_port(port_overrides, port_idx) -> PortDescription(port_idx, role,
    leader_port, members, override)`, `role ∈ {leader, member, standalone}`:
    - target has an override with `op_mode == "aggregate"` → **leader**,
      `members = aggregate_members`, `leader_port = port_idx`;
    - else target appears in some aggregate leader's `aggregate_members` →
      **member**, `leader_port =` that leader, `members =` its members;
    - else **standalone**, `leader_port = None`, `members = []`.

    `override` is the target port's own entry from `port_overrides` (or `None`).
- **infrastructure/client.py** — add `get_devices() -> list[dict]`
  (`GET /proxy/network/api/s/<site>/stat/device`, no MAC → all devices).
  `get_device(mac)` already exists and serves `show port`.

The import-linter contracts are unchanged: `domain` stays pure, `infrastructure`
imports neither `domain` nor `application`, `commands → application → domain`.

## Data flow

- **list devices:** `get_devices()` → `device_summary` per device → table/JSON.
- **show port:** `get_device(mac)` → `describe_port(device["port_overrides"], n)`
  → formatted/JSON.

## Error handling

Reuse `main()`'s exception net (clean `unifictl: <message>` + exit 1):

- No switch given for `show port` and none in config → `ConfigError` (as
  `set lag`).
- Switch MAC not found → `UnifiClientError` (existing "no device found").
- `show port <n>` where the device has no such port index → a clear error
  (`port <n> not found on <mac>`). A standalone port with no override is **not**
  an error — it reports `standalone` with `override: none`.

## Read-only — simpler than writes

No backup, no confirmation, no `--dry-run`. These commands never PUT.

## Testing

- **domain (examples + hypothesis):** `describe_port` — a port is exactly one of
  leader / member / standalone; a member's `leader_port` is always an aggregate
  leader; a leader lists itself among `members`; input never mutated.
  `device_summary` — field extraction incl. missing-field tolerance.
- **infrastructure:** `get_devices` via `pytest-httpx` (URL, API-key header,
  data-envelope unwrap).
- **commands:** mocked service — table vs `--json`, `--switch` config fallback,
  the not-found error paths.
- **e2e:** through the CLI against mocked HTTP, one per command.

## Out of scope

- `list ports`, `list networks`, other resources (future slope).
- Any write/mutation of ports (that's `set …`).
- Live device status/metrics beyond the lean columns (`--json` carries raw).
