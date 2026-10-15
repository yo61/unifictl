## Decision: squash-merge, like every other repository

Squash is the only merge button. The squashed commit takes the PR title as its subject
(`squash_merge_commit_title: PR_TITLE`) and the PR's commit messages as its body, so release-please
reads one changelog line and one version bump per PR, from the title.

## Context

`2026-09-03-rebase-only-merge-policy.md` made this the one repository across Robin's
organisations that rebase-merged. By 2026-10-15 the GitHub settings had gone back to squash-only
without a record of the change: #76 and #77 (Dependabot) and #78 and #79 (the jactionlint rollout,
GLB-23) were all squash-merged while `CLAUDE.md` still said rebase-only. Robin chose to make the
documents match the settings and the rest of the fleet, not the other way round.

## Alternatives considered

- **Restore rebase-only.** Keeps per-commit changelog entries, at the cost of being the only
  repository with a different merge workflow, curation step and CI job.
- **Merge commits.** Rejected in 2026-09-03 for the same reasons as then.

## Reasoning

One merge workflow across every repository: the same button, the same expectations of a PR
title, and nothing repository-specific to remember or to enforce in CI. The rebase-only
machinery (`commit-hygiene`, `--fixup`/`--autosquash` curation) exists only to support a
workflow no other repository uses.

## Trade-offs accepted

- **The PR title is the changelog line.** Its type picks the section and the bump. A PR that
  holds a fix and a feature records only the title's type — the 0.5.4 failure that 2026-09-03
  responded to. Split such a change into two PRs.
- **Nothing lints the PR title.** `Conventional Commits` runs commitlint over the PR's commits,
  not its title, as in the other repositories.
- **Commits inside a PR are no longer release notes**, so the `commit-hygiene` job that rejected
  `fixup!`/`wip` subjects is removed.

## Supersedes

`decisions/2026-09-03-rebase-only-merge-policy.md`.
