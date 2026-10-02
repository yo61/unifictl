# Knowledge index

Routes to one folder per domain. Each folder holds three files:

- `knowledge.md` — facts and patterns observed
- `hypotheses.md` — claims that need more evidence, each with its evidence count
- `rules.md` — confirmed claims, applied by default

A hypothesis confirmed three or more times is promoted to a rule. A rule
contradicted by new data is demoted back to a hypothesis.

Related records: `decisions/` holds why a choice was made, `quality/criteria.md`
holds what to check before calling work done.

## Domains

| Domain | Folder | Covers |
|--------|--------|--------|
| cyclopts | [`cyclopts/`](cyclopts/) | The CLI framework: parsing behaviour, version differences, upgrade notes |
