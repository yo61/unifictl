## Decision: Defer eliminating the homebrew-tap App-bypass that lands unsigned commits on `main`

Scoping note only — **not implementing now**. Records why the `yo61/homebrew-tap`
release automation leaves unsigned commits on `main`, why the obvious "sign the
bump commit" fix is only cosmetic, and what a real fix would take, so the context
survives for whenever it's picked up.

## Context

Releasing unifictl 0.3.0 (2026-07-11) surfaced this. The tap's `main` has a
`required_signatures` ruleset, yet the release added two **unsigned** commits to
`main`:

- `6ed7cfe chore(unifictl): bump to 0.3.0` — created by `bump-unifictl.yaml`
- `b379dd7 unifictl: add 0.3.0 bottle` — created by `brew pr-pull` inside
  `publish-bottles.yaml`

The PR merge-button UI showed "Merging is blocked. Commits must have verified
signatures", but the PR (#79) still merged — because `brew pr-pull` pushes
directly to `main` as the `semantic-release-pusher` App, which is a **bypass
actor** on the ruleset. The UI merge path is never used.

This is deliberate and documented. `bump-unifictl.yaml` lines 235-237:
"Branch is bump/*, not main, so the required_signatures rule does not apply here;
when pr-pull later lands this on main it pushes as the bypass App."

## Alternatives considered

- **Sign only the bump commit** (switch `bump-unifictl.yaml`'s `git commit` to
  GitHub's `createCommitOnBranch` GraphQL mutation, matching unifictl's
  `release.yaml` sync-lockfile job). Rejected as the fix: it makes 1 of the 2
  commits verified and stops the UI "blocked" message — but the UI merge path
  isn't used, and pr-pull's bottle commit (`b379dd7`) stays unsigned regardless.
  Cosmetic, not a fully-signed `main`.
- **Do nothing** — the current, coherent, documented design. What we're keeping
  for now.
- **Eliminate the bypass entirely** so `main` never carries unsigned commits —
  the real fix, deferred (see below).

## Reasoning

The blocker is `brew pr-pull`: it creates its own bottle commit with an internal
`git commit` that has no signing key, so it cannot produce a verified commit
without extra work. As long as pr-pull is the mechanism that lands bottles on
`main`, requiring signatures on `main` is incompatible with it — hence the App
bypass. Signing just the bump commit doesn't remove the bypass or the unsigned
bottle commit, so it doesn't achieve the actual goal (a `main` history where
every commit is verifiable from a trusted source). Not worth a PR on its own.

## Trade-offs accepted

- `main` on `yo61/homebrew-tap` carries unsigned commits from release automation,
  and the `required_signatures` rule is effectively not enforced for the App's
  pushes. Accepted for now: the App token is short-lived and scoped, and the
  automation path is the only writer. The residual risk is that a compromised
  runner (which holds the App token mid-run) could push arbitrary unsigned
  content to `main` via the same bypass — the rule provides no defence there.

## When picked up — scope of the real fix

Make `main` fully signed by removing the bypass. Requires signing **both** commit
sources:

1. Bump commit → `createCommitOnBranch` GraphQL mutation with the App token
   (server-signed, verified). Straightforward; mirror `release.yaml`.
2. pr-pull bottle commit → the hard part. Options to investigate: provision a
   GPG/SSH signing key for the App/runner so `brew pr-pull`'s `git commit` is
   signed; or replace pr-pull's push step with a `createCommitOnBranch` that
   re-applies pr-pull's tree changes; or move bottle attachment off `main`
   entirely (GitHub Releases only) so no bottle commit hits `main`.
3. Then drop the App from the ruleset's bypass-actors list and confirm the whole
   release flow still lands green.

## Supersedes

Nothing. Complements the documented intent in `bump-unifictl.yaml` lines 235-237
and the earlier tap cooldown decision (`decisions/2026-07-10-homebrew-bump-cooldown-gotcha.md`,
which lives in the tap repo).
