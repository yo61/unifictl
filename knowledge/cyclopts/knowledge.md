# cyclopts — knowledge

## 4.25.2 → 5.0.0 (PR #67, 2026-10-02)

Measured by running the same 14 invocations through `unifictl.cli.app` under
both versions.

| Invocation | 4.25.2 | 5.0.0 |
|------------|--------|-------|
| Unknown flag or command | exit 1 | exit 2 |
| `profile set lab site -- -x` | usage error | parses; `-x` is the value |
| `-- completion zsh` | ran | usage error |
| `Completion zsh` (wrong case) | matched | usage error |
| `--profile` before, between, or after the subcommand | applied | applied |
| `app(["__complete", ...])` | unknown-command error | answered by cyclopts' own completion engine |

- **`__complete` is reserved in 5.** cyclopts intercepts it before command
  lookup. unifictl is unaffected because `main()` dispatches `__complete`
  before cyclopts is imported, and never registered it as a command. jobhound
  had registered it and had to remove the registration (jobhound #195).
- **"Child wins" fallthrough** only applies when a subcommand defines the same
  flag as the meta launcher. No unifictl subcommand defines `--profile`.
- **The suite passed unchanged on 5.0.0.** No test asserted a usage-error exit
  code, so CI was green across a user-visible exit-code change.
- **Lockfile:** `rich-rst` moved 1.3.2 → 2.2.0 and `docutils` dropped out.

## How unifictl uses cyclopts

- `cli.app()` calls `get_app().meta(...)`; the meta launcher takes `*tokens`
  plus `--profile` and forwards to `app(tokens)`.
- `commands/_complete.py` imports neither cyclopts nor rich; see
  `decisions/2026-07-14-completion-static-tree-drift-guard.md`.
