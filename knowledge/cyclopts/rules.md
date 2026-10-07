# cyclopts — rules

## A green suite does not show a parser upgrade is behaviour-neutral

Before merging a cyclopts major bump, run the same invocations under the old and
new version and compare exit codes and output. Drive them through every entry
point a caller can reach (`main()` and the `app()` proxy), not only `main()`.

Promoted from hypotheses on 2026-10-07 after three confirmations, none against:

- PR #67: CI green on 5.0.0 while usage errors moved from exit 1 to exit 2.
- yo61/flux-homelab#597: 480 tests passed unchanged on 5.1.0 while the same
  exit-code change and case-sensitive command matching went through unasserted.
- yo61/python-template#39: CI green on 5.1.0 while `app(["__complete", "hel"])`
  printed `begin`, not `hello`. cyclopts 5 claims `__complete` before command
  lookup, so the registered handler was dead; only `main()`'s fast path was tested.
