## Decision: resolve `list devices` IP from `lan_ip`, fall back to `ip`

`device_summary()` resolves a device's LAN address as `lan_ip or ip`, with no
device-type check, and carries the gateway's public address separately as
`wan_ip` (from `last_wan_ip`), surfaced only under `list devices --wan`.

## Context

`unifictl list devices` showed the UDM Pro's **WAN** address (a public IP) in
the `IP` column while every switch and AP showed a LAN address. unifictl was
not transforming anything: `client.get_devices()` returns raw `stat/device`
objects and `domain/devices.py` copied `ip` verbatim.

The controller's `ip` field is layered, not ambiguous. Probing the live UDM Pro
(read-only, 7 adopted devices) confirmed:

| field                | `uap` x4 | `usw` x2 | `udm`         |
| -------------------- | -------- | -------- | ------------- |
| `ip`                 | LAN      | LAN      | **WAN**       |
| `lan_ip`             | absent   | absent   | `192.168.1.1` |
| `last_wan_ip`        | absent   | absent   | WAN           |
| `connect_request_ip` | LAN      | LAN      | `127.0.0.1`   |

`lan_ip` is present on exactly the device where `ip` is not the LAN address,
and absent everywhere else. Three sources agree on the gateway's LAN address
(`lan_ip`, `reported_networks[br0].ip`, `network_table[].ip_subnet`), and every
other device independently reports `inform_ip: 192.168.1.1`.

## Alternatives considered

- **Branch on `type == "udm"`.** The obvious fix. Rejected: it hardcodes a
  gateway model list that silently breaks on `ugw`, `uxg`, `uxg-pro`, and every
  future gateway. `lan_ip`'s presence is the same signal, supplied by the API.
- **`config_network.ip`.** A near-miss worth recording. On the live UDM it reads
  `{"ip": "192.168.1.125", "type": "dhcp"}` — stale controller-management
  config, **not** the gateway's LAN address (`192.168.1.1`). A plausible,
  confidently-wrong field: it would have produced an IP that looks right.
- **`connect_request_ip`.** Correct on 6/7 devices, `127.0.0.1` on the UDM
  because the controller runs on the gateway itself. Fails precisely on the one
  device the fix exists for.
- **Rename the column instead of fixing the value.** Cheap and honest, but
  leaves the table mixing address families across rows.
- **Show WAN always / only when populated / not at all.** A permanent column is
  blank for 6/7 devices; a conditional column makes the table shape
  data-dependent and harder to diff across sites.

## Reasoning

`lan_ip or ip` uses one API-supplied signal to disambiguate both fields, keeps
`device_summary()` type-agnostic, and degrades correctly on hardware we have
not seen: absent `lan_ip` means `ip` was already the LAN address.

`--wan` keeps the lean default table the read-commands design specified while
making the public address reachable without `jq`. The `-` placeholder lives in
`_render_devices`, not the domain — `wan_ip` stays `""` so `--json` and the
dataclass report absence honestly, and the import-linter DDD contract holds.

## Trade-offs accepted

- `wan_ip` reads `last_wan_ip`, whose name implies it may be the *last known*
  address rather than the current one. Chosen over inferring WAN from `ip`
  (when `lan_ip` is present) because it names what it returns. On the live UDM
  all four WAN sources agreed; if a stale value is ever observed after a WAN
  drop, `uplink.ip` is the alternative.
- `--wan` widens the table enough that Rich truncates long device names at 80
  columns.
- `list devices --json` is unchanged and still reports the gateway's WAN in
  `ip`. That is correct for a raw passthrough, but means table and JSON differ
  for that one field — deliberate, since `--json` promises raw objects.

## Defences added

Every fixture in the suite was a switch, so no test exercised a device where
`ip` and `lan_ip` diverge. Added gateway cases to `tests/test_devices.py` and
`tests/test_list_command.py`, using RFC 5737 documentation addresses
(`203.0.113.0/24`) rather than the real WAN IP, so a home address is never
committed to a public repo.
