# TripShot Companion

An existing read-only Python MCP application for Northwestern shuttle information. The folder name ends in v6; the consolidated code includes v10 timetable maintenance. Keep the maintained checkout separate from any legacy runtime. Changing an operational Secure MCP Tunnel requires separate authorization.

## Architecture and data sources

`server.py` exposes 18 stdio MCP tools over the installed Python SDK (the original 16 plus Service Updates query/refresh). Domain modules also work through local CLIs:

```text
MCP client → server.py
  ├─ tripshot_core → synthetic or explicitly configured ride snapshot
  ├─ stops_catalog / nearby_stops → manually imported local stop IDs/names/GPS
  ├─ shuttle_now → tripshot_provider → allowlisted TripShot HTTPS GET
  │                 └─ live_groups + tripshot_enrichment → states/ETAs/directions
  └─ published_full → bundled four-direction schedules + local timetable overlay
                       └─ published_sync → four official Northwestern HTML pages
  Departure/journey results ← service_updates → conservative notice interpretation
                                  └─ official Service Updates page + independent cache
```

TripShot route-group responses are retrieved once per configured route/service day, without authentication headers or cookies. Near midnight, adjacent service days are fetched and duplicate records removed. Upcoming results normally cover four hours. Live-group membership and recent ETA timestamps do not prove GPS prediction accuracy.

Published 2026–27 tables cover Loop clockwise/counterclockwise (13 stop occurrences each) and Intercampus Evanston→Chicago (18) / Chicago→Evanston (12). They support future departures and same-vehicle board/alight planning. Nearby stops use imported GPS and straight-line distances, without a walking network, transfers, or accessibility routing.

