## Decision: File-per-profile config with a separate credential store

Store each profile's non-secret configuration in its own file under a `profiles/`
directory (`~/.config/unifictl/profiles/<name>.toml`, location overridable via
`profiles_dir` in `config.toml`), and store all secrets in a single separate
`~/.config/unifictl/credentials.toml` with `[<credential>]` sections. A profile
binds to a credential by an optional `credential` field that defaults to
`"default"`. Manage both through CLI commands (`profile create/edit/set/unset/
list/describe/activate/delete`, `credential set/list/delete`) rather than by hand
editing. Use `tomlkit` for comment-preserving writes.

## Context

PR #11 (unmerged) stored profiles as `[profiles.<name>]` tables inside
`config.toml` with `api_key` inline, protected by making the whole file `0600`
whenever any profile held a key. Editing meant hand-editing the TOML. Two problems
surfaced while thinking the feature through:

- In UniFi, one controller (one API key) commonly fronts many switches, so
  per-switch profiles would duplicate the key, and rotating it meant editing every
  section.
- Inline secrets forced `0600` on the same file that holds non-secret operational
  config, so the whole file became non-shareable.

Prior art resolves both: the AWS CLI keeps secrets in a separate `credentials`
file from `config`, and gcloud stores each configuration in its own file in a
directory with `create`/`activate`/`delete`/`list` commands.

## Alternatives considered

- **Inline secrets in single-file profile tables** (PR #11) — simplest, but the
  key-duplication and whole-file-`0600` problems above.
- **File-per-profile, secret inline in each profile file** — shareable-per-file but
  still duplicates keys and makes each profile file `0600`.
- **File-per-profile + separate single credential store** (chosen) — non-secret
  files are freely shareable; exactly one `0600` file; one shared `[default]`
  credential backs many profiles; rotation is one command.
- **Credential referenced explicitly, defaulting to the profile name** — considered,
  but `[default]` is simpler for the one-controller homelab case (no naming, no
  per-profile field until a second controller exists).

## Reasoning

The separate credential store makes the `0600` concern collapse to one well-known
file, lets profile configs be shared/synced/committed, and — via the shared
`[default]` credential — removes key duplication for the dominant UniFi case (one
controller, many switches). Because the key then belongs to the credential rather
than any profile, `api_key` is removed from `profile set` and gets its own
`credential` command group; this prevents a profile command from silently
rewriting a shared secret. Editing non-secret config through `$EDITOR` is
convenient, but the API key is never routed through the editor (temp-file/swap/undo
leak), so it only ever arrives via a hidden prompt or `--stdin`. `tomlkit` is
added so structured writes (`set`/`unset`/`activate`) preserve the comments in
files the user hand-edits.

## Trade-offs accepted

- More moving parts than a single file: three file kinds (`config.toml`,
  `profiles/*.toml`, `credentials.toml`) and two command groups.
- A new dependency (`tomlkit`) — justified by comment-preserving edits of
  human-facing files; `tomllib` (read-only) stays on the hot read path.
- Secrets are still cleartext on disk (mitigated by enforced `0600`), unchanged
  from the superseded decision.

## Supersedes

`decisions/2026-07-12-config-profiles-inline-secrets.md` (inline per-profile
secrets protected by whole-file `0600`). Design detail:
`docs/superpowers/specs/2026-07-13-profiles-credentials-redesign-design.md`.
Replaces the storage model in PR #11, revised before merge.
