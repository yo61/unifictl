# cyclopts — hypotheses

## A green suite does not show a parser upgrade is behaviour-neutral

Run the same invocations under the old and new version and compare exit codes
and output before merging a cyclopts major bump.

- Evidence for: 1 — PR #67: CI green on 5.0.0 while usage errors moved from
  exit 1 to exit 2.
- Evidence against: 0

## Changes required by a cyclopts bump in jobhound predict those needed here

- Evidence for: 1 — the exit-code pin from jobhound #195 applied directly.
- Evidence against: 1 — the `__complete` re-routing from the same PR did not
  apply, because unifictl never registered `__complete` with cyclopts.
