## Decision: unifictl's Homebrew bump will hit Homebrew's 24h release cooldown — apply the jobhound self-healing fix

The tap's `bump-unifictl.yaml` regenerates resources with
`brew update-python-resources`, dispatched seconds after a release publishes.
Homebrew hardcodes a 24h "release cooldown" (`RELEASE_COOLDOWN_DAYS = 1`, no env
override) so its resolver **ignores any PyPI upload younger than a day**. The
bump will therefore fail on unifictl's next release with:

```
pip install ... --uploaded-prior-to=<now-24h> unifictl==<new-version>
Unable to determine dependencies for "unifictl==<new-version>"
```

When it does, apply the same self-healing fix already shipped for jobhound.

## Context

Surfaced on jobhound 0.17.0 — the first jobhound release to run through the
tap's new bottle pipeline. The one-shot `bump-jobhound` dispatch failed in
`update-python-resources` for exactly this reason. `bump-unifictl.yaml` uses the
identical pattern (`repository_dispatch` → `brew update-python-resources`, no
`schedule`), so it has the same latent bug; it simply hasn't been triggered by a
release yet.

## Remedy (already proven on jobhound)

Mirror `bump-jobhound.yaml`:

- Add a `schedule` trigger and a **cooldown gate**: resolve the target version
  (dispatch payload, workflow input, or latest on PyPI for scheduled runs) and
  only bump when it is newer than the formula, has no open `bump/*` branch, and
  is **>24h old**. Inside the cooldown the run is a graceful no-op that defers to
  the next scheduled run.
- Add a `skip_cooldown` `workflow_dispatch` input for emergencies: it bypasses
  the gate and skips `update-python-resources` (the only cooldown-enforcing
  step), bumping url/sha256 and reusing the existing resource stanzas. Valid for
  an urgent unifictl-self fix (dependency set unchanged); a compromised
  *dependency* still needs a direct uv/pip re-resolve.

## References

- Fix PR on the tap: yo61/homebrew-tap#46 (`bump-jobhound.yaml`).
- Decision on the tap:
  `decisions/2026-07-10-jobhound-bump-cooldown-retry.md` in yo61/homebrew-tap.
- Homebrew cooldown constant: `Library/Homebrew/release_cooldown.rb`
  (`RELEASE_COOLDOWN_DAYS = 1`), applied in `Library/Homebrew/utils/pypi.rb`.

## Trade-offs accepted

Same as the jobhound fix: the formula/bottles lag a release by ~24-30h in the
normal path (the `skip_cooldown` lever covers urgency), and the schedule runs a
cheap no-op several times a day.
