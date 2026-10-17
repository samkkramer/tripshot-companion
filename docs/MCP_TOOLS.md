# MCP tool baseline

Verified locally on 2026-10-17 with MCP Python SDK 2.3.0, stdio protocol 2026-07-28. There are now **18 tools**, including the unchanged 16 baseline signatures/defaults. Definitions in `server.py` are authoritative. All tools return dictionaries; schemas come from SDK/Python annotations. Service fields are additive; confirmed disruptions intentionally filter journey recommendations while preserving their original schedule evidence.

| Tool signature (arguments) | Main result / provenance | External reads |
| --- | --- | --- |
| `get_ride_summary()` | Ride summary, snapshot source/time, stop count | None |
| `list_ride_stops()` | Saved stops and scheduled/reported times | None |
| `find_stop(query: str)` | Matches within saved ride | None |
| `search_all_stops(query: str)` | Imported catalog matches, total, snapshot source | None |
| `get_vehicle_position()` | Saved coordinates, timestamp, staleness | None |
| `inspect_saved_route_group()` | Saved group/direction structure and counts | None |
| `find_saved_upcoming_arrivals(stop_name: str)` | Snapshot arrivals, reference time, states and filters | None |
| `get_next_shuttles(stop_query: str, limit: int = 8)` | Arrivals, per-route/day coverage, query/fetch times, confidence | TripShot, once per route/day |
| `get_shuttles_at_time(stop_query: str, when_local: str, before_minutes: int = 30, after_minutes: int = 90, limit: int = 12)` | Scheduled departures/window, revision, warnings | Official schedules when due |
| `get_nearby_stops(latitude: float, longitude: float, limit: int = 5)` | Catalog stops, straight-line meters | None |
| `list_published_route_stops()` | Four direction tables, source URLs, schedule type | Official schedules when due |
| `plan_scheduled_shuttle_trip(origin_stop: str, destination_stop: str, when_local: str, limit: int = 8)` | Same-run board/alight options, duration, revision | Official schedules when due |
| `get_scheduled_stops_near(latitude: float, longitude: float, limit: int = 10)` | Nearby catalog stops matched to published routes | Official schedules when due |
| `plan_scheduled_trip_to_location(origin_stop: str, destination_latitude: float, destination_longitude: float, when_local: str, limit: int = 8)` | Same-run options ranked by rough transit + straight-line walk proxy | Official schedules when due |
| `refresh_published_timetables(force: bool = False)` | Refresh status, revision, semantic changes/error | Four fixed official schedule pages when due/forced |
| `get_published_timetable_status()` | Cached status/revision/errors and exception warning | None |
| `get_service_updates(route: str = "", when_local: str = "", refresh: bool = True)` | Official notices, special services, health, revision, provenance; optional route/time filtering | Official Service Updates when due and refresh enabled |
| `refresh_service_updates(force: bool = False)` | Refresh outcome, last-good notices, health, next retry and revision | One official announcement page when due/forced |

Limits are positive integers, capped at 20 with notice where exposed. `when_local` uses Chicago time; supply `YYYY-MM-DDTHH:MM`. Future departure wrapper rejects past dates and dates beyond 30 days, with before window 0–120 minutes and after window 1–180 minutes. Journey planners use a four-hour boarding horizon and do not share the same date-range guard (see audit).

Snapshot ride tools default to the synthetic ride unless explicitly configured. Saved route-group tools require a separate local response and catalog. Schedule tools never establish live operation. Most schedule entry points can perform on-demand timetable refresh unless `TRIPSHOT_DISABLE_SCHEDULE_REFRESH=1`; this does not disable explicit timetable refresh. Future scheduled queries no longer require live-source configuration.

Errors are not yet uniform: guarded tools return `error` dictionaries, while some saved-data failures can become MCP invocation errors. Location journey invalid dates now propagate structured errors, and malformed timetable caches fall back safely. Clients must inspect both MCP error state and returned dictionaries, plus coverage and freshness warnings.

## Service Updates input/output schemas

`get_service_updates` takes three optional properties: `route` (string, default empty, max 128 chars), `when_local` (string, default empty, max 64 chars), and `refresh` (boolean, default true). Empty route/time returns all notices. Route matching uses the exact parsed route label, e.g. `Intercampus`, `Loop`, or `Chicago Express`; notices with unknown route remain visible. A timestamp must be an unambiguous Chicago ISO datetime or carry an explicit UTC offset. Unknown effective dates cannot be filtered away as confidently irrelevant. Invalid input returns `error=invalid_query`, `invalid_refresh`, or `invalid_date_time`.

`refresh_service_updates` takes optional boolean `force` (default false); invalid type returns `error=invalid_force`. This is read-only to Northwestern/TripShot; it writes the development cache only. Force bypasses TTL/backoff once, never the process lock or source validation. `refresh_status` is `updated`, `unchanged`, `not_due`, `in_progress`, or `error`.

Both tools expose the following dictionary fields:

| Field | Type / meaning |
| --- | --- |
| `service_updates_status` | `fresh`, `parse_review_required`, `stale`, `unavailable`, or `not_checked` |
| `service_updates_revision` | Semantic SHA-256 revision string or null; independent of timetable revision |
| `service_updates_checked_at`, `service_updates_last_success_at` | Aware ISO timestamp or null; attempted check versus successful verification |
| `service_updates_age_seconds` | Seconds since last success, or null |
| `service_updates_error`, `service_updates_next_retry_at` | Sanitized error category / retry timestamp, or null |
| `service_updates_source_url`, `service_updates_warning` | Official source and limitation text |
| `normal_service_confirmed` | Always false: absence of a notice is not operational verification |
| `notices` | Array of versioned notice records (query tool filters this) |
| `notice_count`, `special_service_notices` | Query tool: filtered count and special-service subset |

Notice schema v1 includes `id`, evidence `revision`, `heading`, bounded relevant `evidence`, `source_url`, `source_anchor`, approved `links`, `routes`, `directions`, `effects`, `windows`, original date phrases, date basis, explicit review context, warnings, lifecycle, first/last seen timestamps, superseded revision and parser version. Publication/update dates remain null when the source omits them. Window records preserve local/UTC endpoints, precision and ending-boundary ambiguity. Effects distinguish canceled service, unserved stop families, truncation, detour, special service, informational and unresolved notices. Unrecognized/uncertain language never silently becomes a hard cancellation.

Current/future departure and scheduled journey results add the same `service_updates_*` health fields, `normal_service_confirmed=false`, and `service_notices`. Each departure/option adds `service_alerts`, `service_impact` (`unavailable`, `uncertain`, `no_applicable_notice_found`) and `recommendation_status`. Departure rows remain in `arrivals`, even if `not_recommended`; schedule/ETA fields and `total_matched` keep their meaning. Journeys exclude confirmed affected options from `options`, retain original annotated options in `scheduled_options` / `excluded_options`, and add recommended/excluded counts. `total_matching_scheduled_rides` and location `total_options` still count original matching scheduled choices. Uncertain journeys remain `provisional`; unaffected entries are `schedule_only`, never guaranteed operational service.

On-demand Service Updates TTL is 15 minutes, with error retry at 5, 10, 20, 40, then 60 minutes. `TRIPSHOT_DISABLE_SERVICE_REFRESH=1` disables automatic checks for offline work; explicit `refresh_service_updates` still checks. `get_service_updates(refresh=False)` reads cache only. Timetable and Service Updates flags/caches are independent. See [implementation and review workflow](SERVICE_UPDATES_IMPLEMENTATION.md).
