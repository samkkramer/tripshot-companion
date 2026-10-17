# Service Updates development implementation — 2026-10-17

Implements the owner-approved architecture and refresh policy in `SERVICE_UPDATES_PLAN.md`. This is a local development version for review; production runtime/tunnel and external services are unchanged.

## Modules and stored model

- `service_updates_source.py`: one unauthenticated HTTPS GET to Northwestern's official Service Updates URL, max 2 MB, timeout/deadline, strict decoding/content type, optional HTTP validators and redirect validation before another request. No arbitrary link fetching.
- `service_updates_parser.py`: extracts only the Shuttle Service Updates section, checks complete document/section structure, ignores scripts/styles and parking, and produces versioned notice dictionaries. Supported deterministic wording covers explicit cancellations, named stop families, detours/truncation warnings, special services, retractions and unresolved notices. Unsupported wording remains reviewable.
- `service_updates.py`: notice validation, semantic revisions/checksums, history, applicability, OS file lock, atomic manifest, last-known-good fallback, backoff and response snapshot pinning. Published schedules and live ETA fields remain independent.

Ignored `data/service_updates/current.json` is one atomic manifest containing the active validated notice snapshot and refresh health. Retained manifests under `history/` preserve earlier notice revisions and source evidence. Hash-named history files older than 90 days are pruned on successful refresh. `rollback(revision, root=...)` is a developer API for an explicitly selected validated retained revision; rollback remains stale until reverified. It is not an MCP mutation tool. Lock file is persistent, while its OS lock is released on process exit.

Notice schema v1 preserves official URL/anchor/approved links, relevant text, source evidence hash, local identity, dates as originally expressed, local/UTC effective windows with precision/boundary semantics, routes/directions, named physical stop families, effect certainty, first/last seen, superseded revision, parser version and explicit review context. Publication timestamps remain null when absent. The cache contains relevant public evidence, not full mixed-content captures or user locations/queries. See `MCP_TOOLS.md` for result schemas.

## Policy and failure behavior

On demand only: success TTL 15 minutes; failed checks retry after 5, 10, 20, 40, then 60 minutes. Force bypasses TTL/backoff once, but not locking/validation. Conditional 304 responses refresh health only with compatible validated cached data, parser and reviewed context. Invalid HTML, unsupported empty sections, suspicious mass removal, wrong HTTP/content type, oversized/undecodable data, cache corruption or failed writes cannot become a trustworthy empty notice set.

Failed checks keep the last-known-good snapshot and expose stale/unavailable health, error category, last success and next retry. Missing cache means unknown exceptions. A finite notice can expire while the refresh remains stale. Open-ended or removed notices do not imply restoration. Unexplained disappearance becomes `removed_unconfirmed` and provisional; an explicit matching retraction retires an effect. Ambiguous identity/renaming retains separate records with possible-replacement links. Conflicting restoration notices downgrade exclusion certainty.

Every result includes `normal_service_confirmed=false`, even when the source is fresh and no applicable notices exist. Timetable availability and TripShot predictions do not override an official confirmed closure. No automatic delay arithmetic or temporary route travel time is invented.

## Recommendation behavior and compatibility

All original 16 MCP names, signatures and defaults remain; two read-only source tools are added. Departure `arrivals` retain original scheduled/reported timestamps, ETA labels and counts, with additive alert fields. Confirmed closures mark those records `unavailable` / `not_recommended`.

Scheduled planners evaluate board/alight stop events at their respective times and route-level disruptions across the travel interval. A stop boarded before its closure is not retroactively treated as an unserved pickup merely because the journey continues during the closure. Confirmed affected journeys leave recommended `options` and remain in `scheduled_options`/`excluded_options`; original matching counts are preserved. Uncertain scope/year, unknown directions, stale/absent checks and unresolved truncations leave provisional recommendations. Location planning pins one Service Updates revision for every candidate.

Known physical-stop family mappings are explicit in the parser/evaluator. An unknown or direction-qualified stop variant requires review rather than being silently mapped. Patten Gym's temporary terminus linkage/timetable is unresolved, so the announcement is preserved and affected route recommendations are provisional; explicitly named closed endpoints are still excluded when dates are resolved. Chicago Express and other special-service announcements are visible without generated departure options.

## Explicit year review

The source currently omits effective years in some notices. No current-date, academic-year, weekday or retrieval-time heuristic automatically supplies one. To record a deliberate reviewed interpretation, obtain the notice's `revision` from `get_service_updates`, inspect its evidence, and manually create/update ignored `data/service_updates/reviewed_years.json`:

```json
{
  "<64-character notice evidence revision>": {
    "year": 2026,
    "reviewer": "Your name",
    "reason": "Explain the authoritative context used for this specific notice",
    "reviewed_at": "2026-10-17T12:00:00-05:00"
  }
}
```

Then explicitly refresh. Review is bound to the exact normalized evidence/links; source wording changes require another review. A changed review context causes revalidation even within TTL, without reusing a 304 against incompatible interpretation. Invalid review metadata fails safely. This mechanism supplies only a deliberately reviewed year; it cannot guess an unknown stop, direction, operational effect, end date or replacement travel time. Direct parser API tests can pass an explicit year map, with that provenance recorded as API input. No production year review was created during development.

## October 16 demonstration

Run `.\.venv\Scripts\python.exe examples/service_updates_demo.py`. It uses a synthetic paraphrase of the researched incident, a temporary cache, and an explicitly labeled 2026 demonstration review. It performs no network requests and changes no persistent application cache.

| Interpretation | Original Central L (EB) departure | Impact | Recommended / excluded journeys |
| --- | --- | --- | --- |
| Missing year, no review | 2026-10-16 16:32 Chicago | uncertain | 8 provisional / 0 excluded |
| Explicit 2026 fixture review | Same 16:32 schedule retained | unavailable | 0 recommended / 8 excluded |

The real official-page validation also succeeded, extracting three notices: Intercampus change, Chicago Express fall service, and Wildcard reader information. Missing-year notices remain unresolved by default. Live checks used an isolated temporary cache; no archived raw page or production configuration was staged.

## Verification and limits

`run_regressions.py` runs **105 tests**: 65 original baseline tests, 5 reliability tests, 23 source/model acceptance/policy tests (including SU01–SU21), and 12 domain/transport/integration tests. The real local MCP smoke test discovers 18 tools and invokes the synthetic ride and cached Service Updates. Dependency check is clean; no packages were added.

Automated scenarios cover explicit reviewed years, missing/mismatched dates, temporal boundaries, route scope, unresolved terminus, overnight/DST, special routes, revisions, withdrawal/removal, identity, semantic changes, failures/304/empty states, open-ended notices, TripShot conflicts, pickup/drop-off and detour impacts, cross-process lock/interrupted writes/rollback, untrusted content, signatures/defaults and additive fields. Additional checks cover TTL/backoff/force, malformed cache, HTTP/size/charset failures, exact family boundaries, negated cancellation, explicit local reviews, and one revision across location comparisons.

Limitations for review: deterministic English patterns deliberately leave unsupported wording unresolved; stop-family mappings are finite; direction-qualified variants and temporary termini need review; effective end wording can be ambiguous; no special-route timetable, transfer/walking-network or vehicle-operation verification exists. Official HTML changes may require parser maintenance. History is local with finite retention; no background availability is provided. Old saved snapshots are not rewritten with present-day notices. Production/tunnel deployment and end-to-end ChatGPT revalidation remain separate, unperformed work.
