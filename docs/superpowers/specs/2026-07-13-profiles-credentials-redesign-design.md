# Design: Profiles & credentials redesign (file-per-profile + separate credential store)

Date: 2026-07-13
Status: Approved (brainstorming) — pending spec review
Supersedes: `docs/superpowers/specs/2026-07-12-config-profiles-design.md` and the storage model in PR #11.

## Summary

Replace the single-file `[profiles.<name>]`-tables model (PR #11, unmerged) with a
file-per-profile store plus a separate credential store, and add CRUD commands so
profiles and credentials are managed through the CLI rather than by hand-editing.
The model follows established prior art: **gcloud configurations** (a directory of
per-profile files, an active/default pointer, `create`/`activate`/`delete`/`list`)
and the **AWS CLI** habit of keeping secrets in a separate file from non-secret
config.

The resolved `Settings` shape is unchanged — only *where* fields come from changes,
so the command layer (`set lag`, `show port`, `list devices`) is untouched.

## Goals

- Non-secret profile config lives in per-profile files that are safe to share,
  sync, or commit.
- Secrets live in exactly one `0600` file; the `0600` concern collapses to that
  one well-known path.
- One controller/key can back many per-switch profiles without duplicating the key.
- Profiles and credentials are created/edited/removed via CLI commands; config and
  credential files are created automatically on first write.
- The env-only workflow still works with zero profiles.

## Non-goals

- Migration from the PR #11 format — nothing shipped; PR #11 is revised before merge.
- Multiple credential fields (AWS has key id + secret); a unifictl credential is a
  single `api_key`.
- Secret encryption / OS keychain — protection is file permissions, as before.
- Editing secrets through `$EDITOR` (deliberately excluded; see Security).

## Relationship to PR #11

PR #11 is revised on the same branch before merging. Its single-file storage,
`load_settings` profile resolution, `profile list/show/example`, `_complete.py`
entries, README, and the `2026-07-12` decision record are replaced by this design.
A new decision record supersedes `decisions/2026-07-12-config-profiles-inline-secrets.md`.

## Storage layout

Three file kinds under `~/.config/unifictl/` (XDG config home):

### 1. `config.toml` — selection + tool defaults
```toml
default_profile = "home"                 # optional; the active profile
profiles_dir    = "~/.config/unifictl/profiles"   # optional override; default shown
leaders         = [1, 3]                 # optional operational default for `set lag`
```
Auto-created on first write (e.g. `profile activate`, or `profile create` scaffolding).
Not sensitive.

### 2. `profiles/<name>.toml` — one non-secret profile per file
```toml
# base_url = "https://192.168.1.1"    # controller URL
# site     = "default"
# switch   = "aa:bb:cc:dd:ee:ff"      # MAC of the switch to operate on
# credential = "default"              # which credentials.toml section holds the api_key
# ca_cert / insecure_tls / timeout_ms also allowed
base_url = "https://192.168.1.1"
switch   = "aa:bb:cc:dd:ee:ff"
```
The filename (minus `.toml`) is the profile name — there is no `[profiles.x]` wrapper.
Directory is `profiles_dir` (default `<config>/profiles/`), `~` expanded, relative
paths resolved against the config dir. Allowed keys: `base_url`, `site`, `switch`,
`ca_cert`, `insecure_tls`, `timeout_ms`, `credential`. `api_key` is **rejected** here
(it belongs in the credential store). Not sensitive — normal permissions.

### 3. `credentials.toml` — the single secret file
```toml
[default]
api_key = "…"

[work]              # only when a second controller with a different key exists
api_key = "…"
```
The **only** file requiring `0600`. Created `0600` by `credential set` / `profile create`.
On any read that needs a key, a group/world-readable `credentials.toml` is refused with
a `chmod 600` hint. Sections are credential names; each holds one `api_key`.

## Profile → credential binding

A profile's optional `credential` field names its `credentials.toml` section; when
omitted it defaults to `"default"`. So the common homelab case — one controller, one
key, many per-switch profiles — needs no `credential` field anywhere and shares the
single `[default]` section. A second controller gets a named section (e.g. `[work]`)
and the profiles that use it set `credential = "work"`.

## Resolution

### Profile selection (unchanged)
```
--profile NAME  >  UNIFI_PROFILE env  >  default_profile (config.toml)  >  none
```
Unknown selected profile ⇒ `ConfigError` listing available profile names.

### Field resolution into `Settings`
- `base_url`, `site`, `ca_cert`, `insecure_tls`, `timeout_ms`:
  `UNIFI_* env  >  profile file  >  built-in default`.
- `api_key`:
  `UNIFI_API_KEY env  >  credentials[ profile.credential or "default" ].api_key  >  (ConfigError)`.
- `switch`: `--switch (CLI, command layer)  >  profile file `switch`  >  none`.
- `leaders`: `--leader (CLI)  >  config.toml `leaders`  >  ()`. Not a profile field.

With no profile selected and none default, every field falls to env/CLI/built-in —
the env-only workflow, unchanged. (`config.toml` no longer holds a top-level `switch`
default; `switch` is a profile field now.)

## Command surface

Two noun-grouped sub-apps. Rationale: these manage the tool's own local config, a
distinct concern from the verb-first domain commands (`list devices`, `show port`,
`set lag`), matching how `gcloud config …` / `kubectl config …` group config CRUD.

### `unifictl profile …`
- **`create NAME`** — ensure `profiles_dir` exists; open `$EDITOR` on a commented
  template of the non-secret fields; on save, validate and write `profiles/NAME.toml`.
  Then resolve the profile's credential (`default` or its `credential`); if that
  section is absent from `credentials.toml`, prompt once (hidden) for the API key and
  write it (`0600`). Reuses an existing credential without prompting.
- **`edit NAME`** — open `$EDITOR` on the existing `profiles/NAME.toml`; validate on save.
- **`set NAME KEY VALUE`** — set one non-secret field (tomlkit round-trip, comments
  preserved). `KEY == api_key` ⇒ `ConfigError` pointing to `credential set`.
- **`unset NAME KEY`** — remove a non-secret field.
- **`list`** — profile names, marking `default_profile`.
- **`describe NAME`** — the profile's resolved fields, with `api_key` shown **redacted**
  (read via its credential). Replaces PR #11's `show`.
- **`activate NAME`** — write `default_profile = NAME` to `config.toml` (create if absent).
- **`delete NAME`** — remove `profiles/NAME.toml` (confirm; `--yes` to skip). Leaves
  credentials untouched (may be shared).

`profile example` (PR #11) is dropped — `create` + `describe` supersede it.

### `unifictl credential …`
- **`set [NAME=default]`** — hidden prompt or `--stdin`; write/rotate `[NAME].api_key`
  in `credentials.toml` (create `0600` if absent). Rotating a shared key is one command.
- **`list`** — credential names only. Never prints keys. (Showing which profiles
  reference each is a possible later enhancement, out of scope for v1.)
- **`delete NAME`** — remove the `[NAME]` section (confirm; `--yes`).

Tab-completion (`_complete.py` static tables) covers both command trees.

## `$EDITOR` handling

`create`/`edit` launch `$VISUAL` then `$EDITOR`; if neither is set, `ConfigError` with a
hint (e.g. "set $EDITOR"). The editor operates on a temp file seeded from the template
(create) or the existing file (edit); on exit the content is parsed and validated, and
only written to the real path on success. On invalid TOML or a rejected key, the error is
printed and the editor is re-opened on the same temp file so the user can fix it
(visudo-style); if they exit again without changing it, the operation aborts, leaving any
existing file untouched and writing nothing. The API key is **never** placed in an editor
buffer/temp file — it only ever arrives via hidden prompt or `--stdin`.

## Security & permissions

- Secrets live only in `credentials.toml`, created and required to be `0600`. A
  group/world-readable `credentials.toml` is refused (with a `chmod 600` hint) whenever
  a key is read from it.
- `profiles/*.toml` and `config.toml` are non-sensitive (normal permissions) and may be
  shared/committed.
- `profile describe` redacts `api_key` (last 4, `str()`-coerced); no command prints a raw key.
- The editor never receives the secret (no editor temp-file/swap/undo leak).

## Validation & errors

| Condition | Result |
| --- | --- |
| Unknown selected profile | `ConfigError`, lists available profiles |
| `api_key` key inside a `profiles/*.toml` | `ConfigError` → use `credential set` |
| Unknown key / wrong type in a profile file | `ConfigError` naming the file + key |
| Profile's credential section missing when a key is needed | `ConfigError` → `credential set NAME` |
| `credentials.toml` group/world-readable | `ConfigError` + `chmod 600` hint |
| `$EDITOR`/`$VISUAL` unset for `create`/`edit` | `ConfigError` with a hint |
| `profile set … api_key …` | `ConfigError` → `credential set` |

## Dependencies

- **`tomlkit`** — comment/format-preserving TOML read-modify-write for the mutation
  commands, so `set`/`unset`/`activate` and templated files keep their comments.
  Pinned exact version. Pure-Python.
- Pure reads on the hot path (`load_settings`) stay on stdlib `tomllib`; `tomlkit` is used
  only by the write/round-trip commands.

## Architecture / placement

- `infrastructure/profile_store.py` (new) — filesystem + TOML I/O for the three file
  kinds: read/write profile files, read/write `credentials.toml` sections, read/write
  `config.toml` selection keys, permission enforcement, `profiles_dir` resolution.
  Encapsulates all `tomlkit`/`0600`/path logic behind a small interface.
- `infrastructure/config.py` — `load_settings()` resolves selection + field ladders
  using `profile_store` for reads. `Settings` unchanged.
- `commands/profile.py` — the `profile` sub-app (create/edit/set/unset/list/describe/
  activate/delete).
- `commands/credential.py` (new) — the `credential` sub-app (set/list/delete).
- `commands/_editor.py` (new, small) — `$EDITOR` launch + validate-on-save loop, reused
  by `create`/`edit`.
- `cli.py` — register both sub-apps; the `--profile` meta launcher is unchanged.
- `commands/_complete.py` — add `profile`/`credential` command trees to the static tables.

## Testing

- Resolution: profile-file + credential-section + env combinations for every field;
  profile selection precedence; `credential` binding (default vs named); env overrides;
  env-only (no profiles) backward compatibility.
- Permissions: `credentials.toml` refusal when group/world-readable and a key is read;
  created files are `0600`.
- Store I/O: round-trip write preserves comments (tomlkit); `profiles_dir` override
  (`~`, relative); unknown-key / `api_key`-in-profile rejection.
- Commands: `create`/`edit` with the editor subprocess mocked (assert template seeding,
  validate-on-save, no secret in the editor temp file); `set`/`unset`/`activate`/`list`/
  `describe` (redaction) / `delete`; `credential set` (hidden prompt and `--stdin`) /
  `list` (no keys) / `delete`; error paths from the table above.
- Completion: `profile`/`credential` sub-command names match the real apps.

## Phasing (for the implementation plan)

Roughly: (1) `profile_store` + credentials/config I/O + permissions; (2) resolution in
`load_settings` + backward-compat; (3) `credential set/list/delete`; (4) `profile
create/edit` + editor helper; (5) `profile set/unset/list/describe/activate/delete`;
(6) completion; (7) docs + decision record + remove PR #11's superseded pieces.

## Open questions

None outstanding — all forks resolved during brainstorming.
