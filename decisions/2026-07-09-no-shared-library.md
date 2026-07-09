## Decision: No shared code library with unifi-mcp; align to its documented contract instead

`unifictl` will not extract or depend on a shared `unifi-core` package with
`unifi-mcp`. Instead it re-implements the private controller-API client in
Python and stays consistent with `unifi-mcp`'s documented contract for that API.
The client stays isolated in `infrastructure/` as ordinary hygiene.

## Context

The proposal and the first `SPEC.md` draft proposed extracting a shared
`unifi-core` library once `unifi-mcp` also spoke the legacy REST API, and made
"extraction-ready" client isolation a first-class goal. On inspecting the
`unifi-mcp` repo, it is a **TypeScript/Node** project (pnpm, vitest, oxfmt), and
its legacy-controller-API work exists only as an approved design doc
(`docs/superpowers/specs/2026-07-05-legacy-controller-api-design.md`),
unimplemented. `unifictl` is planned as **Python** (mirroring jobhound).

## Alternatives considered:

- **Shared code library (`unifi-core`)** — the original plan. Impossible: no
  runtime spans TypeScript and Python without a service boundary neither tool
  wants.
- **Rewrite one tool in the other's language** — out of scope; both are
  established in their stacks for good reasons (MCP/Node vs. jobhound-style CLI).
- **Shared documented contract, re-implemented per language** — chosen.

## Reasoning

Cross-language means the only shareable thing is the *contract*, not the code:
endpoints, auth model, the `{site}` = internal-reference quirk, TLS/CA handling,
and the `port_overrides` shape. `unifi-mcp`'s legacy-API design doc already
documents that contract, so it becomes the reference and `unifictl` re-implements
against it. Client isolation is still worth keeping — as hygiene and to give the
contract one authoritative home — just not as a path to extraction.

## Trade-offs accepted

- The private-API client logic is implemented twice (once per language) and must
  be kept in sync by hand as the contract evolves. Accepted: the surface is
  small (a handful of endpoints), and a service boundary would be far heavier.

## Supersedes

The proposal's "Shared library with unifi-mcp" section and the "extract
`unifi-core`" ADR, both written before the language mismatch was known.
