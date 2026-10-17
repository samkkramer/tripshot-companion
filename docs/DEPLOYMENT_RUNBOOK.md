# Controlled operational cutover — tripshot-local

**Prepared 2026-10-17; NOT EXECUTED. Explicit owner approval is required before stopping the operational tunnel, backing up/editing its profile, or starting it against this repository.** Approval of cutover does not approve any notice interpretation. No new tunnel, Git repository, ChatGPT connection, key, hosting, or deployment service is needed.

## Verified readiness

Application release under review: `e233ae7` plus this documentation-only readiness commit. On October 17:

- All **105 regressions passed**; real local MCP smoke discovered 18 tools and successfully called the synthetic ride and cached Service Updates. Dependency check passed.
- A separate real stdio MCP session ran from an unrelated temporary working directory, with both automatic refresh sources enabled. Absolute Projects interpreter/server paths worked; application Python sources contain no Downloads paths. Python 3.14.7 / MCP 2.3.0 / tzdata 2026.5; pip resolves to the Projects environment.
- Official Service Updates refreshed at **2026-10-17 13:44:45 America/Chicago** (`18:44:45.900886+00:00`). Result: `refresh_status=updated`, `service_updates_status=parse_review_required`, no fetch error, three notices, `normal_service_confirmed=false`. Checked/last-success times agree. Source publication/update timestamps are null; retrieval time is not publication time.
- `get_shuttles_at_time("Emerson/Maple (EB)", "2026-10-19T08:00")` returned four schedule rows. Emerson/Maple→Tech journey at that time returned seven options; first boards 08:29 and alights 08:35. Both retain provisional warnings from the unresolved-year Intercampus notice. Loop Library/Norris→Emerson/Maple (WB), October 19 at 19:00, returned eight `schedule_only` options.
- Development catalog exists with **50 stops**; local live-source configuration exists and validates both Loop and Intercampus. No URLs/configuration contents were displayed. Optional saved route-group `data/live_response.json` is absent: the two legacy saved-route-group tools remain discoverable but require an intentional local snapshot before successful invocation. The default saved-ride/vehicle tools use synthetic data, not an operating vehicle.
- `tripshot-local` exists at `C:\Users\samkk\AppData\Roaming\tunnel-client\tripshot-local.yaml`, with one stdio command pointing to Downloads, runtime key reference `env:CONTROL_PLANE_API_KEY`, and loopback health address `127.0.0.1:8080`. No tunnel-client process was present at inspection. Recheck immediately before changing anything.
- The key is **not available in Codex's process environment**. This does not establish whether another PowerShell session has it. Authenticated doctor/start checks are deferred until the existing trusted key-loading procedure has supplied the same reference in the operator shell. Never paste a key into chat, a command argument, this repository, or the profile.

No operational profile changes, backups, tunnel startup, authenticated doctor run, ChatGPT discovery refresh, or end-to-end rollout have been performed. Only the development data caches were refreshed.

## Notices requiring owner review

