# Migration audit — 2026-10-17

## Scope and environment

Audited the Projects development copy, not the Downloads runtime. No tunnel configuration was read, changed, or started. Git was absent and initialized locally. Existing modules and contracts were retained, with one focused timetable parser fix described below.

Python 3.14.7, MCP 2.3.0, tzdata 2026.5. Original `requirements.txt` permits MCP >=2,<3 and tzdata >=2025.2; those installed versions satisfy it, and `pip check` passed. The copied interpreter ran, but `pip.exe --version` resolved to Downloads; creation metadata also referenced Downloads. Recreated `.venv` in Projects, verified its pip path, and retained the copied environment as ignored `.venv-migration-backup/`. `requirements-lock.txt` records all installed application dependency versions for this Windows/Python baseline (not hashes or a cross-platform lock).

## Inventory and data flow

| Area | Files | Responsibility |
| --- | --- | --- |
| MCP boundary | `server.py` | 16 typed tools; validation and domain calls |
| HTTP provider | `tripshot_provider.py`, `fetch_tripshot_once.py`, `configure_sources.py` | Local route templates, HTTPS allowlist, no credentials, GET, blocked redirects, bounded payload/timeouts |
| Stop catalog | `stops_catalog.py`, `import_stops.py`, `nearby_stops.py`, `nearby.py` | Manual import, ID/name/GPS join and straight-line distance |
| Current arrivals | `live_groups.py`, `tripshot_enrichment.py`, `shuttle_now.py` | Nested tagged stop states, time conversion, live/nonlive separation, direction inference, confidence, four-hour aggregation, midnight coverage and deduplication |
| Saved ride | `tripshot_core.py`, `demo.py` | Synthetic or configured snapshot inspection; stale saved vehicle position |
| Published schedules | `published_full.py`, `published_loop.py`, `published_intercampus.py` | Full four-direction tables, fixed service calendars, same-run journey planning; older schedule helpers still supply constants/calendars |
| Timetable maintenance | `published_sync.py`, `timetable_sync_cli.py` | Four-page HTML validation, SHA-256 revision, diff, atomic individual writes, local history and fallback |
| Diagnostics/CLI | `published_schedule_cli.py`, `inspect_live.py`, `inspect_route_directions.py`, `tripshot_diagnose_live.py`, `compare_etas.py` | Local exploration and explicit comparisons; not server entry points |
| Verification | `tests/test_*.py`, four root regression modules, smoke test, `run_regressions.py` | Offline fixtures, provider guards, midnight, directions, timetables, limits, refresh and real SDK transport |

Data models are ordinary dictionaries/lists rather than formal versioned domain classes. TripShot joins use stop/ride IDs. Published schedules instead use display-name normalization and synthetic run IDs. Outputs distinguish `record_type`, scheduled vs reported timestamps, confidence and source. Direction inference counts distinctive stop markers, despite its `ordered_stop_sequence` basis label; it does not actually verify their order. Navigation-ID fallback is provisional.

The local imported catalog contains 50 unique IDs with 50 numeric coordinate pairs. This verifies structure/presence, not physical GPS accuracy or exhaustive coverage. Full tables contain 13+13 Loop and 18+12 Intercampus stop occurrences (not 56 unique physical stops), with 30 Evanston→Chicago and 29 Chicago→Evanston runs per operating weekday.

## Observed verification

| Check | Result |
| --- | --- |
| Existing regressions before changes | 27 in `tests/` + 37 root tests = 64 passed using real SDK |
| Initial local smoke | Real handshake, 16 tools, imported Emerson search succeeded |
| Final offline suite | 65 passed, including official Sherman / Emerson alias regression |
| Final portable smoke | 16 expected tools; real stdio call returns bundled DEMO ride with two stops |
| Environment | Recreated interpreter/pip point to Projects; `pip check` clean |
| TripShot current fetch | Loop and Intercampus requests succeeded for 2026-10-17; zero matching Emerson arrivals at check time |
| Official timetable integration | Before fix: Evanston→Chicago rejected (17/18 stops matched); other three pages parsed. After fix: all four parsed; normalized content unchanged from bundled fallback; isolated temporary cache only |
| Official calendars | Loop and Intercampus route-page rules reviewed against bundled calendar constants; no observed discrepancy |

The initial sandbox denied Python temporary-file writes/cleanup and the first smoke stalled. That test process was stopped; approved execution outside the sandbox passed. Network checks likewise required execution outside the sandbox. These are environment restrictions, not regression failures. Current-fetch success does not verify vehicle movement, changing ETAs, GPS accuracy, or realized arrivals. No tunnel/end-to-end ChatGPT revalidation was attempted.

## Focused fix

`published_sync._norm` applied the Sherman/Emerson NB→IB alias before removing punctuation. The actual official label contains spaces/slashes/parentheses, so the alias never ran. Move punctuation normalization before the alias. A new full-four-page regression uses the actual official spelling. External validation then returned `unchanged`; no route contracts or bundled times changed. Rejecting the mismatch had correctly preserved existing data.

## Outstanding reliability findings

