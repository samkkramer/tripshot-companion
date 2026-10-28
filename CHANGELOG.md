# Changelog

## 2026-10-28 — GitHub publication security review

- Expanded ignore rules to cover the screenshot's missing dependency-directory rule and additional local/private artifact types.
- Scanned current publication files and all existing Git history locally with Gitleaks and an independent object/content guard; no credential findings detected. Kept approved author attribution and disclosed historical non-credential metadata without rewriting history.
- Removed personal machine paths and actual profile/tunnel fingerprints from current public documentation, preserving portable cutover templates and private backup verification instructions.
- Added a reusable redacted publication audit, six offline regression tests, and a publication checklist. All 111 tests and the 18-tool MCP smoke test pass; application behavior and dependencies are unchanged. No remote, push, operational profile access or deployment was performed.

## 2026-10-17 — Deployment-readiness review and controlled cutover plan

- Reverified 105 regressions, real 18-tool MCP smoke and dependency consistency. A local MCP session from an unrelated directory successfully refreshed official Service Updates and queried future schedules and journeys with alerts enabled.
- Confirmed the development catalog and both live-source templates exist/validate without displaying configuration contents. Documented missing-year/scope review proposals without approving them.
- Inspected official OpenAI guidance, installed tunnel-client 0.0.16 help and whitelisted existing profile metadata. Prepared exact PowerShell backup/change/doctor/run and rollback procedures with single-instance guards and seven ChatGPT acceptance tests.
- Documentation only: original profile/runtime unchanged; no tunnel started, credentials copied, remote configured, hosting or deployment performed. Authenticated diagnostics and cutover await owner approval and a trusted runtime-key-loaded operator shell.

## 2026-10-17 — Departure/journey integration and development verification

- Preserved all 16 existing MCP signatures/defaults and existing scheduled/ETA fields. Added service-health/provenance fields and per-record disruption annotations to current/future departures and scheduled journeys.
- Confirmed cancellations/unserved boarding or alighting stops exclude journey recommendations. Original options/counts remain available; uncertain notices, unresolved truncations, conflicting restorations and unavailable refreshes produce provisional recommendations.
- Pinned one exception revision throughout each response, including location journey comparisons. Added read-only `get_service_updates` and `refresh_service_updates` tools; real stdio discovery now returns 18 tools.
- Added hash-bound local reviewed-year context with reviewer/reason/timestamp, without automatic year inference. Source wording changes invalidate that review. Added an offline October 16 before/after demonstration.
- Verified 105 regressions (including all SU01–SU21 scenarios), real MCP handshake and two tool invocations, and the offline demonstration. Actual official HTML parses successfully in an isolated cache. No new dependencies, tunnel/runtime changes, remote, scheduler, infrastructure or deployment.

## 2026-10-17 — Service Updates model and refresh

- Added a bounded official-page fetcher with pre-request redirect checks, deterministic conservative parser, versioned notices, provenance, applicability evaluator, and independent local cache.
- Implemented 15-minute success TTL; 5/10/20/40/60-minute error retries, force refresh, conditional HTTP checks, OS locking, atomic manifest promotion, last-known-good recovery, history/rollback and 90-day history retention.
- Automated SU01–SU21 acceptance scenarios, plus refresh-policy and corruption regressions. Unknown years, stops/directions, dates or effects remain explicit review warnings rather than guessed cancellations.
- Validated against the actual official website: three shuttle notices parsed. The October 16 and Chicago Express notices omit explicit effective years, so they remain uncertain without evidence-bound reviewed context. No special-route departure times are synthesized.

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
