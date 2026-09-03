# Quality criteria — unifictl

Evaluate a change against these before calling it complete. Each block is one
category; `blocking` criteria must pass, `warning` criteria must be consciously
accepted and noted.

Maintenance rules (from the global standards): note the date when a criterion
catches a real issue; promote a criterion triggered 3+ times to **always check**
(run it automatically rather than listing it); suggest pruning anything never
triggered after 10+ evaluations; propose new criteria rather than adding them
silently.

Related: `decisions/` records why choices were made; this file records what to
check. A criterion that keeps firing usually deserves a decision record.

---

## Category: UniFi API field mapping

## Criteria:

    - A raw controller field is not copied into the domain until its meaning has
      been checked on **every device type the command can return** (`uap`,
      `usw`, `udm`/`ugw`/`uxg`). Fields such as `ip` change meaning by type.
    - Where a corrective field exists, prefer its presence as the signal over a
      hardcoded device-type list — `lan_ip or ip`, not `if type == "udm"`.
      Type lists silently break on unreleased models.
    - A field chosen by name alone is verified against a second, independent
      source before use. `config_network.ip` and `connect_request_ip` both look
      like a gateway's LAN address and both are wrong.
    - `--json` output stays a faithful passthrough of the controller objects.
      Corrections belong in the table, never in the raw dump.

## Severity: blocking

## Source: decisions/2026-09-03-device-ip-field-layering.md — `list devices`
reported the UDM Pro's public WAN address in a column of LAN addresses.

## Last triggered: 2026-09-03

---

## Category: Layering and architecture

## Criteria:

    - `uv run lint-imports` passes: infrastructure imports neither domain nor
      application; `commands -> application -> domain` is one-directional.
    - Domain functions take and return plain data, with no cyclopts, rich, or
      httpx types in their signatures.
    - Presentation defaults (placeholders, padding, colour, truncation) live in
      the command layer. The domain reports absence as `""`/`None` so `--json`
      and the dataclasses stay honest.
    - No relative imports; absolute `unifictl.*` paths only.

## Severity: blocking

## Source: pyproject.toml `[tool.importlinter]`; SPEC.md §3; global standards.
Applied 2026-09-03 to place the `-` WAN placeholder in `_render_devices`
rather than `device_summary`.

## Last triggered: 2026-09-03

---

## Category: Test coverage and TDD

## Criteria:

    - The test was written first and **observed failing for the intended
      reason** before the implementation existed. A test that passed on first
      run is a regression guard, not a driver — label it as such.
    - Fixtures cover every variant the code path can encounter, not just the
      common one. A suite modelling only switches cannot catch a gateway bug.
    - Every error branch the code handles has a test that triggers it.
    - Behaviour is asserted, not implementation. A refactor that breaks tests
      without breaking behaviour means the tests were wrong.

## Severity: blocking

## Source: global standards (TDD, test edges); 2026-09-03 — every device
fixture in the suite was a `usw`, so nothing exercised a device where `ip` and
`lan_ip` diverge.

## Last triggered: 2026-09-03

---

## Category: Secrets and privacy in published artefacts

## Criteria:

    - Reserved documentation ranges (RFC 5737 `203.0.113.0/24`,
      `192.0.2.0/24`) are used in **every artefact that leaves the machine** —
      fixtures, docs, commit messages, PR and issue bodies, review comments —
      never a real public IP, key, or internal hostname taken from live
      probing. Redacting afterwards does not undo it: GitHub keeps body and
      comment edit history, readable by anyone who can see the thread.
    - Scope is checked per artefact, not once per change. Sanitising the diff
      says nothing about the PR description written from the same probe output.
    - `credentials.toml` is written `0600` atomically, and reads reject a
      group/world-readable file.
    - Profile files never hold secrets; only the credential store does.
    - Live-controller probe output stays in the scratchpad and is not committed.

## Severity: blocking

## Source: decisions/2026-07-13-separate-credential-store.md;
decisions/2026-07-12-config-profiles-inline-secrets.md. 2026-09-03 — a live
probe surfaced the real WAN address; it was substituted with `203.0.113.7` in
the fixtures and decision note, then pasted verbatim into the PR #39 body on a
public repo. Widened from "fixtures and documentation" to every outbound
artefact after that miss, since the internal-only hostname meant the PR body
was the first public disclosure of the address.

## Last triggered: 2026-09-03 (twice)

---

## Category: Shell completion

## Criteria:

    - Any change to a command, sub-command, or flag updates the hand-mirrored
      tables in `commands/_complete.py`.
    - `tests/test_completion_tree_drift.py` and the literal expectations in
      `tests/test_complete.py` both pass — the two guard different things and
      both must be updated.
    - The completion fast-path still imports neither cyclopts nor rich.
    - New flags complete in bash, zsh, and fish.

## Severity: blocking

## Source: decisions/2026-07-14-completion-static-tree-drift-guard.md — the
tree is duplicated deliberately for startup speed, so the guard is the only
thing keeping it honest.

## Last triggered: 2026-09-03

---

## Category: Destructive and write operations

## Criteria:

    - Any controller write snapshots the prior state to a timestamped backup
      first, and reports the backup path on success.
    - A diff of the computed change is shown before applying.
    - `--dry-run` applies nothing; confirmation is required unless `--yes`, and
      `--yes` still writes the backup.
    - Read commands issue no writes.

## Severity: blocking

## Source: decisions/2026-07-09-lag-toggle-model.md; `commands/set.py`,
`infrastructure/backup.py`.

## Last triggered: never

---

## Category: Verification integrity

## Criteria:

    - Gate commands are run whole and their exit status checked. Never pipe a
      lint or test command through `tail`/`head` — the pipeline reports the
      pager's status and hides the failure.
    - `task dev:check` passes end to end. A gate that short-circuits early
      (e.g. at `fmt-check`) has not run the later stages — re-run after fixing.
    - Success is claimed only after the output has been read, not because a
      command was issued.

## Severity: blocking

## Source: global standards (zero warnings); prior session — a gate piped
through `tail` masked a non-zero exit. 2026-09-03 — `dev:check` exited 201 at
`fmt-check`, leaving typecheck, imports, and tests unrun.

## Last triggered: 2026-09-03

---

## Category: Commits and release hygiene

## Criteria:

    - Conventional Commits, imperative mood, subject <= 72 chars; commitlint
      passes.
    - One logical change per commit. A bug fix and a feature ship as separate
      commits so release-please files each under the right changelog heading.
    - Never commit directly to `main`; never push to `main`.
    - Commit bodies describe what the code does now, in plain language — no
      "critical", "robust", "comprehensive"; no discarded alternatives.

## Severity: warning

## Source: global standards; release-please-config.json. 2026-09-03 — the
gateway IP fix and the `--wan` flag were split so both reach the changelog.

## Last triggered: 2026-09-03
