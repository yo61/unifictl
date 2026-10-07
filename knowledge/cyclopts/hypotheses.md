# cyclopts — hypotheses

## A green suite does not show a parser upgrade is behaviour-neutral

Run the same invocations under the old and new version and compare exit codes
and output before merging a cyclopts major bump.

- Evidence for: 2 — PR #67: CI green on 5.0.0 while usage errors moved from
  exit 1 to exit 2. yo61/flux-homelab#597: the `homelab` CLI's 480 tests passed
  unchanged on 5.1.0 while the same exit-code change and case-sensitive command
  matching (`Completion zsh` stopped working) went through unasserted.
- Evidence against: 0

## Changes required by a cyclopts bump in jobhound predict those needed here

- Evidence for: 1 — the exit-code pin from jobhound #195 applied directly.
- Evidence against: 1 — the `__complete` re-routing from the same PR did not
  apply, because unifictl never registered `__complete` with cyclopts.
- Related, not counted: unifictl's own notes predicted yo61/flux-homelab#597 the
  same way. The exit-code pin applied directly; `__complete` again needed nothing,
  because `homelab` also dispatches it before cyclopts is imported. That supports
  a broader claim (any sibling repo's bump predicts the next) rather than this
  jobhound-specific one.
