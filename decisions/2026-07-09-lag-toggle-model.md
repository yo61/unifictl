## Decision: A LAG toggle is a pure op_mode flip on the leader port

Model a LAG as living entirely on its **leader** port's override:
`op_mode: aggregate` + `aggregate_members` (+ a controller-managed `lag_idx`).
`set lag on`/`off` flips **only** `op_mode` on the named leader ports and changes
nothing else. The `--leader` flag (and the `leaders` config key) names the leader
ports. There is no `num_ports`/`aggregate_num_ports` and no notion of pairs.

## Context

The initial `SPEC.md` "LAG domain rule" assumed aggregation was expressed as
`op_mode: aggregate` + `aggregate_num_ports = N` (contiguous from the leader).
Live data from the UDM Pro contradicted this — leaders store
`aggregate_members: [17, 18]` (an explicit member list) + `lag_idx`, with **no**
`aggregate_num_ports`. Rather than guess how toggling behaves, we ran
experiments on empty lab ports 1/2/3.

## Alternatives considered:

- **`aggregate_num_ports` model** (the original spec) — contradicted by the
  hardware; the field does not exist on this firmware.
- **`on` supplies member pairs/groups** — treat `on` as *forming* LAGs, so it
  needs the membership. Heavier interface; overlaps Terraform's declarative role.
- **`op_mode`-flip toggle** (chosen) — the tool only flips `op_mode`; the
  controller owns membership persistence and `lag_idx`.

## Reasoning

Two experiments on a live UDM Pro USW-24-PoE (`scratchpad/lag3_probe.sh`,
`lag_roundtrip.sh`) established:

- A LAG accepts an **arbitrary-length** member list — a 3-port `aggregate_members`
  was accepted (not pairs-only). The LAG is defined solely on the leader's
  override; the other members get **no override of their own** (passive).
- Setting the leader to `op_mode: switch` **dissolves** the LAG; members follow
  automatically. `aggregate_members` **persists** (dormant); the controller
  **drops `lag_idx`**.
- Setting the leader back to `op_mode: aggregate` **reforms** the LAG from the
  persisted `aggregate_members` and the controller **re-assigns `lag_idx`** — no
  members or `lag_idx` need re-supplying.

So restoring is a pure `op_mode` flip: the membership survives the toggle. The
tool therefore reads the device, flips `op_mode` on the named leaders, preserves
everything else, and writes the whole array back.

## Trade-offs accepted:

- The tool only **toggles pre-existing LAGs**; it cannot create one from scratch
  (that needs the member list — steady-state/Terraform territory, as the proposal
  defers). Toggling a leader that has no override raises `UnknownLeaderError`.
- `lag_idx` is left to the controller; the tool never sets it.

## Supersedes:

The `SPEC.md` "LAG domain rule" (`aggregate_num_ports`, contiguous-from-leader)
and the `num_ports` / `--num-ports` design in
`decisions/2026-07-09-private-api-auth.md`'s sibling spec. Grounded now in
observed controller behaviour, not assumption.