Evidence was read from [Northwestern's official Service Updates](https://www.northwestern.edu/transportation-parking/service-updates/). These are proposals, **not approved interpretations**:

| Notice | Evidence and proposed interpretation | Still unresolved |
| --- | --- | --- |
| Intercampus change — Friday October 16 | A 16:30–23:10 shortened route omits Central L, Central/Jackson and Ryan Field; other stops remain served. Chicago→Evanston terminates at Patten Gym; Evanston→Chicago starts at Noyes L. **Propose year 2026**, consistent with the stated Friday and current academic context. | No explicit year in this notice; ending-boundary semantics; physical-stop directional mapping; Patten's stop/timetable linkage and changed running times. Keep uncertain until reviewed. |
| Chicago Express Fall Quarter | Academic year 2026–27 is stated; fall Saturdays listed are October 17/31, November 14/21 and December 5. **Propose those five dates in 2026.** | Date lines omit years; there is no validated Express timetable in this app. Year review must not invent departure times or add it to Intercampus schedules. |
| Wildcard reader implementation | Informational rider eligibility/tap-reader guidance, with a January 2026 testing reference. **Propose leaving informational**, with no service cancellation or effective interval applied. | No precise operational interval; conditional-wording/date warnings are preserved and do not cancel service. |

Current evidence revisions (not credentials): Intercampus `25b946258ad69c278392c5d481b3f4cae84c76c5c2489b338184b52258a90514`; Chicago Express `3a4b5f25e9ef8a96239b89ff0cf77eb789a84e9cc9e1f1f07445afc573a0c56a`. Re-fetch/review before approving; changed wording invalidates old review hashes. No `reviewed_years.json` entries were created. If explicitly approved later, use the [evidence-bound review format](SERVICE_UPDATES_IMPLEMENTATION.md); that mechanism approves a year only, not unknown scope/termini. Unknown-year warnings currently can also downgrade later Intercampus trips. This is conservative behavior, not a fetch failure.

## Documentation and installed CLI

Official [Secure MCP Tunnel guidance](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) describes local stdio forwarding, runtime-key references, doctor, foreground run and health/readiness checks. The installed client's help is the authority for exact flags here. No `init`, admin tunnel mutation, connection recreation, or client upgrade is part of this cutover.

Observed client: **0.0.16**, build `5f99daabd4aa4a77049e6d81d54a0d8c18335397`. Projects and Downloads executables have identical SHA-256 `4226bb74a72388147882881f29f79801b95e285d731a138071812e3aa6766571`. The executable is intentionally ignored by Git; retain it on disk. Read-only checks performed: `--version`, main/quickstart help, profile list, profile-edit help, sample stdio profile, run/doctor/health help. This CLI has `profiles edit`; there is no `config` command. Verified flags include `--profile-dir`, `--profile`, `--explain`, `--json`, and health `--require-control-plane-poll`.

The profile's original SHA-256 is `6cd68b523d0c5fb9da4119447fbb1af75f555d9dc39a1b93b992794c99b68b08`; the tunnel-ID fingerprint is `e7cb7a65636c` (full ID withheld). The script below fails if this reviewed profile has changed, rather than overwriting an unexpected configuration.

The **only profile change** will be its single `mcp.commands[].command` value:

```yaml
command: "C:/Users/samkk/Projects/TripShot_MCP/TripShot_MCP_Starter_v6/.venv/Scripts/python.exe -u C:/Users/samkk/Projects/TripShot_MCP/TripShot_MCP_Starter_v6/server.py"
```

Tunnel ID, API-key reference, health/logging/transport settings and every other profile byte remain unchanged. Backups stay outside Git beside the profile and contain references, not credential material. Do not back up a profile containing literal secrets; the guard below aborts if it detects them.

## Approval and operator preflight

Tell Codex: **“I approve the documented tripshot-local cutover to the Projects repository. Leave notice-year/scope reviews unchanged.”** That approval authorizes the maintenance sequence below, not new infrastructure or remote changes. Run it only after approval, in a trusted Windows PowerShell session where the existing runtime-key loading procedure has supplied `CONTROL_PLANE_API_KEY`. Do not echo or re-enter that key in command text. If the reference is missing, the script aborts before stopping/editing anything; load it using your existing private procedure and retry.

Prevent a race with another operator: use only this guarded foreground procedure for launch/rollback during the maintenance window. It holds a named system mutex for the entire run and requires zero existing tunnel-client processes. This conservatively blocks other local profiles too. An unmanaged command started outside this procedure or a client on another computer cannot be locked by this shell: confirm no other host/operator uses this tunnel ID, and do not start a second client manually. No automatic service/task should restart the old command during maintenance; if one exists, pause that launcher explicitly before proceeding. No such supervisor was configured or changed here.

### Window A — preflight, stop, backup, change, diagnose, run

**After approval**, paste the complete block in a trusted PowerShell window. It does not retrieve or copy the key; it checks only whether the existing reference is populated. If the old client is running in another terminal, use **Ctrl+C there**, wait for it and its stdio child to exit, then press Enter at the prompt. Do not close the terminal holding your only trusted key-loading context. No indiscriminate process kill is used.

```powershell
$ErrorActionPreference = 'Stop'
$tripShotRoot = 'C:\Users\samkk\Projects\TripShot_MCP\TripShot_MCP_Starter_v6'
$tripShotClient = Join-Path $tripShotRoot 'tunnel-client.exe'
$tripShotProfiles = Join-Path $env:APPDATA 'tunnel-client'
$tripShotProfile = Join-Path $tripShotProfiles 'tripshot-local.yaml'
$expectedProfileHash = '6CD68B523D0C5FB9DA4119447FBB1AF75F555D9DC39A1B93B992794C99B68B08'
$expectedClientHash = '4226BB74A72388147882881F29F79801B95E285D731A138071812E3AA6766571'
$newCommand = 'C:/Users/samkk/Projects/TripShot_MCP/TripShot_MCP_Starter_v6/.venv/Scripts/python.exe -u C:/Users/samkk/Projects/TripShot_MCP/TripShot_MCP_Starter_v6/server.py'

if (-not [Environment]::GetEnvironmentVariable('CONTROL_PLANE_API_KEY', 'Process')) {
    throw 'Runtime key reference is unavailable. Use the existing trusted key-loading procedure in this shell; do not paste a key into command text or chat.'
}
foreach ($name in @('MCP_COMMAND','TUNNEL_CLIENT_CONFIG','TUNNEL_CLIENT_PROFILE',
    'TUNNEL_CLIENT_PROFILE_FILE','TUNNEL_CLIENT_PROFILE_DIR','CONTROL_PLANE_TUNNEL_ID',
    'TRIPSHOT_JSON_PATH','TRIPSHOT_LIVE_JSON_PATH','TRIPSHOT_STOP_NAMES_PATH',
    'TRIPSHOT_DISABLE_SCHEDULE_REFRESH','TRIPSHOT_DISABLE_SERVICE_REFRESH')) {
    if ([Environment]::GetEnvironmentVariable($name, 'Process')) {
        throw "Unexpected override $name is set. Review it privately before cutover; no value was printed."
    }
}
foreach ($path in @($tripShotClient,$tripShotProfile,
    (Join-Path $tripShotRoot '.venv\Scripts\python.exe'),
    (Join-Path $tripShotRoot 'server.py'),
    (Join-Path $tripShotRoot 'data\stops_catalog.local.json'),
    (Join-Path $tripShotRoot 'data\sources.local.json'))) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required local file missing: $path" }
}
if ((Get-FileHash -LiteralPath $tripShotClient -Algorithm SHA256).Hash -ne $expectedClientHash) {
    throw 'Client binary changed since review; inspect its capabilities before proceeding.'
}
Set-Location -LiteralPath $tripShotRoot
if (@(git status --porcelain).Count -ne 0) { throw 'Git working tree must be clean.' }
git diff --quiet e233ae7 HEAD -- '*.py' 'requirements*.txt'
if ($LASTEXITCODE -ne 0) { throw 'Application code/dependencies changed since readiness verification; review and retest first.' }
git log -1 --format='%h %s'

$tripShotMutex = [Threading.Mutex]::new($false, 'Global\TripShotCompanion.tripshot-local')
$tripShotOwned = $false
try {
    try { $tripShotOwned = $tripShotMutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $tripShotOwned = $true }
    if (-not $tripShotOwned) { throw 'Another guarded TripShot operator already owns the runtime.' }

    if (@(Get-Process -Name 'tunnel-client' -ErrorAction SilentlyContinue).Count -gt 0) {
        Read-Host 'Stop the existing client with Ctrl+C in its owning terminal, wait for exit, then press Enter'
    }
    if (@(Get-Process -Name 'tunnel-client' -ErrorAction SilentlyContinue).Count -gt 0) {
        throw 'A tunnel-client is still running. No profile change was made.'
    }
    if ((Get-FileHash -LiteralPath $tripShotProfile -Algorithm SHA256).Hash -ne $expectedProfileHash) {
        throw 'Operational profile changed since review. No backup/edit performed; review it privately again.'
    }

    $originalBytes = [IO.File]::ReadAllBytes($tripShotProfile)
    $original = [IO.File]::ReadAllText($tripShotProfile)
    $apiReferencePattern = '(?m)^[ \t]*api_key:[ \t]*["'']?env:CONTROL_PLANE_API_KEY["'']?[ \t]*\r?$'
    $literalSecretPattern = '(?i)\bsk-[A-Za-z0-9_-]{15,}|\bbearer\s+[A-Za-z0-9._-]{15,}|-----BEGIN.*PRIVATE KEY-----'
    if ([regex]::Matches($original,$apiReferencePattern).Count -ne 1 -or
        [regex]::IsMatch($original,$literalSecretPattern)) {
        throw 'Profile credential/reference needs private review. Nothing was copied or edited.'
    }
    $commandRegex = [regex]::new('(?m)^(?<prefix>[ \t]+command:[ \t]*)(?<value>[^\r\n]*)(?<cr>\r?)$')
    $commandMatches = $commandRegex.Matches($original)
    if ($commandMatches.Count -ne 1 -or
        -not $commandMatches[0].Value.Contains('C:/Users/samkk/Downloads/TripShot_MCP/TripShot_MCP_Starter_v6/.venv/Scripts/python.exe') -or
        -not $commandMatches[0].Value.Contains('C:/Users/samkk/Downloads/TripShot_MCP/TripShot_MCP_Starter_v6/server.py')) {
        throw 'Expected single old stdio command not found. Nothing was copied or edited.'
    }
    $candidate = $commandRegex.Replace($original, [Text.RegularExpressions.MatchEvaluator]{
        param($m)
        $m.Groups['prefix'].Value + '"' + $newCommand + '"' + $m.Groups['cr'].Value
    })
    if ($commandRegex.Replace($original,'${prefix}<MCP_COMMAND>${cr}') -cne
        $commandRegex.Replace($candidate,'${prefix}<MCP_COMMAND>${cr}')) {
        throw 'Unexpected changes outside MCP command; aborting.'
    }

    $backupDir = Join-Path $tripShotProfiles 'backups'
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    $tripShotBackup = Join-Path $backupDir ('tripshot-local.' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '.yaml')
    Copy-Item -LiteralPath $tripShotProfile -Destination $tripShotBackup
    if ((Get-FileHash -LiteralPath $tripShotBackup -Algorithm SHA256).Hash -ne $expectedProfileHash) {
        throw 'Backup verification failed; operational profile not changed.'
    }
    Write-Host "Verified rollback backup: $tripShotBackup"

    $hadBom = $originalBytes.Length -ge 3 -and $originalBytes[0] -eq 239 -and
        $originalBytes[1] -eq 187 -and $originalBytes[2] -eq 191
    $pending = Join-Path $tripShotProfiles ('tripshot-local.' + [guid]::NewGuid().ToString('N') + '.pending')
    try {
        [IO.File]::WriteAllText($pending,$candidate,[Text.UTF8Encoding]::new($hadBom))
        [IO.File]::Replace($pending,$tripShotProfile,$null)
    } finally {
        if (Test-Path -LiteralPath $pending) { Remove-Item -LiteralPath $pending }
    }

    & $tripShotClient doctor --profile tripshot-local --profile-dir $tripShotProfiles --explain
    if ($LASTEXITCODE -ne 0) { throw 'Doctor failed. Do not start; follow rollback below.' }
    if (@(Get-Process -Name 'tunnel-client' -ErrorAction SilentlyContinue).Count -ne 0) {
        throw 'A client appeared during diagnostics. Do not start another instance.'
    }
    & $tripShotClient run --profile tripshot-local --profile-dir $tripShotProfiles
    if ($LASTEXITCODE -ne 0) { throw 'Client exited unsuccessfully; inspect redacted diagnostics and consider rollback.' }
} finally {
    if ($tripShotOwned) { $tripShotMutex.ReleaseMutex() }
    $tripShotMutex.Dispose()
}
```

The foreground call intentionally remains running. Do not launch a second `run` to check it. If any gate fails after the profile was replaced, the old runtime is still intact: use the verified backup and rollback below. An unhealthy client should be stopped before retrying or rolling back.

### Window B — verify readiness, then ChatGPT

```powershell
$tripShotRoot = 'C:\Users\samkk\Projects\TripShot_MCP\TripShot_MCP_Starter_v6'
$tripShotClient = Join-Path $tripShotRoot 'tunnel-client.exe'
$tripShotProcesses = @(Get-Process -Name 'tunnel-client' -ErrorAction SilentlyContinue)
if ($tripShotProcesses.Count -ne 1) { throw 'Expected exactly one tunnel-client; investigate before testing.' }
& $tripShotClient health --port 8080 --pid $tripShotProcesses[0].Id --require-control-plane-poll
if ($LASTEXITCODE -ne 0) { throw 'Client is not healthy/ready with a successful poll; cutover is not verified.' }
```

Initial startup/long-poll establishment can take time. If the first readiness probe is negative during startup, wait and recheck within a 60-second observation window; do not launch another client. A persistent failure requires diagnostics/rollback. Check the loopback operator page at `http://127.0.0.1:8080/ui` if needed. Keep raw HTTP logging disabled. Inspect the **existing** ChatGPT TripShot connection, refresh its tool discovery if available, and start a new chat so cached schemas do not hide the two added tools. Do not delete/recreate the connection or edit the hosted tunnel identity.

## Rollback

After **Ctrl+C in Window A**, wait for the new client and stdio child to exit. Use a trusted key-loaded shell. Paste the exact backup path printed during cutover; do not select an arbitrary latest backup. Restoring that file restores the previous command **and the same ID/reference**, without modifying the original Downloads runtime. The guard requires the reviewed original hash.

```powershell
$ErrorActionPreference = 'Stop'
$tripShotRoot = 'C:\Users\samkk\Projects\TripShot_MCP\TripShot_MCP_Starter_v6'
$tripShotClient = Join-Path $tripShotRoot 'tunnel-client.exe'
$tripShotProfiles = Join-Path $env:APPDATA 'tunnel-client'
$tripShotProfile = Join-Path $tripShotProfiles 'tripshot-local.yaml'
$rollbackBackup = Read-Host 'Exact verified backup path printed during cutover'
$expectedOriginalHash = '6CD68B523D0C5FB9DA4119447FBB1AF75F555D9DC39A1B93B992794C99B68B08'
if (-not [Environment]::GetEnvironmentVariable('CONTROL_PLANE_API_KEY','Process')) {
    throw 'Use the existing trusted runtime-key loading procedure in this shell first.'
}
foreach ($name in @('MCP_COMMAND','TUNNEL_CLIENT_CONFIG','TUNNEL_CLIENT_PROFILE',
    'TUNNEL_CLIENT_PROFILE_FILE','TUNNEL_CLIENT_PROFILE_DIR','CONTROL_PLANE_TUNNEL_ID',
    'TRIPSHOT_JSON_PATH','TRIPSHOT_LIVE_JSON_PATH','TRIPSHOT_STOP_NAMES_PATH',
    'TRIPSHOT_DISABLE_SCHEDULE_REFRESH','TRIPSHOT_DISABLE_SERVICE_REFRESH')) {
    if ([Environment]::GetEnvironmentVariable($name,'Process')) {
        throw "Unexpected override $name is set. Review privately before rollback; no value was printed."
    }
}
$resolvedBackup = (Resolve-Path -LiteralPath $rollbackBackup).Path
$expectedBackupParent = [IO.Path]::GetFullPath((Join-Path $tripShotProfiles 'backups'))
if ([IO.Path]::GetDirectoryName($resolvedBackup) -ne $expectedBackupParent -or
    (Get-FileHash -LiteralPath $resolvedBackup -Algorithm SHA256).Hash -ne $expectedOriginalHash) {
    throw 'Not the verified original-profile backup; nothing restored.'
}
$tripShotMutex = [Threading.Mutex]::new($false,'Global\TripShotCompanion.tripshot-local')
$tripShotOwned = $false
try {
    try { $tripShotOwned = $tripShotMutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $tripShotOwned = $true }
    if (-not $tripShotOwned) { throw 'Another guarded operator owns the runtime.' }
    if (@(Get-Process -Name 'tunnel-client' -ErrorAction SilentlyContinue).Count -ne 0) {
        throw 'Stop the current client before restoring or restarting.'
    }
    $pending = Join-Path $tripShotProfiles ('tripshot-local.'+[guid]::NewGuid().ToString('N')+'.pending')
    try {
        Copy-Item -LiteralPath $resolvedBackup -Destination $pending
        [IO.File]::Replace($pending,$tripShotProfile,$null)
    } finally {
        if (Test-Path -LiteralPath $pending) { Remove-Item -LiteralPath $pending }
    }
    Set-Location -LiteralPath $tripShotRoot
    & $tripShotClient doctor --profile tripshot-local --profile-dir $tripShotProfiles --explain
    if ($LASTEXITCODE -ne 0) { throw 'Rollback doctor failed; do not start.' }
    if (@(Get-Process -Name 'tunnel-client' -ErrorAction SilentlyContinue).Count -ne 0) {
        throw 'Another client appeared; do not start a second instance.'
    }
    & $tripShotClient run --profile tripshot-local --profile-dir $tripShotProfiles
} finally {
    if ($tripShotOwned) { $tripShotMutex.ReleaseMutex() }
    $tripShotMutex.Dispose()
}
```

Use Window B health checks after rollback. The older server may expose fewer tools; that is expected rollback behavior, not proof of a new tunnel. Reconcile ChatGPT's cached schema with the restored server. Keep the Downloads runtime and verified backup until the review/rollback window is explicitly closed.

## Post-cutover end-to-end acceptance (not yet performed)

Run through the existing ChatGPT connection. Inspect actual tool results and the connection's supplied tool inventory, not a model-generated claim of tool availability. Exact names/defaults are in [MCP_TOOLS.md](MCP_TOOLS.md). Baseline dates below are October 2026 examples: if execution happens later, use a future operating weekday within 30 days and the published 2026–27 calendar. Historical disruption testing uses the journey tool, since the future departure wrapper rejects past dates.

| Test | Invocation / procedure | Expected result and failure distinction |
| --- | --- | --- |
| 1. Discovery | Existing connection exposes all 18 names, including `get_service_updates` and `refresh_service_updates`. Compare with the documented inventory. | Exactly 18 current names/signatures supplied. Missing names with healthy local 18-tool discovery suggest stale ChatGPT schema; refresh discovery/new chat before diagnosing the server. A failed MCP handshake/poll is transport failure. |
| 2. Scheduled departure | `get_shuttles_at_time(stop_query="Emerson/Maple (EB)", when_local="2026-10-19T08:00")` | Four published rows at readiness check, with schedule-only data and source/alert metadata. Unknown-year warnings can make them provisional. An empty list on a weekend/holiday/wrong stop/time is not transport failure or proof of no service; check window, calendar, matched stops, and explicit `error`/MCP state. |
| 3. Current TripShot | During Intercampus weekday operating hours or Loop evening service, call `get_next_shuttles(stop_query="Emerson", limit=8)`. | Route/day `coverage` succeeds and timestamps are current; actual arrival count may be zero. Distinguish request/auth/parser errors (`coverage.ok=false`, `error`, MCP error) from valid empty responses. Reported ETA is never GPS verification. Defer if service is not operating; do not use the synthetic vehicle tool as a substitute. |
| 4. Official notices | `refresh_service_updates(force=True)`, then `get_service_updates(refresh=False)`. | Official source URL, current check/last-success timestamp, revision, notices and uncertainty warnings. `parse_review_required` with no fetch error is a successful fetch requiring interpretation, not a refresh failure. `normal_service_confirmed=false` always. A genuine outage returns stale/unavailable health and retained last-good evidence. |
| 5. Affected journey | `plan_scheduled_shuttle_trip(origin_stop="Central L (EB)", destination_stop="Ward Building", when_local="2026-10-16T16:20")`. | With no year review, preserve provisional options and explain uncertain applicability. Only after a separately approved 2026 review, expect affected options in `excluded_options`, original times retained and `total_matching_scheduled_rides` unchanged. Historical source evidence must still be retained/available; if gone, use a current authoritative disruption or the isolated offline demo, and mark that branch not verified end to end. Never turn the demo into a live notice or silently approve a year. |
| 6. Unaffected journey | `plan_scheduled_shuttle_trip(origin_stop="Library / Norris", destination_stop="Emerson/Maple (WB)", when_local="2026-10-19T19:00")` | Eight Loop options at readiness check, `schedule_only` under the current notices. An empty result requires calendar/time/stop-order checks; Intercampus-only warnings should not cancel Loop. No result guarantees a vehicle is operating. |
| 7. Ambiguity/failure | Query the current missing-year Intercampus notice and a related journey without adding review metadata. If a real source failure occurs, inspect refresh result/status instead. | Uncertain evidence stays visible, related recommendations are provisional, and absence/failure never asserts normal service. Do not disrupt the network or change operational source URLs to induce a fault. Injected timeout/403/cache-failure behavior is already covered offline; if the live ambiguity case disappears, report the live failure branch deferred rather than fabricate an outage. |

Completion requires healthy/ready polling, actual ChatGPT discovery and representative calls, and recording observed outcomes/deferred tests in `PROJECT_STATUS.md`. Local tests/doctor alone do not establish end-to-end completion. If readiness fails, stop the sole new client and follow rollback; do not start a parallel old instance.