Timetable refresh checks four fixed [official schedule pages](https://www.northwestern.edu/transportation-parking/shuttles/routes/), validates tables, detects semantic changes and retains fallback/history. It runs on demand during schedule operations: normally every 24 hours, retry after errors every 2 hours. Calendars and service hours remain bundled rules. [Service Updates](https://www.northwestern.edu/transportation-parking/service-updates/) are evaluated separately through an independent on-demand cache, never written into timetable cells.

Service Updates use a 15-minute success TTL and error retries at 5, 10, 20, 40, then 60 minutes. Confirmed cancellations and unserved boarding/alighting stops exclude affected journey recommendations while retaining original schedule evidence. Uncertain dates, directions, stops, truncations, conflicting notices or failed refreshes produce warnings/provisional recommendations. Departure rows preserve their scheduled/reported times and carry disruption annotations. Special-service announcements are surfaced without inventing departure times. No absence/error result confirms normal service, and there is no background scheduler.

See [tool schemas](docs/MCP_TOOLS.md), [current status](PROJECT_STATUS.md), [historical audit](docs/REPOSITORY_AUDIT.md), and [Service Updates implementation/review workflow](docs/SERVICE_UPDATES_IMPLEMENTATION.md). The [approved plan](docs/SERVICE_UPDATES_PLAN.md) and [playbook](docs/AI_Integration_Development_Playbook.md) preserve design/history; current code and tests remain authoritative.

## Installation (Windows PowerShell, Python 3.14)

Create the environment in this checkout. Never copy or activate the original runtime's environment. During migration, the copied environment was retained as ignored `.venv-migration-backup/` and a new local `.venv` created.

```powershell
Set-Location (Join-Path $env:USERPROFILE 'Projects\TripShot_MCP\TripShot_MCP_Starter_v6')
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check
```

If `python` is unavailable, invoke your installed Python 3.14 executable by its full path; this machine's Python launcher did not enumerate installations. No environment activation is required. Always use `python.exe -m pip` from this checkout. A moved environment's `pip.exe`/`mcp.exe` may still launch the old runtime.

Direct dependencies are `mcp>=2,<3` and `tzdata>=2025.2` in `requirements.txt`. The migration verified Python 3.14.7 / MCP 2.3.0 / tzdata 2026.5; `requirements-lock.txt` snapshots transitive versions on Windows. To deliberately evaluate newer compatible dependencies, install from `requirements.txt`, run the checks below, and review changes before updating the snapshot. Linux/macOS installs should use `requirements.txt`; the snapshot includes Windows-specific packages.

## Tests

```powershell
.\.venv\Scripts\python.exe run_regressions.py
.\.venv\Scripts\python.exe test_tripshot_mcp_local.py
```

The runner disables both automatic refresh sources, requires the real MCP SDK, and runs `tests/` plus the root version/limit modules (105 tests after Service Updates). This includes automated SU01–SU21 acceptance scenarios, five reliability regressions and further integration/transport tests. Default unittest discovery alone does not include all tests. The smoke test launches/closes its own local subprocess, verifies all 18 names, invokes the synthetic ride and queries cached Service Updates. It needs neither imported data nor a tunnel and cannot validate GPS accuracy or a remote connection. Contract regression checks require Git and the retained baseline commit.

## Local operation

Use these offline demonstrations without importing TripShot data:

```powershell
$env:TRIPSHOT_DISABLE_SCHEDULE_REFRESH = '1'
$env:TRIPSHOT_DISABLE_SERVICE_REFRESH = '1'
.\.venv\Scripts\python.exe demo.py
.\.venv\Scripts\python.exe published_schedule_cli.py routes
.\.venv\Scripts\python.exe published_schedule_cli.py departures 'Central L' 2026-10-19T08:15
.\.venv\Scripts\python.exe published_schedule_cli.py trip 'Emerson/Maple (EB)' 'Sheridan/Haven - Tech (SB)' 2026-10-19T08:00
.\.venv\Scripts\python.exe timetable_sync_cli.py status
.\.venv\Scripts\python.exe examples/service_updates_demo.py
```

Use dates within the published service calendar; the example dates are fixed baseline examples. Results are approximate schedule entries, not confirmation of operation. Remove the environment flag to permit on-demand automatic timetable checks:

```powershell
Remove-Item Env:TRIPSHOT_DISABLE_SCHEDULE_REFRESH -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe timetable_sync_cli.py check
# Explicit immediate recheck, bypassing throttle:
.\.venv\Scripts\python.exe timetable_sync_cli.py force
```

Explicit refresh still fetches pages when the automatic-refresh flag is set. Changes are local data writes only; no TripShot or university data is modified. Failed refreshes retain prior tables and report status; that does not establish normal service.

For authorized current lookups, import only a saved stop response body (not headers/HAR/browser credentials), then configure the observed public Loop and Intercampus `live?day=` URL templates interactively:

```powershell
.\.venv\Scripts\python.exe import_stops.py data/stops_response.json
.\.venv\Scripts\python.exe configure_sources.py
.\.venv\Scripts\python.exe shuttle_now.py Emerson --limit 8
.\.venv\Scripts\python.exe nearby.py 42.052 -87.685 --limit 5
```

Local files `data/stops_catalog.local.json`, `data/stop_names.local.json`, `data/sources.local.json`, response captures and both refresh caches/history are ignored. A fresh clone has only synthetic fixtures and bundled tables; catalog/configuration import is a separate local step. Future scheduled queries work without live-source configuration. Invalid location-journey dates propagate errors, and malformed timetable caches fall back to validated history or bundled schedules.

Saved-data tools optionally use `TRIPSHOT_JSON_PATH` (ride), `TRIPSHOT_STOP_NAMES_PATH` (name mapping), and `TRIPSHOT_LIVE_JSON_PATH` (route-group response). Never point development tools to production-private files. The default ride is synthetic; the default route-group file `data/live_response.json` is not supplied. See diagnostic CLIs in the audit for optional snapshot investigations.

## Local MCP usage

Configure a local stdio-compatible MCP client to launch this development interpreter and server, with this checkout as its working directory:

```json
{
  "command": "C:\\path\\to\\TripShot_Companion\\.venv\\Scripts\\python.exe",
  "args": ["-u", "C:\\path\\to\\TripShot_Companion\\server.py"]
}
```

This is a local client example, not a tunnel configuration. Running `server.py` directly waits for protocol input; verify with the smoke test instead. Tools include current/future departures, snapshots, stop discovery/proximity, scheduled journeys, timetable status/refresh, and Service Updates; [all 18 signatures](docs/MCP_TOOLS.md) are documented separately. Client-side discovery may need refreshing after schema changes. This development work does not restart, reconnect, or reconfigure the existing ChatGPT tunnel.

## Service Updates review

Call `get_service_updates(refresh=False)` to inspect cache without network, `get_service_updates(route="Intercampus", when_local="2026-10-19T08:00")` for applicable notices, or `refresh_service_updates(force=True)` for an explicit check. To enable automatic Service Updates checks after offline work, remove `Env:TRIPSHOT_DISABLE_SERVICE_REFRESH`; the timetable flag remains independent. Explicit refresh tools bypass their automatic-disable flags.

The current official October 16 notice omits its year, so default interpretation remains uncertain. An explicit reviewed year can be supplied in ignored `data/service_updates/reviewed_years.json`, tied to that notice's exact evidence revision and including reviewer, reason and aware timestamp. Changed source wording invalidates the review. See [the documented format](docs/SERVICE_UPDATES_IMPLEMENTATION.md); no review has been silently created for production data.

The offline demo uses a synthetic paraphrase and explicit 2026 fixture review: the original **October 16, 16:32 Central L (EB)** schedule record remains visible, changes from `uncertain` to `unavailable`, and affected same-vehicle journeys move to `excluded_options`. It makes no external requests and uses only a temporary cache.

## Security and contribution

Before publication, follow the [GitHub publication review](docs/PUBLICATION_REVIEW.md) and run `scripts/audit_publication.py --staged` plus `--history`. Publish reviewed Git content, not a bulk upload of this working directory: ignored local data and credentials are not protected by a manual ZIP upload. Personal author attribution is retained with permission; older commits still contain non-credential machine/deployment metadata despite cleanup of the current documentation.

The operational `tripshot-local` profile still launches the Downloads runtime. See the [controlled cutover and rollback runbook](docs/DEPLOYMENT_RUNBOOK.md) for verified readiness, pending notice interpretations, exact Windows PowerShell steps and end-to-end acceptance. Explicit approval is required before changing/stopping/starting that operational tunnel; no cutover has been executed.

Keep access read-only and limited to the validated hosts/endpoints. Do not add credentials, authenticated browser sessions, continuous polling, external writes, or deployment as routine changes. Inspect all candidate paths before staging; never commit secrets, local response data, environments, binaries or tunnel configuration. The three shipped JSON fixtures are synthetic. Do not publish the stdio server as an unauthenticated hosted endpoint.

Follow [AGENTS.md](AGENTS.md), record changes in [CHANGELOG.md](CHANGELOG.md), and preserve tool contracts. Git baseline is local only; no remote or push is configured by this migration.
