## Decision: exit 1 only for an error; a declined prompt exits 0

Exit codes are `0` success, `1` the command failed, `2` usage error. Answering
no at a confirm prompt, or closing the editor without saving, is the user's
choice and not an error, so it exits `0`.

## Context

The cyclopts 5 upgrade (#67) moved usage errors from exit 1 to exit 2, which
prompted documenting the exit codes in the README. Writing that table showed
SPEC.md claimed a declined write exits 1 while every abort path in the code
(`set lag`, `credential delete`, `profile delete`, `profile create`,
`profile edit`) prints `aborted` and returns, exiting 0.

## Alternatives considered

- **Exit 1 on a declined confirm prompt**, as SPEC.md originally said. It stops
  `unifictl set lag off && next-step` from continuing after a "no".
- **Exit 1 for the three confirm prompts, 0 for the two editor aborts.**

## Reasoning

A non-zero exit means something went wrong. Declining is a successful outcome
of the command doing what it was told. The code already behaved this way; the
SPEC was the outlier.

## Trade-offs accepted

A wrapper cannot tell "applied" from "declined" by exit status alone. Scripts
that must not prompt pass `--yes`, and never reach a decline path.

## Supersedes: none
