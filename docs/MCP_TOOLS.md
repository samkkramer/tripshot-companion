# MCP tool baseline

Verified locally on 2026-10-17 with MCP Python SDK 2.3.0, stdio protocol 2026-07-28. Definitions in `server.py` are authoritative. All tools return dictionaries; schemas come from the SDK and Python annotations. No migration change to tool names, signatures, defaults, or output contracts.

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

Limits are positive integers, capped at 20 with notice where exposed. `when_local` uses Chicago time; supply `YYYY-MM-DDTHH:MM`. Future departure wrapper rejects past dates and dates beyond 30 days, with before window 0–120 minutes and after window 1–180 minutes. Journey planners use a four-hour boarding horizon and do not share the same date-range guard (see audit).

Snapshot ride tools default to the synthetic ride unless explicitly configured. Saved route-group tools require a separate local response and catalog. Schedule tools never establish live operation. Most schedule entry points can perform an on-demand timetable refresh unless `TRIPSHOT_DISABLE_SCHEDULE_REFRESH=1`; this variable does not disable explicit refresh calls. The future departure wrapper currently reads live-source configuration even though it does not fetch TripShot.

Errors are not yet uniform: guarded tools return `error` dictionaries, while some saved-data/cache/invalid-journey failures can become MCP invocation errors. Clients must inspect both MCP error state and returned dictionaries, plus coverage and freshness warnings.
