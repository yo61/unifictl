# unifictl — specification

> Derived from `PROPOSAL.md`. This spec pins the decisions needed to scaffold
> and build the first cut: the tool skeleton plus the `lag` feature end-to-end.
> Reference implementation for all conventions: **jobhound**
> (`../jobhound`) — mirror its patterns unless this spec says otherwise.

## 1. Objective

A small Python CLI for **imperative** UniFi homelab actions the official
Integration API can't express. It is the action-side companion to `unifi-mcp`
(reads): same gateway, same API key, but it hits the **private/legacy session
controller API** to *do* things the Integration API can't describe.

- **User:** the homelab operator (single user, single controller), driving a
  bootstrap procedure by hand or from a script.
- **First feature:** toggle switch-port link aggregation (LACP LAG) off and on
  around PXE-booting the Talos k8s nodes. Bootstrap flow:
  `set lag off` → PXE nodes into Talos maintenance mode → `set lag on`.
- **Why a CLI and not Terraform:** breaking a LAG for a boot then restoring it
  is a *time-ordered* procedure, not a steady state. Declarative baseline config
  is deferred to Terraform (`filipowm/unifi`); `unifictl` owns the imperative
  toggle.

### Success criteria

1. `unifictl set lag off` dissolves the configured LAG(s); `set lag on` restores
   them — both via read-modify-write of the device's `port_overrides`.
2. `--dry-run` prints the computed `port_overrides` change and writes nothing.
3. A real apply prints the diff, prompts for confirmation, and snapshots the
   current full `port_overrides` array to a timestamped file **before** the PUT.
4. The domain rule (the `port_overrides` transform) is pure and property-tested.
5. The UniFi client is isolated in `infrastructure/` with no domain/application
   imports, so it can later be extracted into a shared `unifi-core` library.

## 2. Commands

### CLI shape — verb-first

The CLI grammar is **verb-first** (`set <resource> <value>`), consistent with
jobhound's `jh set <field> …` and the kubectl/systemctl "control" CLIs the tool
name evokes. This is a **presentation-layer decision only** — see §3; the
backend stays Domain-Driven regardless of the surface grammar.

```
unifictl set lag off                    # dissolve the node LAG(s) for PXE
unifictl set lag on                     # restore the LACP bond(s)
unifictl set lag off --dry-run          # print computed change, write nothing
unifictl set lag off --switch <mac>     # override the configured switch
unifictl set lag on  --ports 11 --ports 13 --num-ports 2
unifictl set lag off --yes              # skip the confirm prompt (backup still taken)
```

`set` is a cyclopts sub-app; `lag` is a command under it (`set.command(name="lag")`),
exactly as jobhound registers `set priority`, `set company`, etc. The property
being set *is* the command name.

### `set lag` signature

```python
def lag(
    state: Literal["on", "off"],
    /,
    *,
    switch: str | None = None,      # switch MAC; falls back to config/env
    ports: list[int] | None = None, # LAG leader ports; falls back to config
    num_ports: int = 2,             # ports per LAG (valid 2–8, contiguous from leader)
    dry_run: bool = False,
    yes: bool = False,              # skip confirmation; backup is still written
) -> None:
```

- `state` maps to aggregation intent: `on` → leader `op_mode = "aggregate"`;
  `off` → leader `op_mode = "switch"`.
- `switch` / `ports` resolve from config/env when omitted (§5); an explicit flag
  always overrides.
- `on`/`off` **compute** the target overrides from config via the domain rule.
  The pre-write backup is an independent recovery artifact, not the restore path.

### Output & exit codes

Follow jobhound's `main()` net: convert known domain/infra exceptions into a
single clean `unifictl: <message>` stderr line and `exit(1)`; success and
`--dry-run` exit `0`. Human-readable output via `rich`; the dry-run/diff view
shows per-port before → after for the affected ports only.

| Exit | Meaning |
|------|---------|
| 0 | Applied, or dry-run printed, or user declined a no-op |
| 1 | Config/secret missing, device not found, API error, or user declined the write |

## 3. Project structure

`src/` layout, DDD layering, mirroring jobhound. The CLI grammar (§2) lives
entirely in `commands/`; swapping `set lag` for `lag set` would touch no other
layer.

```
src/unifictl/
  cli.py                     # entry point; explicit command registration (jobhound pattern)
  commands/
    set.py                   # `set` sub-app + `lag` command — THIN adapter only
  application/
    lag_service.py           # set_aggregation() use-case: fetch → transform → backup → apply
  domain/
    aggregation.py           # PURE transform + rules (op_mode, num_ports 2–8). No I/O.
    models.py                # Device / PortOverride value objects
  infrastructure/
    client.py                # UnifiClient (httpx) — EXTRACTION-READY, no domain/app imports
    config.py                # load_settings() → frozen Settings (env secrets + XDG TOML)
    backup.py                # timestamped port_overrides snapshot writer
tests/                       # mirrors package structure
```

