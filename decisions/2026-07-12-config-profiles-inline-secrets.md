## Decision: Store per-profile secrets inline in config.toml, protected by 0600

Introduce named configuration profiles (`[profiles.<name>]` tables in
`~/.config/unifictl/config.toml`) that carry full connection details, including
an inline `api_key`. When a profile contains an inline `api_key`, the config file
must be `0600`; a group/world-readable file is refused with a `chmod 600` hint.
This reverses the prior intent that secrets live only in `UNIFI_*` environment
variables and never in the config TOML.

## Context

`unifictl` needs to point at different target UniFi controllers without
re-exporting env vars. A profile that selects a whole controller must carry that
controller's `api_key`. A single set of `UNIFI_*` env vars cannot hold secrets for
N controllers, so per-profile secret storage is required. The original
`config.py` docstring asserted "secrets ... are never read from the ... TOML
file" — profiles necessarily relax that.

## Alternatives considered

- **Inline secret + enforce 0600** (chosen) — simplest, self-contained; same risk
  model as `~/.aws/credentials` / `~/.netrc`. Key sits on disk in cleartext.
- **Env indirection (`api_key_env = "UNIFI_API_KEY_HOME"`)** — keeps the config
  file secret-free, preserving the old boundary. But it forces the user to manage
  N env vars for N profiles and adds a level of indirection for little gain here.
- **Both inline and env-indirection supported** — most flexible, but doubles the
  code and test surface for a homelab tool with a couple of targets. YAGNI.
- **OS keychain integration** — most secure, most machinery; unjustified now.

## Reasoning

Robin explicitly wants a profile to set `base_url`, `api_key`, `site`, TLS and
`switch` in one place, with env/CLI as fallback. Inline storage is the only option
that satisfies "one named target, edited in one file." The `0600` enforcement is
gated on a secret actually being present, so secret-free operational configs are
never nagged. The disk-cleartext risk is accepted as standard for a local CLI
credentials file and is bounded by file permissions.

## Trade-offs accepted

- API key stored in cleartext on disk (mitigated by enforced `0600`, not
  eliminated). No keychain, no encryption at rest.
- The config file now mixes operational and secret data; permission enforcement
  becomes conditional logic rather than a clean "TOML never holds secrets" rule.
- No secret-free indirection escape hatch in v1 (can be added later without
  breaking inline profiles).

## Supersedes

The informal "secrets never in the config TOML" intent stated in
`src/unifictl/infrastructure/config.py` module docstring. No prior formal decision
record covered this. Design detail: `docs/superpowers/specs/2026-07-12-config-profiles-design.md`.
