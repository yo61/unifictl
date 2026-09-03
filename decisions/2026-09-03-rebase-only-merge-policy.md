## Decision: rebase-merge only; every commit in a PR is release-note material

Squash and merge-commit are disabled on the repository; rebase is the only
merge button. Each commit in a PR must stand on its own as a changelog line,
curated with `git rebase -i --autosquash` before merge. A `commit-hygiene` CI
job rejects `fixup!`/`squash!`/`amend!`/`wip` subjects so uncurated commits
cannot reach `main`.

## Context

0.5.4 shipped the `--wan` flag but recorded it under **Bug Fixes** with a patch
bump, because the PR was squash-merged and release-please parses only the
squashed commit's *subject* — which was the PR title, typed `fix`.

The commit set was deliberately split into `fix(list): ...` and
`feat(list): ...` precisely to get both changelog sections. That effort was
wasted, and the failure is not a configuration mistake: `squash_merge_commit_
message` was already `COMMIT_MESSAGES`, so the squashed commit `967cc09`
literally contains `* feat(list): add --wan to show gateway public addresses`
in its body. Preserved in the message, ignored by the parser.

Two facts settled the direction:

- **release-please does walk non-first-parent commits.** 30 of the 59 commit
  SHAs cited in `CHANGELOG.md` are not on `main`'s first-parent line — they are
  individual branch commits from the era when this repo used merge commits, each
  of which got its own changelog entry. Per-commit types do reach the changelog
  under any non-squash strategy.
- **The repo already validates every commit.** The `Conventional Commits` CI job
  runs commitlint over the whole PR commit range with `fetch-depth: 0`, and a
  local `commit-msg` hook does the same. The repo was paying for per-commit
  validation under a strategy that discarded all but the title.

## Alternatives considered

- **Keep squash; one PR per logical change.** Works, and needs no settings
  change. Rejected because it fragments review: the change that prompted this
  was one coherent investigation, and splitting it into two PRs would have
  degraded the review to fix the changelog. It also puts the type decision on
  the PR title, which must be chosen before the change's final shape is known.
- **Merge commits.** Also surfaces per-commit types, but adds a merge commit per
  PR and non-linear history. Recent releases have been linear; no reason to give
  that up when rebase achieves the same changelog result.
- **Keep squash and be disciplined about PR titles.** This is the status quo
  that just failed. A single title cannot express a change that is both a fix
  and a feature, so one of the two is always lost.

## Reasoning

Rebase-merge makes the commit the unit of changelog granularity, which is the
unit commitlint already enforces. Curation moves to just before merge, when the
finished change is in view — rather than at PR-creation time, when its shape
still has to be predicted. It keeps history linear and needs no per-merge
choice, since the other two buttons are now gone.

The residual judgement — *is this commit worth a changelog line* — is the same
judgement squash demanded as *does this deserve its own PR*. Rebase relocates it
rather than adding it, and the CI guard removes the mechanical half.

## Trade-offs accepted

- **Every commit is public release notes.** Under squash, a stray commit was
  invisible; now it ships. The `commit-hygiene` job catches fixup and WIP
  markers, but nothing can judge whether a well-formed commit is worth
  publishing — that stays manual.
- **Curation is a manual step.** `git commit --fixup <sha>` during development
  plus one `git rebase -i --autosquash` before pushing keeps it mechanical, but
  it is a step that can be forgotten. CI fails loudly when it is.
- **Changelog entries lose the inline PR reference.** GitHub's rebase-merge does
  not rewrite commit subjects, so no `(#N)` suffix is appended. Compare 0.3.1's
  `... ([#7](...)) ([63bd40a](...))` with merge-commit-era 0.4.0's
  `... ([abce28a](...))`. The commit link remains; the issue link does not.
- **Rebase rewrites SHAs**, so a pushed branch's commits are not the commits
  that land on `main`, and there is no merge commit marking the PR boundary.
- **Granularity can swing the other way.** Six changelog lines for one feature
  is visible in this repo's own history (`feat: add static __complete candidate
  handler`, `feat: bundle per-shell completion scripts`, `feat: wire completion
  command ...`). Curating toward fewer, larger commits is now a changelog
  concern, not only a review one.

## Supersedes

No prior decision recorded a merge strategy; this establishes one.