### Layer responsibilities

- **domain/** — pure model + rules, no I/O. `apply_aggregation(overrides,
  leader_ports, num_ports, enable) -> new_overrides` returns a new
  `port_overrides` array. Enforces: change only the target leader ports,
  preserve every other override untouched, `num_ports` in 2–8. Unit/property
  tested with hypothesis.
- **application/** — `set_aggregation(...)` orchestrates fetch (client) →
  transform (domain) → snapshot (backup) → apply (client), plus the `--dry-run`
  short-circuit. Returns a result carrying before/after/diff for the adapter to
  render. No cyclopts, no httpx types leaking in.
- **infrastructure/** — `UnifiClient` implements the two private-API calls
  (§6), API-key auth, TLS/CA handling. `config.py` loads settings. **Boundary
  rule:** this package imports nothing from `domain/` or `application/`, so it
  lifts cleanly into `unifi-core` later. Enforce with an import-linter contract.
- **commands/** — parse args, run the confirm prompt (`questionary`/`rich`),
  print the diff and result, map exceptions to exit codes. **Zero business
  logic** — same discipline as jobhound's `set.py`.

### Stack (match jobhound exactly)

| purpose | choice |
|---------|--------|
| CLI | `cyclopts==4.11.2` (pinned, as jobhound) |
| HTTP | `httpx>=0.28` |
| output | `rich>=13` |
| prompt | `questionary>=2.0` |
| config | `xdg-base-dirs>=6`, `tomli-w>=1.0` (+ stdlib `tomllib`) |
| build | `uv` + `hatchling`, `src/` layout |
| lint/format | `ruff` (line-length 100, double quotes, `select = E,F,I,UP,B,SIM,RUF`) |
| types | `ty` (strict-by-default) |
| tests | `pytest`, `pytest-cov`, `hypothesis` |
| http tests | `pytest-httpx` (mock the two endpoints) |
| repo tooling | Taskfile (`dev:lint\|fmt\|typecheck\|test\|check`), pre-commit, commitlint, release-please, mise, `decisions/`, `docs/` |
| entry point | `[project.scripts] unifictl = "unifictl.cli:main"` (short alias TBD) |

`requires-python = ">=3.11"` to match jobhound.

## 4. Config, secrets & domain mechanics

### Secret / operational split (a deliberate refinement over jobhound)

unifictl handles secrets jobhound doesn't, so `infrastructure/config.py` splits
them by sensitivity. Mirror jobhound's manual typed loader (frozen dataclass,
`tomllib` read, validation with clear errors) — **not** cyclopts' auto config
sources, so secrets never surface in `--help`.

- **Secrets & connection — env only, never CLI params, never logged:**
  - `UNIFI_BASE_URL` — gateway, e.g. `https://192.168.1.1`
  - `UNIFI_API_KEY` — Integration API key (also authenticates the private endpoints)
  - `UNIFI_CA_CERT` — optional path to the controller CA cert (PEM)
  - `UNIFI_INSECURE_TLS` — last-resort TLS bypass (off by default)
  - `UNIFI_TIMEOUT_MS`, `UNIFI_SITE` (default `default`)
- **Operational params — XDG TOML (`~/.config/unifictl/config.toml`), safe to
  commit an example:** switch MAC, leader ports, ports-per-LAG. Resolution
  order: explicit flag > env > TOML > built-in default.

Auth: reuse `UNIFI_API_KEY` for the private endpoints (works on UniFi OS).
Username/password session login is **deferred** — add only if an endpoint
rejects the key.

### LAG domain rule (bake into `domain/aggregation.py`)

- Aggregation is expressed on the LAG **leader** port only:
  `op_mode = "aggregate"` + `aggregate_num_ports = N` (2–8; group is contiguous
  from the leader). Breaking a LAG = set the leader's `op_mode = "switch"`;
  members revert to normal switching.
- `port_overrides` is a **single array on the device**. There is no per-port
  PATCH: GET the device, mutate only the target ports in that array, PUT the
  whole array back. **Any omitted override resets to controller default — the
  array must be preserved.**

### Endpoints (private API, proxied under `/proxy/network`)

- `GET /proxy/network/api/s/<site>/stat/device/<mac>` → device `_id` + `port_overrides`
- `PUT /proxy/network/api/s/<site>/rest/device/<id>` → `{ "port_overrides": [ ... ] }`

### Write safety — confirm + backup

Every real (non-`--dry-run`) apply:
1. Compute the new array (domain) and render the per-port diff.
2. Prompt `y/N` to confirm, unless `--yes`.
3. Snapshot the **current full `port_overrides` array** to a timestamped file
   under the XDG data dir (`~/.local/share/unifictl/backups/`) **before** the PUT.
4. PUT the whole array; report the outcome.

## 5. Code style

House standards (`~/.claude/CLAUDE.md`) plus jobhound's config:

- Hard limits: ≤100 lines/function, cyclomatic ≤8, ≤5 positional params,
  100-char lines, absolute imports only, Google-style docstrings on non-trivial
  public APIs.
- Zero-warnings policy across `ruff`, `ty`, `pytest` — clean output is the
  baseline. Any suppression needs an inline justification comment.
- Fail fast with actionable messages (operation, input, suggested fix); never
  swallow exceptions. Self-documenting code; no commented-out code.
- Newtypes/value objects over bare primitives in `domain/`; `Literal`/enums for
  states, not boolean flags, where it reads clearer.

## 6. Testing strategy

Tests in `tests/` mirroring the package. Test behavior, not implementation;
cover edges and errors, not just the happy path.

- **domain/ (hypothesis, pure):** properties of `apply_aggregation` — every
  non-target override is preserved byte-for-byte; only leader ports change;
  `on` then `off` returns the original array (round-trip); `off` is idempotent;
  `num_ports` outside 2–8 raises. This is the highest-value test surface.
- **application/:** `set_aggregation` with a mocked `UnifiClient` — asserts
  fetch → transform → apply ordering; `--dry-run` issues **no** PUT; the backup
  is written **before** the PUT; the returned diff matches.
- **infrastructure/:** `pytest-httpx` mocking the two endpoints — correct URLs,
  API-key auth header, whole-array PUT body, CA/TLS handling; `config.py`
  raises typed errors on malformed TOML/env and honours the resolution order.
- **commands/:** invoke the cyclopts app with monkeypatched `sys.argv`
  (jobhound pattern) — output, exit codes, confirm-prompt accept/decline, and
  that `--yes` skips the prompt but still triggers a backup.
- Verify tests catch failures (break code → test fails → fix). Consider
  `mutmut` on `domain/`.

## 7. Boundaries

### Always

- Preserve the full `port_overrides` array (read-modify-write); mutate only the
  target leader ports.
- Take a timestamped backup of the full array before any PUT.
- Load secrets from env only; never print/log the API key; never register
  secrets as CLI params.
- Keep `UnifiClient` free of `domain/` and `application/` imports
  (extraction-ready); enforce with an import-linter contract.
- Keep `commands/` a thin adapter; business logic lives in `application/` +
  `domain/`.
- Commit on a feature branch; run `ruff` + `ty` + relevant tests first.

### Ask first

- Any write beyond the LAG toggle (new endpoints, new `port_overrides` fields).
- Adding a dependency beyond the jobhound-mirrored stack.
- Extracting the shared `unifi-core` library (defer until `unifi-mcp`'s
  legacy-API work pins the shared surface).
- Shipping any committed config that sets `UNIFI_INSECURE_TLS`.
- Distribution mechanism (`uv tool` / `pipx` vs a Homebrew formula in `yo61/tap`).
- Adopting session (username/password) auth.

### Never

- Never PUT without a backup, and never without either `--dry-run` shown or a
  confirmation (`--yes` counts as the confirmation; the backup still happens).
- Never commit secrets or a populated `UNIFI_API_KEY`.
- Never perform I/O in `domain/`.
- Never use the private API for reads the Integration API already covers — reads
  belong to `unifi-mcp`; `unifictl` owns imperative actions.
- Never push to `main`/`master`; never leave `ruff`/`ty`/`pytest` warnings
  unaddressed.

## 8. ADRs to capture during build

1. Use the private/legacy session API for `port_overrides` because the
   Integration API does not expose per-port aggregation.
2. Isolate the UniFi client behind `infrastructure/` so it can be extracted into
   a shared `unifi-core` library once `unifi-mcp` adopts the legacy REST API.
3. CLI grammar is verb-first (`set <resource> <value>`) for consistency with
   jobhound and kubectl/systemctl; independent of the DDD backend.

## 9. Open items (not blocking the first build)

- Command alias in the `jh` spirit vs. spelling out `unifictl`.
- Distribution: `uv tool` / `pipx` vs Homebrew tap.
- Whether a future `lag`-noun sub-app (`lag status`) is worth adding alongside
  `set lag` once read operations exist.
