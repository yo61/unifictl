"""Infrastructure layer — I/O adapters (HTTP client, config, backups).

Isolated from ``domain`` and ``application`` (enforced by import-linter) so the
UniFi client stays a faithful implementation of unifi-mcp's documented
private-API contract. See ``SPEC.md`` §3.
"""