1. **Service exceptions absent (product priority):** no closure, temporary skipped stop, special route, revised notice, or alert freshness integration. Fixed calendars and timetable refresh cannot detect these. See the separate plan.
2. **Future lookup config coupling (reproduced):** `server.get_shuttles_at_time` and the `shuttle_now --at` CLI call `get_sources()` although the schedule implementation ignores its argument. Without local live config, valid future lookups fail; direct published CLI works. Remove the dependency in a small compatibility patch later.
3. **Invalid location-plan dates (reproduced):** `plan_trip` returns an error dictionary, but `plan_to_coordinates` indexes `trip['options']`; with a nearby served stop an invalid date produces uncaught `KeyError`. Propagate structured errors before iterating.
4. **Malformed cache handling (reproduced):** naive `checked_at_utc` causes aware/naive `TypeError`; valid JSON of wrong type (e.g. list for status) causes `AttributeError`. Active data verifies a signature and route keys, not all nested route structure. Treat cache corruption as untrusted input and fall back visibly.
5. **Calendar/shape assumptions (inspection):** refresh only updates time cells. Loop frequency/origin minutes, operating hours, seasonal breaks and holidays stay hard-coded. New stops/order changes fail closed; permissive substring aliases can also misidentify labels. Synthetic round-trips alone did not catch the official-label bug.
6. **Time semantics (inspection):** parser treats naive API timestamps as UTC; naive user dates get Chicago attached without rejecting nonexistent/ambiguous DST times. Journey tools accept dates outside the future wrapper's 30-day guard; dates beyond supported calendar scope can look like ordinary empty results. More boundary tests needed.
7. **Freshness/concurrency (inspection):** timetable checks happen during requests (24h success throttle; 2h error retry), not in background. Four sequential 8-second fetches can delay tools. No cross-process refresh lock; active/status/history are individually atomic, not one transaction. A status write failure can escape or follow active promotion. No automatic rollback command or cache-history retention limit.
8. **Snapshot/input consistency (inspection):** saved route-group tools need ignored local data; most snapshot wrappers lack friendly missing-file guards. File modification time is a snapshot-time proxy. Catalog reads mostly require UTF-8, while some helpers accept BOM; incomplete/malformed rows are not uniformly handled. `load_once` writes raw response briefly to OS temp before parsing.
9. **Observability/compatibility (inspection):** broad exceptions become coverage errors, sometimes containing exception text/paths. ETA classifier always reports unverified GPS; changes require explicit two-snapshot comparison. Stop-name joins can be ambiguous; nearest stop is not a usable journey or walkable route. Retain provenance throughout future integration.
10. **Testing/dependencies (inspection):** default root discovery does not recurse into the non-package `tests/` directory; legacy v8/v9 tests can stub missing SDK. New runner imports real SDK first and explicitly loads both groups. Timetable refresh disabling must occur before schedule calls. Broad dependency ranges may admit future API changes; use the verified snapshot and test upgrades deliberately.

## Outdated and excluded material

The old README accumulated conflicting v1–v6 instructions (including “no HTTP”); replaced with current operation guidance. `UPGRADE_V7.md` remains historical reference, not setup. Old script docstrings mentioning v3/v4/v7 are historical labels. `published_loop.lookup` and limited `published_intercampus.lookup` remain used by legacy tests; their constants/calendars are also imported by the full implementation. Do not delete them as redundant until dependencies are disentangled.

Ignored and retained locally: `.venv*`, bytecode, `.bak`/pre-version backups, `tunnel-client.exe`, `eta_before.json`, `eta_after.json`, `eta_comparison.txt`, `directions.txt`, source URLs, stop imports, timetable status/active/history, and migration scratch scripts. None is needed in Git. `data/example_live.json` had incorrectly been ignored even though tests depend on it; all three synthetic fixtures are now included.

## Security review and Git boundary

Review the exact nonignored candidate paths before staging; scan only those source, documentation and synthetic fixture bytes for credential formats/assignments, private keys, credential-bearing URLs and unexpected binary content. Report path/line/category without matched values. Manually inspect synthetic fixtures and review each candidate source via syntax/inventory and content inspection. Local `.env`, tunnel settings, browser state, credentials, raw captures and binaries are excluded without opening them. `sources.local.json` is consumed only by the existing validated provider for authorized read-only checks; its content is never displayed or staged.

No real API key/access token is required by this application or present in the reviewed baseline. This review is not a dedicated supply-chain vulnerability audit or proof that every ignored local file is secret-free. The historical playbook reports a past screenshot credential exposure; rotation cannot be verified and no credential inspection was performed. The timetable fetcher validates redirect destinations only after following them; future fetchers should block unapproved redirects before requests, as the TripShot fetcher already does.

No Git remote, push, deployment, external write, scheduled job, or production runtime change belongs to this baseline. Git initially lacked an author identity; the owner supplied a name/email for repository-local configuration. No global Git settings are changed.

Baseline review scanned 50 intended files (35 Python files also parsed successfully) and all three synthetic fixtures, with zero credential-pattern or unexpected-binary findings. Ignore checks confirmed exclusion of environments, executable, backups, raw comparison/direction outputs, sources/catalog imports, and timetable state. Recreated environment package versions exactly match the copied environment; no dependency upgrade was introduced.
