"""LOCAL MCP server. Run via MCP Inspector or another stdio-compatible client.

Do NOT deploy publicly as-is. A hosted server needs its own authentication,
authorized data feed, controls, and operational security.
"""
from mcp.server import MCPServer
import tripshot_core as core
from stops_catalog import search_stops as lookup_stops
from live_groups import overview as live_overview, arrivals as live_arrivals
from nearby_stops import find_nearby_stops as geo_nearby_stops
from shuttle_now import combine as combine_arrivals, planned_at_time
from tripshot_provider import get_sources
from published_full import route_stops, plan_trip, served_stops_near, plan_to_coordinates, check_timetable_updates, timetable_status

mcp = MCPServer("TripShot Snapshot Explorer")


@mcp.tool()
def get_ride_summary() -> dict:
    """Summarize one locally saved TripShot ride JSON. Does not access live systems."""
    return core.get_ride_summary()


@mcp.tool()
def list_ride_stops() -> dict:
    """List stop IDs, planned times and reported expected arrivals in one snapshot."""
    return core.list_ride_stops()


@mcp.tool()
def find_stop(query: str) -> dict:
    """Find an ID or known stop name within the saved ride, not all shuttle trips."""
    return core.find_stop(query)


@mcp.tool()
def search_all_stops(query: str) -> dict:
    """Search a manually imported local stop list; no live TripShot calls."""
    return lookup_stops(query)


@mcp.tool()
def get_vehicle_position() -> dict:
    """Report the last SAVED vehicle coordinate, including its timestamp and staleness."""
    return core.get_vehicle_position()


@mcp.tool()
def inspect_saved_route_group() -> dict:
    """Describe routes, active-trip counts, and availability in a SAVED live?day response."""
    return live_overview()


@mcp.tool()
def find_saved_upcoming_arrivals(stop_name: str) -> dict:
    """Find arrivals in a manually exported route-group snapshot, NOT live arrivals."""
    return live_arrivals(stop_name)


