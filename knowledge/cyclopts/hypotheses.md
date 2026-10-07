# cyclopts — hypotheses

## Changes required by a cyclopts bump in jobhound predict those needed here

- Evidence for: 1 — the exit-code pin from jobhound #195 applied directly.
- Evidence against: 1 — the `__complete` re-routing from the same PR did not
  apply, because unifictl never registered `__complete` with cyclopts.
- Related, not counted: unifictl's own notes predicted yo61/flux-homelab#597 the
  same way. The exit-code pin applied directly; `__complete` again needed nothing,
  because `homelab` also dispatches it before cyclopts is imported. That supports
  a broader claim (any sibling repo's bump predicts the next) rather than this
  jobhound-specific one.
  yo61/python-template#39 cut the other way: it registered `__complete` with
  cyclopts as jobhound had, so jobhound's re-routing applied there and not here.
