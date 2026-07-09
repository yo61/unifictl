## Decision: Authenticate the private UniFi controller API with the Integration API key

Use the Integration API key (`X-API-KEY: $UNIFI_API_KEY`) for every private
controller-API call — reads (`stat/device`) and writes (`rest/device`). Do not
build username/password session auth (cookie + CSRF); keep it as a documented,
unbuilt fallback.

## Context

The `SPEC.md` first draft assumed the API key authenticated the private surface
but hedged, and `unifi-mcp`'s legacy-controller-API design doc states the legacy
surface "uses cookie/CSRF session auth instead of `X-API-KEY`". That design
statement was never tested against the private surface — it was a carried-forward
assumption. Session auth is the most complex part of the client (login, cookie
jar, CSRF, re-login-on-401) and carries an MFA caveat (needs a dedicated local
non-MFA account), so building it on an untested assumption was a poor bet.

## Alternatives considered:

- **API-key only** — simplest; one header, no login/cookie/CSRF, no extra
  account. Risk: might be rejected on the private surface.
- **Session auth only** — matches `unifi-mcp`'s design; proven pattern elsewhere
  but unproven here, most code, MFA caveat.
- **API key with session fallback** — most robust, two code paths, both built.
- **Verify first, then build only what works** — one live request settles it.

## Reasoning

Verified against a live UDM Pro (UniFi OS) rather than guessing. Two probes with
the API key:

- `GET /proxy/network/api/s/default/stat/device` → `HTTP 200`, real device JSON.
- Idempotent no-op write on the USW 24 PoE (`mac 70:a7:41:90:82:dd`): read
  `port_overrides`, `PUT` the identical array back to
  `rest/device/6a219cf7f8fe3457418cad89` → `HTTP 200 {"rc":"ok"}`.

The key authorizes both read and write with no CSRF or session — expected on
UniFi OS, where `X-API-KEY` is stateless and doesn't participate in CSRF. So the
session-auth subsystem is unnecessary. YAGNI: don't build it until an endpoint
actually rejects the key.

## Trade-offs accepted

- No auth path for non-UniFi-OS / older controllers that require session login.
  Acceptable: the target is a UDM Pro; a fallback is documented, not built.
- The write proof was an idempotent no-op, not the real LAG toggle; a `PUT` may
  trigger a (normally non-disruptive) device re-provision. Accepted as adequate
  evidence for the write path.

## Supersedes

None. Corrects the untested auth assumption carried from `unifi-mcp`'s
legacy-controller-API design doc for the write side.
