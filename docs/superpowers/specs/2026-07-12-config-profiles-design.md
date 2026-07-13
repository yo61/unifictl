# Design: Local configuration profiles

Date: 2026-07-12
Status: Approved (brainstorming) — pending spec review

## Summary

Add named **configuration profiles** to `unifictl` so the tool can be pointed at
different target UniFi controllers/switches without re-exporting environment
variables. A profile bundles the stable target identity — connection details
(`base_url`, `api_key`, `site`, TLS settings) and the `switch` to operate on.
(Mutable LAG state, `leaders`, is deliberately excluded.) Profiles are **optional
and additive**: with no profiles defined and no default profile set,
`load_settings()` behaves exactly as it does today (env + CLI only). An optional
`default_profile` selects a profile when none is named explicitly.

## Goals

- Define one or more named targets in `~/.config/unifictl/config.toml`.
- Select a target per-invocation with `--profile NAME`, per-session with
  `UNIFI_PROFILE`, or persistently with `default_profile`.
- Let any single value be overridden on the command line or via env, independent
  of the selected profile.
- Preserve the current env-only workflow unchanged (no migration, no dual-format
  shim).

## Non-goals

- Profile *management* commands that mutate config (`profile add`/`edit`/`rm`).
  Profiles are edited by hand in the TOML for v1 (YAGNI). Read-only
  `list`/`show`/`example` are in scope; `example` prints to stdout and never
  writes the file.
- Per-file profile storage / a `profiles/` directory (premature machinery).
- Secret indirection (`api_key_env`) or an OS keychain. Secrets are stored inline
  in the profile, protected by file permissions (see Security).
- Session/username-password auth (unchanged; still API-key only).

## Approach (chosen)

**Named `[profiles.<name>]` tables inside the existing single `config.toml`.**
The file gains an optional top-level `default_profile` key and any number of
`[profiles.<name>]` tables. Today's top-level `switch`/`leaders` keys remain valid
as global operational defaults, and `leaders` stays top-level only (never a
profile field — see below). This is additive — nothing existing is removed or
reinterpreted.

Rejected alternatives:

- **A `profiles/` directory (one file per profile):** cleaner isolation but more
  filesystem machinery and test surface than a handful of targets justify.
- **Profiles fully replace top-level config:** single clean model, but makes
  profiles mandatory and breaks the current env-only + top-level `switch`
  workflow. Violates the "optional" requirement.

## Config file format

```toml
# ~/.config/unifictl/config.toml
# Must be chmod 0600 when any profile contains an inline api_key.

default_profile = "home"          # optional; selects a profile when none named

# Top-level operational defaults (unchanged):
#   switch  — no-profile default, overridden by a selected profile's switch
#   leaders — default LAG leader ports for `set lag`; NOT a profile field
switch  = "70:a7:41:90:82:dd"
leaders = [1, 3]

[profiles.home]
base_url     = "https://192.168.1.1"
api_key      = "…"
site         = "default"
switch       = "70:a7:41:90:82:dd"
# ca_cert     = "/path/to/ca.pem"
# insecure_tls = false
# timeout_ms   = 30000
# (no `leaders` — LAG membership is mutable operational state, not target identity)

[profiles.lab]
base_url = "https://10.0.0.1"
api_key  = "…"
switch   = "aa:bb:cc:dd:ee:ff"
```

Allowed keys inside a `[profiles.<name>]` table: `base_url`, `api_key`, `site`,
`ca_cert`, `insecure_tls`, `timeout_ms`, `switch` — the stable target-identity
fields, all optional. Unknown keys inside a profile table are **rejected** with a
`ConfigError` naming the profile and the offending key (fail fast); this includes
`leaders`, which is deliberately not a profile field.

A profile holds what is **stable about a target's identity** — which controller
(`base_url`/`api_key`/`site`/TLS) and which switch. `leaders` is excluded because
it is **mutable operational state**: the tool will create and reshape LAGs, so a
switch's leader ports change over time. Persisting them per-profile would cause
config drift. `leaders` therefore stays exactly as today — the `--leader` flag
with the top-level `config.toml` `leaders` as an optional default — outside the
profile system.

## Resolution

Two independent resolutions happen on each invocation.

### 1. Which profile is selected

```
--profile NAME  >  UNIFI_PROFILE env  >  default_profile in config  >  none
```

- An unknown profile name (from any source) ⇒ `ConfigError` listing the available
  profile names.