def _validated_limit(limit: int, *, default: int) -> tuple[int | None, str | None]:
    """Keep tool invocation errors within MCP responses, not server tracebacks."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        return None, f"Invalid limit {limit!r}: supply an integer from 1 to 20; a good default is {default}."
    if limit > 20:
        return 20, f"Requested {limit} results; capped at 20 (the supported maximum)."
    return limit, None


@mcp.tool()
def get_next_shuttles(stop_query: str, limit: int = 8) -> dict:
    """Fetch currently upcoming shuttle arrivals near a named stop (e.g. Emerson).

    This is a one-time lookup covering roughly the next 4 hours. Use limit=8
    normally, or an integer 1-20. If a caller requests >20, return 20 and
    disclose the cap. TripShot's live-data grouping does NOT establish that
    the ETAs are GPS-validated. "NonDirectional" is not a compass direction.
    Do not use this tool to assert future-morning service availability when
    the requested time is beyond its four-hour lookahead.
    """
    if not isinstance(stop_query, str) or not stop_query.strip() or len(stop_query) > 128:
        return {"error": "invalid_stop_query", "message": "Provide a stop name of 1-128 characters, e.g. Emerson/Maple (WB)."}
    valid_limit, notice = _validated_limit(limit, default=8)
    if valid_limit is None:
        return {"error": "invalid_limit", "message": notice}
    try:
        output = combine_arrivals(stop_query.strip(), get_sources(), limit=valid_limit)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": "lookup_failed", "message": str(exc)}
    if notice:
        output["limit_notice"] = notice
    return output


@mcp.tool()
def get_shuttles_at_time(stop_query: str, when_local: str, before_minutes: int = 30,
                         after_minutes: int = 90, limit: int = 12) -> dict:
    """Find *planned/scheduled* departures near a SPECIFIC future Chicago time.

    when_local MUST be YYYY-MM-DDTHH:MM (America/Chicago), e.g.
    2026-10-20T19:30. Never label results live or GPS-confirmed.
    Uses Northwestern's complete official 2026-27 Loop schedule and
    the complete 2026-27 Intercampus tables for BOTH directions.
    Covers ALL stops in official published route tables, not just Emerson.
    No TripShot HTTP calls needed for future published schedules.
    Returns an inconclusive result, not 'no service', if data is missing.
    For shuttles due within minutes, call get_next_shuttles instead.
    """
    if not isinstance(stop_query, str) or not stop_query.strip() or len(stop_query) > 128:
        return {'error':'invalid_stop_query', 'message':'Provide a stop name of 1-128 characters.'}
    valid_limit, notice = _validated_limit(limit, default=12)
    if valid_limit is None:
        return {'error':'invalid_limit','message':notice}
    try:
        output = planned_at_time(stop_query.strip(), when_local, {},
                                 before_minutes=before_minutes, after_minutes=after_minutes,
                                 limit=valid_limit)
    except (ValueError, TypeError, FileNotFoundError) as exc:
        return {'error':'future_lookup_failed','message':str(exc)}
    if notice:
        output['limit_notice'] = notice
    return output


@mcp.tool()
def get_nearby_stops(latitude: float, longitude: float, limit: int = 5) -> dict:
    """Find nearest imported stops (straight-line distance, NOT walking ETA).

    Supply the user's shared latitude and longitude, not guessed coordinates;
    limit must be a positive integer (max 20). Nearest is not necessarily
    served by the right shuttle or direction.
    """
    valid_limit, notice = _validated_limit(limit, default=5)
    if valid_limit is None:
        return {"error": "invalid_limit", "message": notice}
    try:
        output = geo_nearby_stops(latitude, longitude, valid_limit)
    except (TypeError, ValueError) as exc:
        return {"error": "invalid_coordinates", "message": str(exc)}
    if notice:
        output["limit_notice"] = notice
    return output


@mcp.tool()
def list_published_route_stops() -> dict:
    """List EVERY scheduled stop in Loop CW/CCW and Intercampus both directions.

    Useful for discovering which stops are served, before requesting departure
    times, route directions or stop-to-stop travel estimates.
    """
    return {'routes':route_stops(), 'schedule_type':'OFFICIAL_2026_27_PUBLISHED_APPROXIMATE',
            'note':'No shuttle GPS, live operation, walking directions or accessibility status.'}


@mcp.tool()
def plan_scheduled_shuttle_trip(origin_stop: str, destination_stop: str, when_local: str, limit: int = 8) -> dict:
    """Look up SAME-VEHICLE board/alight times for ANY published stop pair.

    when_local is YYYY-MM-DDTHH:MM America/Chicago. Does not plan transfers
    or walking; planned time is not a promise of travel time.
    """
    val,notice=_validated_limit(limit,default=8)
    if val is None:return {'error':'invalid_limit','message':notice}
    if not (isinstance(origin_stop,str) and isinstance(destination_stop,str) and
            0<len(origin_stop.strip())<=128 and 0<len(destination_stop.strip())<=128):
        return {'error':'invalid_stop_query','message':'Provide two stop names (1-128 chars).'}
    out=plan_trip(origin_stop.strip(),destination_stop.strip(),when_local,limit=val)
    if notice:out['limit_notice']=notice
    return out


@mcp.tool()
def get_scheduled_stops_near(latitude: float, longitude: float, limit: int = 10) -> dict:
    """Nearby imported TripShot stops SERVED by a published shuttle direction.

    Distance is straight-line, NOT walking distance. Requires local stop
    catalog and user-provided GPS coordinates; no geocoding or location tracking.
    """
    val,notice=_validated_limit(limit,default=10)
    if val is None:return {'error':'invalid_limit','message':notice}
    try:out=served_stops_near(latitude,longitude,limit=val)
    except (TypeError,ValueError) as e:return {'error':'invalid_coordinates','message':str(e)}
    if notice:out['limit_notice']=notice
    return out


@mcp.tool()
def plan_scheduled_trip_to_location(origin_stop: str, destination_latitude: float,
                                    destination_longitude: float, when_local: str, limit: int = 8) -> dict:
    """Compare scheduled drop-off stops near destination GPS coordinates.

    The walking-distance proxy is straight-line ONLY; ChatGPT should verify
    pedestrian directions separately and never call it a guaranteed best stop.
    """
    val,notice=_validated_limit(limit,default=8)
    if val is None:return {'error':'invalid_limit','message':notice}
    if not isinstance(origin_stop,str) or not origin_stop.strip():
        return {'error':'invalid_stop_query'}
    try:out=plan_to_coordinates(origin_stop,destination_latitude,destination_longitude,when_local,limit=val)
    except (TypeError,ValueError) as e:return {'error':'invalid_query','message':str(e)}
    if notice:out['limit_notice']=notice
    return out


@mcp.tool()
def refresh_published_timetables(force: bool = False) -> dict:
    """Check Northwestern's four OFFICIAL schedule pages, at most once daily.

    Detect changes in actual timetable cells (not page-layout noise).
    On validated changes, atomically activate the new version and keep the
    previous schedule for rollback. On network/format failure retain the
    old schedule. Force=True bypasses the 24-hour check throttle once.
    Never a realtime prediction or background monitor.
    """
    if not isinstance(force,bool):
        return {'error':'invalid_force','message':'force must be boolean'}
    return check_timetable_updates(force=force)


@mcp.tool()
def get_published_timetable_status() -> dict:
    """Report the active schedule revision, last verification, and any failures.

    Does not make external requests. Use refresh_published_timetables(force=True)
    for an immediate recheck of the official Northwestern timetable pages.
    """
    return timetable_status()


if __name__ == "__main__":
    mcp.run(transport="stdio")
