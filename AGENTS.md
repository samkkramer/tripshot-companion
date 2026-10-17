# Repository guidance

- Maintain the existing Python application; make small, reviewable changes. The v6 folder contains consolidated v10 code.
- Work only in this development checkout. Never modify the Downloads runtime or read/change/start Secure MCP Tunnel configuration, credentials, or client.
- TripShot access stays read-only, unauthenticated HTTPS GET to the validated Northwestern host and observed route paths. Do not add cookies, tokens, retries, polling, or write endpoints without explicit authorization.
- Preserve MCP tool names, arguments, defaults, and output fields. Explain and test any justified contract change; inventory is in `docs/MCP_TOOLS.md`.
- Distinguish saved snapshots, approximate schedules, reported ETAs, and verified observations. Fetch/update timestamps and live-group membership do not prove GPS prediction accuracy. Empty/error responses do not prove absence of service.
- Run `.\.venv\Scripts\python.exe run_regressions.py` and `.\.venv\Scripts\python.exe test_tripshot_mcp_local.py` after relevant changes. Use the real MCP SDK. Keep regression tests offline; isolate refresh caches in temporary directories.
- Use `.\.venv\Scripts\python.exe -m pip`, not copied environment launchers. Recreate a copied `.venv`; never repair the original runtime.
- Before staging, inspect the candidate list and scan only intended source/docs/synthetic fixtures for credentials without printing matches. Never stage local data, raw responses, environment files, binaries, tunnel configuration, backups, or caches. Preserve synthetic fixtures needed by tests.
- Do not create remotes, push, deploy, or contact others without authorization.
- Keep README for operation/architecture, PROJECT_STATUS for current facts/priorities, CHANGELOG for changes, and detailed findings/plans under docs. Historical playbook claims require verification.
- Service Updates are separate from timetable refresh. The owner approved implementation of `docs/SERVICE_UPDATES_PLAN.md`: demand-driven 15-minute TTL, 5-minute error retry doubling to 60 minutes, force refresh, explicit uncertainty, preserved source evidence/history, no scheduler. Confirmed disruptions exclude journeys while original schedule records remain available; uncertain disruptions downgrade confidence.