- "none" is valid and means: no profile layer participates in field resolution
  (pure env/CLI/top-level, i.e. today's behaviour).

### 2. Each field's value (the ladder)

```
CLI flag  >  UNIFI_* env var  >  selected profile  >  top-level TOML default  >  built-in default
```

- Only fields that have a CLI flag today (e.g. `--switch`) participate at the CLI
  tier; others start at the env tier.
- `base_url` and `api_key` have no CLI flag and no top-level TOML tier
  (secrets/connection were never top-level) — they resolve
  `env > profile > (error if missing)`.
- `leaders` is **not** a profile field, so it has no profile tier: it resolves
  `--leader flag > top-level TOML default > (empty)`, exactly as today.
- Missing required `base_url`/`api_key` after the full ladder ⇒ existing
  `ConfigError` messages ("UNIFI_BASE_URL is not set", etc.), extended to mention
  the profile when one is selected.

## CLI surface

- **Global `--profile NAME`** flag on the top-level app, available to every
  command. Mechanism: a cyclopts `app.meta` parameter that resolves the profile
  name once and makes it available to each command's `load_settings(...)` call.
  (Threading a global flag through mounted sub-apps is the one non-trivial wiring
  task; settle the exact mechanism in the plan.)
- **`unifictl profile list`** — read-only. Lists profile names, marks the default,
  shows `base_url` for each. No secrets.
- **`unifictl profile show NAME`** — read-only. Shows a profile's resolved fields
  with `api_key` **redacted** (e.g. last 4 chars or `****`). Unknown NAME ⇒
  `ConfigError`.
- **`unifictl profile example [NAME]`** — read-only. Prints a fully-commented
  `[profiles.<NAME>]` TOML block to **stdout** (NAME defaults to `example`): every
  allowed field with placeholder values, plus a `chmod 600` reminder comment. It
  does **not** write the config file; the user redirects it
  (`unifictl profile example home >> ~/.config/unifictl/config.toml`). This keeps
  it non-mutating and composable.

## Security

- Secrets are stored **inline** in the profile (chosen over env-indirection for
  simplicity — same risk model as `~/.aws/credentials`/`~/.netrc`).
- **Permission enforcement, conditional on secrets:** when `config.toml` contains
  at least one profile with an inline `api_key`, and the file is group- or
  world-readable, `load_settings()` refuses with a `ConfigError` and a
  `chmod 600 <path>` hint. A secret-free config is never nagged.
- `profile show` redacts `api_key`. No command ever prints the raw key.

## Error handling

| Condition | Result |
| --- | --- |
| Unknown profile name (flag/env/default) | `ConfigError`, lists available names |
| Profile field wrong type | `ConfigError` naming profile + key + expected type |
| Unknown key inside a profile table | `ConfigError` naming profile + key |
| `config.toml` group/world-readable with inline secret | `ConfigError` + `chmod 600` hint |
| Required `base_url`/`api_key` missing after ladder | existing `ConfigError`, mentions active profile |
| `profile show` unknown NAME | `ConfigError`, lists available names |

## Architecture / placement

- All logic lives in `src/unifictl/infrastructure/config.py`. New surface:
  - `load_settings() -> Settings` — resolves the ladder, reading the selected
    profile name internally from `UNIFI_PROFILE`/`default_profile`. Signature is
    unchanged, so the five existing commands are untouched.
  - `read_config()` / `load_profiles(data)` — parse + validate profile tables.
  - profile-selection helper (`UNIFI_PROFILE`/`default_profile`).
  - a permission-check helper for the secret-present case.
- The global `--profile` flag is a cyclopts `app.meta` launcher in `cli.py` that
  sets `os.environ["UNIFI_PROFILE"]` before dispatch (so flag beats env), keeping
  the flag genuinely global without threading it through sub-apps.
- New command module `src/unifictl/commands/profile.py` mounts a `profile`
  sub-app (`list`, `show`, `example`), registered in `cli.py` alongside the others.
- `Settings` (frozen dataclass) is unchanged — profiles resolve *into* it.

## Testing

Resolution is pure logic over one TOML read + env, so it's unit-testable with
`tmp_path` + monkeypatched env. Cases:

- Each ladder tier wins in isolation (CLI, env, profile, top-level, default).
- Precedence conflicts: value set in profile **and** CLI ⇒ CLI wins; profile
  **and** env ⇒ env wins.
- Profile selection precedence: `--profile` > `UNIFI_PROFILE` > `default_profile`.
- Backward-compat: no `[profiles]` and no `default_profile` ⇒ identical to today.
- Unknown profile name ⇒ `ConfigError` (per source).
- Malformed profile field ⇒ `ConfigError`.
- Unknown key inside a profile table ⇒ `ConfigError` (including a `leaders` key,
  which is not a profile field).
- `leaders` resolves from `--leader`/top-level default only; a profile never
  supplies it.
- Permission refusal only when an inline secret is present; secret-free config
  loads regardless of mode.
- `profile list` output (names + default marker); `profile show` redaction and
  unknown-name error.
- `profile example` prints a valid `[profiles.<NAME>]` block (round-trips through
  `tomllib`) with all allowed keys and the `chmod 600` reminder; defaults NAME to
  `example`; writes nothing.

Tests mirror package structure in `tests/` (extend `test_config.py`; add
`tests/test_cmd_profile.py`).

## Resolved implementation questions

See the plan `docs/superpowers/plans/2026-07-13-config-profiles.md`:

- Global `--profile` flag: a cyclopts `app.meta` launcher that sets `UNIFI_PROFILE`
  (verified against cyclopts 4.11.2; preserves help/version and error propagation).
- `api_key` redaction in `profile show`: last 4 characters (`…cret`), or `****`
  when the value is 4 chars or shorter.
- Completion: new commands are added to the hardcoded `_complete.py` static tables;
  profile-name *value* completion is deferred (out of scope for v1).
