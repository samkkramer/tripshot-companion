# Changelog

## 2026-10-17 — Reliability prerequisites

- Scheduled future MCP/CLI lookups no longer load live TripShot configuration.
- Location journey planning propagates invalid-date results instead of raising `KeyError`.
- Timetable caches validate nested table structure, tolerate malformed status timestamps/types, and fall back to validated history or bundled tables with warnings.
- Added offline regression coverage for configuration independence, date errors and corrupted caches. Existing MCP signatures and fields preserved.

## 2026-10-17 — Initial consolidated local baseline

This is the first Git baseline of an existing application developed through v10. Earlier version references describe development stages, not earlier commits.

- Audited the existing read-only TripShot integration, complete four-direction 2026–27 schedules, journey planning, and 16-tool stdio MCP interface.
- Recreated the development virtual environment after confirming copied pip launchers targeted the Downloads runtime; retained `.venv-migration-backup/` locally and ignored it.
- Added a tested dependency snapshot, complete offline regression runner, and portable synthetic-fixture MCP smoke test with exact tool inventory checks.
- Fixed timetable normalization order for Northwestern's Sherman / Emerson (NB) alias to TripShot's (IB); added a regression reproducing the official label. No tool contracts changed.
- Replaced accumulated README instructions, added project status, durable agent guidance, tool inventory, audit findings, and a Service Updates design with acceptance tests.
- Expanded ignore rules to retain three synthetic JSON fixtures while excluding local imports, response captures, timetable state/history, backups, executables, environments, and secrets.
- Verified 65 regressions, local MCP handshake/discovery/invocation, dependency consistency, and all four current official timetable pages in an isolated cache. Both TripShot route requests succeeded with zero matching arrivals at check time.
- Service Updates remain unimplemented; original runtime and tunnel were not changed. No remote or deployment was created.
