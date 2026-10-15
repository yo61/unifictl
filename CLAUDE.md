# unifictl — project instructions

Extends `~/.claude/CLAUDE.md`. Only rules that override or add to it are here.

## Merge and commit workflow

This repo **squash-merges**, like every other repository: squash is the only merge button. The
squashed commit's subject is the **PR title**, and release-please reads that title to pick the
changelog section and the version bump. Write PR titles as release notes for users, in
Conventional Commits form.

- One PR, one changelog line. A change that is both a fix and a feature is two PRs, or the title
  type that loses is lost from the changelog.
- Commits inside a PR are review history, not release notes; follow-up commits are fine.
- `Conventional Commits` runs commitlint over the PR's commits. Nothing lints the title, so check
  it before merging.

See `decisions/2026-10-15-squash-merge-like-every-other-repo.md`.

## Before calling work done

Evaluate the change against `quality/criteria.md`; blocking criteria must pass.
It is drawn from this repo's decision records and from failures actually
observed, not a generic template.

Run the gate whole and check its exit status:

```sh
task dev:check
```

Never pipe it through `tail`/`head` — the pipeline reports the pager's status
and hides the failure. The gate short-circuits, so a failure at `fmt-check`
means typecheck, imports, and tests never ran; re-run after fixing.

## Domain notes

- **`stat/device` fields are device-type-dependent.** `ip` is the LAN address on
  switches and APs but the **WAN** address on gateways, which report their LAN
  address in `lan_ip`. Verify any new raw field across `uap`, `usw`, and `udm`
  before mapping it, and prefer a corrective field's presence over a hardcoded
  device-type list. See `decisions/2026-09-03-device-ip-field-layering.md`.
- **`list devices --json` is a raw passthrough** of the controller's objects.
  Corrections belong in the table layer, never in the JSON.
- **The completion command tree in `commands/_complete.py` is hand-mirrored** and
  deliberately imports neither cyclopts nor rich. Any command or flag change
  must update it; two separate tests guard it and both need updating.
- **Live-probe output is not repo material.** Use RFC 5737 addresses
  (`203.0.113.0/24`) in fixtures, docs, commit messages, and PR bodies — a real
  address in a PR body cannot be un-published, since GitHub keeps edit history.

## Records

- `decisions/` — one architecture decision record per choice
- `quality/criteria.md` — the pre-completion gate
- `knowledge/INDEX.md` — routes to per-domain facts, hypotheses, and rules
- `SPEC.md` — build reference
