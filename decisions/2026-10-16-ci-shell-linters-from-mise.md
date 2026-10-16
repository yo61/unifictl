## Decision: CI installs shellcheck and shfmt from `mise.toml`

CI's `lint` job installs the two shell linters with `jdx/mise-action` (`install_args: shellcheck
shfmt`), at the exact versions `mise.toml` pins for the local hooks. Renovate's `mise` manager owns
those two pins; the rest of `mise.toml` is disabled in `renovate.json5`.

## Context

CI installed shfmt v3.14.1 with `go install` and used the runner's shellcheck, while `mise.toml`
pinned both for local hooks as `3.14` and `0.11`. Nothing updated the CI shfmt pin, the two shfmt
pins had to be bumped together by hand, and CI's shellcheck could differ from the local one
(GLB-41).

## Alternatives considered

- **A `# renovate:` comment on a `SHFMT_VERSION` in `ci.yaml`**, as yo61/flux-homelab does (it has
  no `mise.toml`). Leaves shfmt with two pins and shellcheck unpinned in CI.
- **`jdx/mise-action` installing only these two tools** (taken), as yo61/kuard's CI installs its
  hook tools (`decisions/2026-10-15-prek-hooks-without-pins.md` there).

## Reasoning

One pin per tool, in the file the local hooks already use, with one owner. Dependabot supports
neither `mise.toml` nor annotated workflow values, so the owner is Renovate. mise installs both
through aqua, which verifies checksums.

## Trade-offs accepted

- One more SHA-pinned action, `jdx/mise-action` v5.1.1 (outside the 7-day cooldown), which
  Dependabot updates.
- The two pins are exact, so every shellcheck or shfmt release is a Renovate PR.
- uv, task and node in `mise.toml` still have no updater; CI gets uv and task from their setup
  actions, not from `mise.toml`.

## Supersedes

None.
