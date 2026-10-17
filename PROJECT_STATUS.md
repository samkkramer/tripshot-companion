# Project status — 2026-10-17

**Baseline:** Existing consolidated v10 application in the Projects development copy; 16 stdio MCP tools. Original Downloads runtime and Secure MCP Tunnel untouched. Local Git baseline only; no remote, deployment, or scheduled job.

**Capabilities:** Read-only Loop/Intercampus route-group retrieval; imported catalog of 50 unique stops with coordinates; nested stop-state parsing; reported vs scheduled ETAs and conservative confidence labels; inferred/provisional Loop directions; adjacent service-day queries around midnight; all four published 2026–27 direction tables; future departures, same-run journeys, nearby stops, rough destination planning; on-demand validated timetable refresh with fallback/history. Service exceptions are not integrated.

**Sources:** Observed public Northwestern TripShot route-group JSON, manual local stop imports, four official Northwestern HTML timetables, and bundled 2026–27 service-calendar rules. Saved ride defaults to synthetic data. Timetable updates and [official Service Updates](https://www.northwestern.edu/transportation-parking/service-updates/) are distinct.

**Verified:** Initial 64 existing regressions passed. Final 65 tests pass with real MCP 2.3.0; local smoke verifies 16 names and a real synthetic-fixture tool call (protocol 2026-07-28). Python 3.14.7 / tzdata 2026.5; dependency check clean. Recreated copied `.venv` after pip launcher resolved to Downloads. Live read-only requests to both configured routes succeeded on October 17, with zero matching Emerson arrivals at check time. All four official timetable pages validate and match bundled content after the focused NB/IB alias fix; check used an isolated cache.

**Not verified:** GPS prediction accuracy, changing ETAs, realized arrivals, physical coordinate accuracy, continuous availability, tunnel/ChatGPT end-to-end connection, dependency vulnerability posture, or prior credential rotation. Passing offline tests does not establish these.

**Outstanding bugs:** Future departure MCP/CLI wrapper unnecessarily requires live config; invalid location-journey date can raise `KeyError`; malformed cache type/naive timestamp can raise errors. Fixed calendar/hours are not refreshed. Direction inference uses marker presence, not actual sequence order. Cache writes lack a multi-process transaction/lock. Detailed evidence and lesser limitations are in [the audit](docs/REPOSITORY_AUDIT.md).

**Limitations:** Published times are approximate, never live confirmation; errors/empty results do not establish no service. Journey planning is same vehicle within four hours, with no transfers or routed walking/accessibility. Schedule support is bounded to 2026–27; only the future-departure wrapper applies the 30-day query limit. Special services are absent. Local catalog/config imports are intentionally outside Git.

**Next priorities:** Review the [Service Updates plan and acceptance tests](docs/SERVICE_UPDATES_PLAN.md), then implement its offline parser/model and refresh safety before applying exceptions to journeys. Use a small prerequisite patch for future-query config independence, invalid-date propagation, and malformed-cache fallback. Preserve all existing tool contracts and rerun both regression and smoke checks.
