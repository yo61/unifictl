## Decision: Local DNS records belong to Terraform, not unifictl (for now)

`unifictl` will **not** add CRUD for local DNS records. These records are
declarative steady-state config and are managed with Terraform's
`unifi_dns_record` resource (`filipowm/unifi`). Revisit only if a concrete
imperative, time-ordered DNS use-case appears that Terraform cannot express.

## Context

A request came in to add CRUD for local DNS records. Probing the live UDM Pro
(read-only) confirmed the records persist in the v2 collection
`GET /proxy/network/v2/api/site/<site>/static-dns`, returning a bare JSON array
of records shaped `{_id, enabled, key, value, record_type, ttl, port, priority,
weight}`. On current firmware these are created via **Settings → Policy Engine →
Policy Table → Create New Policy → "DNS"**; that UI path is presentation only —
the records still store in `static-dns` (no separate policy object holds the DNS
data; the obvious `policy`/`policies`/`policy-table` endpoints 404 and
`trafficrules` is empty).

Terraform's `filipowm/unifi` provider already ships a first-class
`unifi_dns_record` resource **and** data source targeting that same collection,
covering more record types (A/AAAA/CNAME/MX/NS/PTR/SOA/SRV/TXT) than a first cut
would.

## Alternatives considered

- **Full CRUD in unifictl (`dns list/set/delete/show`)** — the original request.
  Rejected: duplicates Terraform and, if any DNS is managed in Terraform, every
  `terraform plan` fights the CLI's writes (state drift).
- **Read-only `dns list` convenience in unifictl** — rejected: SPEC §7 already
  says reads belong to `unifi-mcp`, and a read-only lister earns little.
- **Manage DNS with Terraform `unifi_dns_record`** — chosen.

## Reasoning

`unifictl`'s charter (SPEC §1) is imperative, time-ordered actions the
declarative tools can't express — e.g. breaking a LAG for a PXE boot. A
hostname→address map has a desired steady state, which is exactly what
`terraform plan`/`apply` reconciles. The feature's premise (per-record CRUD) does
not fit the tool; the right home already exists and is more complete.

## Trade-offs accepted

- By-hand DNS edits go through a `plan`/`apply` cycle rather than a one-line CLI
  command. Accepted: it keeps a single source of truth and avoids drift between
  two controllers of the same resource.
- If a genuinely imperative DNS need ever appears, this decision is revisited
  rather than assumed permanent — hence "for now".

## Supersedes

None. First decision on DNS records.
