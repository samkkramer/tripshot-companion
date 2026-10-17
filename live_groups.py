"""Explore manually exported TripShot live route-group JSON, without network calls.

Observed structure in browser screenshots; fields may vary by TripShot version.
Don't label saved/polled results as live ETA without verification of source timestamps.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any

from stops_catalog import LOCAL_CATALOG

HERE = Path(__file__).resolve().parent
DEFAULT_LIVE = HERE / "data" / "live_response.json"
CHICAGO = ZoneInfo("America/Chicago")


def load_live(path: str | Path | None = None) -> tuple[dict[str, Any], Path]:
    file = Path(path or os.getenv("TRIPSHOT_LIVE_JSON_PATH", str(DEFAULT_LIVE))).expanduser().resolve()
    if not file.exists():
        raise FileNotFoundError(f"No local JSON file at {file}. Save the 'live?day=' Response body here first.")
    if file.stat().st_size > 15_000_000:
        raise ValueError("File is larger than 15 MB; refusing to parse")
    raw = json.loads(file.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError("Expected a JSON object for live route-group response")
    node = raw.get("InternalRouteGroupLiveData")
    if not isinstance(node, dict):
        node = raw
    if not isinstance(node.get("exactLiveData"), list) and not isinstance(node.get("inexactLiveData"), list):
        raise ValueError("No exactLiveData/inexactLiveData found; check the selected Response body")
    return node, file


def _read_stops() -> list[dict[str, Any]]:
    if not LOCAL_CATALOG.exists():
        raise FileNotFoundError("Import stops first: python import_stops.py data\\stops_response.json")
    stops = json.loads(LOCAL_CATALOG.read_text(encoding="utf-8"))
    return stops if isinstance(stops, list) else []


def _date(s: Any) -> datetime | None:
    if not isinstance(s, str) or not s:
        return None
    try:
        parsed = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except ValueError:
        return None


def _local_iso(s: Any) -> str | None:
    dt = _date(s)
    return dt.astimezone(CHICAGO).isoformat(timespec="seconds") if dt else None


def _iter_directions(node: dict[str, Any]):
    for section_name in ("exactLiveData", "inexactLiveData"):
        sections = node.get(section_name)
        if isinstance(sections, list):
            for direction in sections:
                if isinstance(direction, dict):
                    yield section_name, direction


def _ride_data(item: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Support ride snapshots shaped as {ride: {ride: {...}}} or {ride: {...}}."""
    if not isinstance(item, dict):
        return {}, {}
    outer = item.get("ride") if isinstance(item.get("ride"), dict) else item
    inner = outer.get("ride") if isinstance(outer.get("ride"), dict) else outer
    return outer, inner


