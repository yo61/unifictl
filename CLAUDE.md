# unifictl — project instructions

Extends `~/.claude/CLAUDE.md`. Only rules that override or add to it are here.

## Merge and commit workflow

This repo **rebase-merges**. Squash and merge-commit are disabled on GitHub, so
rebase is the only merge button.

**Every commit lands on `main` and becomes a changelog line.** release-please
reads each commit's *subject* to pick the changelog section and the version
bump, so a PR holding a `fix:` and a `feat:` commit yields both a Bug Fixes and
a Features entry and bumps the minor. Write subjects as release notes for
users, not as notes for reviewers.

Fold review fixes into the commit they correct rather than appending follow-ups:

```sh
git commit --fixup <sha>      # or HEAD, HEAD~2
GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash origin/main
git push --force-with-lease   # if the branch was already pushed
```

`-i` is what makes `--autosquash` take effect on every git version; on older
git the flag is ignored without it. `GIT_SEQUENCE_EDITOR=:` accepts the todo
list autosquash already arranged, so no editor opens and the command is safe
to run unattended.

- **Rebasing and force-pushing your own unmerged PR branch is expected here.**
  It does not breach the global "never amend/rebase commits already pushed to
  shared branches" rule — that rule protects shared branches (`main`), not your
  own feature branch. Use `--force-with-lease`, never bare `--force`.
- **Never use `:/text` as a `--fixup` target.** It searches every ref and
  returns the youngest match, so it silently aims at commits on other branches;
  the resulting marker has no target in range and never squashes. Use a SHA or
  `HEAD~n`. See `decisions/2026-09-03-rebase-only-merge-policy.md`.
- A change spanning a fix and a feature belongs in **one PR with two commits**,
  not two PRs. That was only necessary under squash-merge.

CI enforces the mechanical half: `commit-hygiene` rejects `fixup!`, `squash!`,
`amend!`, and `wip` subjects, and `Conventional Commits` runs commitlint over
every commit in the PR. commitlint ignores fixup markers by default, which is
why the separate job exists.

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
- `SPEC.md` — build reference