def _stop_status(item: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Unwrap TripShot's tagged stop states.

    Real responses contain {"Skipped": {"stopId": ...}} or
    {"Awaiting": {"stopId": ..., "expectedArrivalTime": ...}}.
    Older/example snapshots may put stopId on the outside instead.
    """
    for state in ("Awaiting", "Arriving", "Arrived", "Departed", "Skipped", "Completed"):
        if state in item:
            value = item[state]
            return state, value if isinstance(value, dict) else {}
    return "Unknown", item


def _stop_id(item: dict[str, Any], details: dict[str, Any]) -> str | None:
    """Resolve stopId from inside tagged state; support older flat fixtures."""
    for source in (details, item):
        candidate = source.get("stopId") or source.get("sharedStopId")
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def overview(path: str | Path | None = None) -> dict[str, Any]:
    node, file = load_live(path)
    records = []
    for section, group in _iter_directions(node):
        record: dict[str, Any] = {"section": section, "direction": group.get("direction")}
        for k in ("liveRides", "liveTrips", "liveTimetable", "nonliveRides"):
            record[k + "_count"] = len(group.get(k, [])) if isinstance(group.get(k), list) else None
        if isinstance(group.get("liveRides"), list) and group["liveRides"]:
            _, example = _ride_data(group["liveRides"][0])
            record["first_live_ride_fields"] = sorted(example.keys())
            record["first_live_ride_has_stopStatus"] = isinstance(example.get("stopStatus"), list)
        records.append(record)
    return {"shared_route_id": node.get("sharedRouteId"), "snapshot_file": str(file),
            "source": "SAVED_BROWSER_RESPONSE_NOT_REALTIME_QUERY", "directions": records}


def arrivals(query: str, path: str | Path | None = None, include_past: bool = False,
             reference_time_iso: str | None = None) -> dict[str, Any]:
    node, file = load_live(path)
    q = query.strip().casefold()
    if not q:
        return {"error": "Enter a stop name or ID"}
    stops = _read_stops()
    matched_stops = [s for s in stops if q in str(s.get("name", "")).casefold() or q in str(s.get("stop_id", "")).casefold()]
    ids = {s["stop_id"] for s in matched_stops}
    if not ids:
        return {"query": query, "matches": [], "arrivals": [], "warning": "No stop matches in imported catalog"}
    now = _date(reference_time_iso) if reference_time_iso else datetime.fromtimestamp(file.stat().st_mtime, timezone.utc)
    assert now is not None
    results = []
    checked = 0
    with_stops = 0
    matching_states: dict[str, int] = {}
    skipped_past_or_unknown: dict[str, int] = {"non_upcoming_state": 0, "past": 0, "missing_time": 0}
    for section, group in _iter_directions(node):
        for array_name in ("liveRides", "nonliveRides"):
            entries = group.get(array_name, [])
            if not isinstance(entries, list):
                continue
            for entry in entries:
                checked += 1
                outer, ride = _ride_data(entry)
                statuses = ride.get("stopStatus")
                if not isinstance(statuses, list):
                    continue
                with_stops += 1
                for entry_stop in statuses:
                    if not isinstance(entry_stop, dict):
                        continue
                    state, details = _stop_status(entry_stop)
                    sid = _stop_id(entry_stop, details)
                    if sid not in ids:
                        continue
                    matching_states[state] = matching_states.get(state, 0) + 1
                    # A skipped/departed stop is NOT an upcoming pickup.
                    if not include_past and state not in ("Awaiting", "Arriving"):
                        skipped_past_or_unknown["non_upcoming_state"] += 1
                        continue
                    expected_raw = details.get("expectedArrivalTime") or entry_stop.get("expectedArrivalTime")
                    scheduled_raw = details.get("scheduledDepartureTime") or entry_stop.get("scheduledDepartureTime")
                    expected_date = _date(expected_raw)
                    scheduled_date = _date(scheduled_raw)
                    sort_date = expected_date or scheduled_date
                    if not include_past and sort_date is None:
                        skipped_past_or_unknown["missing_time"] += 1
                        continue
                    if not include_past and sort_date < now:
                        skipped_past_or_unknown["past"] += 1
                        continue
                    rec = {
                        "stop_name": next((s["name"] for s in matched_stops if s["stop_id"] == sid), None),
                        "stop_id": sid,
                        "direction": group.get("direction"),
                        "ride_id": ride.get("rideId") or outer.get("rideId"),
                        "route_name": ride.get("routeName") or node.get("sharedRouteId"),
                        "record_type": "ride_in_live_group" if array_name == "liveRides" else "scheduled_or_nonlive_ride",
                        "status": state,
                        "rider_status": details.get("riderStatus"),
                        "reported_expected_arrival_local": _local_iso(expected_raw),
                        "scheduled_local_clock": details.get("scheduledAt") or entry_stop.get("scheduledAt"),
                        "scheduled_departure_local": _local_iso(scheduled_raw),
                        "last_eta_update_local": _local_iso(ride.get("lastEtaUpdate") or outer.get("lastEtaUpdate")),
                        "is_verified_gps_prediction": False,
                    }
                    rec["_order"] = sort_date.timestamp() if sort_date else float("inf")
                    results.append(rec)
    results.sort(key=lambda x: x["_order"])
    distinct = []
    seen = set()
    for item in results:
        item.pop("_order")
        key = (item["stop_id"], item["direction"], item["ride_id"], item["reported_expected_arrival_local"], item["scheduled_departure_local"])
        if key not in seen:
            distinct.append(item)
            seen.add(key)
    return {
        "query": query, "matching_stops": matched_stops,
        "reference_time_local": now.astimezone(CHICAGO).isoformat(timespec="seconds"),
        "source": "MANUALLY_SAVED_TRIPSHOT_JSON_NOT_LIVE", "live_group_route_id": node.get("sharedRouteId"),
        "rides_examined": checked, "rides_with_stop_status": with_stops,
        "matching_stop_states": matching_states,
        "filtered": skipped_past_or_unknown,
        "arrivals": distinct,
        "warning": "This is a manually saved snapshot, NOT live arrivals. Expected times may simply equal scheduled times. The file modification time is a proxy for snapshot time, not an API timestamp."
    }
