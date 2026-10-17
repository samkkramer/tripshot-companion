"""Read-only, offline analysis of an exported TripShot ride JSON response.

No HTTP requests, authentication, browser automation, or write operations.
The sample fixture is synthetic. We do not assume undocumented API access.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any

CHICAGO = ZoneInfo("America/Chicago")
BASE = Path(__file__).resolve().parent
DEFAULT_DATA = BASE / "data" / "example_ride.json"
DEFAULT_NAMES = BASE / "data" / "stop_names.example.json"
LOCAL_NAMES = BASE / "data" / "stop_names.local.json"


def _date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except ValueError:
        return None


def _local(value: Any) -> str | None:
    dt = _date(value)
    return dt.astimezone(CHICAGO).isoformat(timespec="seconds") if dt else None


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Snapshot missing: {path}")
    if path.stat().st_size > 5_000_000:
        raise ValueError("Snapshot exceeds the 5 MB safety limit")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    return data


def _bundle(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Observed shape: {ride: {ride: {...}, route: {...}, vehicleStatus: {...}}}.

    Also handles flat ride objects. Only response fields seen in screenshots are used.
    """
    wrapper = raw.get("ride") if isinstance(raw.get("ride"), dict) else raw
    ride = wrapper.get("ride") if isinstance(wrapper.get("ride"), dict) else wrapper
    return wrapper, ride


def _names() -> dict[str, str]:
    file = Path(os.environ.get("TRIPSHOT_STOP_NAMES_PATH", str(LOCAL_NAMES if LOCAL_NAMES.is_file() else DEFAULT_NAMES)))
    if not file.is_file():
        return {}
    data = _load(file)
    return {str(k): str(v) for k, v in data.items()}


def _source() -> tuple[dict[str, Any], dict[str, Any], Path]:
    file = Path(os.environ.get("TRIPSHOT_JSON_PATH", str(DEFAULT_DATA))).expanduser().resolve()
    raw = _load(file)
    wrapper, ride = _bundle(raw)
    return wrapper, ride, file


def _status(stop: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    # One observed state is {"Awaiting": { ... }}. Future observations may differ.
    for state in ("Awaiting", "Arrived", "Departed", "Skipped", "Completed"):
        item = stop.get(state)
        if isinstance(item, dict):
            return state, item
    return "Unknown", {}


def _file_meta(file: Path) -> dict[str, Any]:
    return {
        "source": "MANUAL_LOCAL_JSON_SNAPSHOT",
        "snapshot_file_modified_at_local": datetime.fromtimestamp(file.stat().st_mtime, tz=CHICAGO).isoformat(timespec="seconds"),
        "warning": "This is a saved snapshot, NOT a live TripShot query. Do not call these current arrivals.",
    }


def get_ride_summary() -> dict[str, Any]:
    """Describe the saved ride snapshot; no user, passenger, or authentication data."""
    wrapper, ride, file = _source()
    route = wrapper.get("route") if isinstance(wrapper.get("route"), dict) else {}
    return {
        **_file_meta(file),
        "route_name": ride.get("routeName") or route.get("name"),
        "scheduled_start_local": _local(ride.get("scheduledStart")),
        "scheduled_end_local": _local(ride.get("scheduledEnd")),
        "reported_late_by_seconds": ride.get("lateBySec"),
        "eta_available_flag": wrapper.get("etaAvailable", ride.get("etaAvailable")),
        "live_data_available_flag": ride.get("liveDataAvailable"),
        "last_eta_update_local": _local(ride.get("lastEtaUpdate")),
        "stop_count_in_snapshot": len(ride.get("stopStatus", [])) if isinstance(ride.get("stopStatus"), list) else 0,
    }


def list_ride_stops() -> dict[str, Any]:
    """Return stop IDs and reported arrival values for ONE saved ride only."""
    wrapper, ride, file = _source()
    stops = ride.get("stopStatus") if isinstance(ride.get("stopStatus"), list) else []
    names = _names()
    result = []
    for index, item in enumerate(stops):
        if not isinstance(item, dict):
            continue
        state, details = _status(item)
        stop_id = str(details.get("stopId") or details.get("sharedStopId") or item.get("stopId") or item.get("sharedStopId") or "")
        expected = details.get("expectedArrivalTime") or item.get("expectedArrivalTime")
        scheduled_at = details.get("scheduledAt") or item.get("scheduledAt")
        expected_local = _local(expected)
        expected_clock = None
        if expected_local:
            parsed = _date(expected)
            expected_clock = parsed.astimezone(CHICAGO).strftime("%H:%M:%S") if parsed else None
        matches_schedule = expected_clock == scheduled_at if expected_clock and scheduled_at else None
        result.append({
            "index": item.get("viaIdx", index),
            "stop_id": stop_id,
            "stop_name": names.get(stop_id),
            "status": state,
            "rider_status": details.get("riderStatus"),
            "scheduled_local_clock": scheduled_at,
            "scheduled_departure_local": _local(details.get("scheduledDepartureTime") or item.get("scheduledDepartureTime")),
            "reported_expected_arrival_local": expected_local,
            "expected_time_matches_scheduled_clock": matches_schedule,
            "prediction_verified_live": False,  # do not infer GPS-based ETA from a field name
        })
    return {
        **_file_meta(file),
        "route_name": ride.get("routeName"),
        "stops": result,
        "interpretation": "Expected times are values reported in a saved response. Identical scheduled and expected times do not prove a real-time prediction.",
    }


def find_stop(query: str) -> dict[str, Any]:
    """Look up a stop within the saved ride by its ID or configured name."""
    data = list_ride_stops()
    q = query.strip().casefold()
    if not q:
        return {"error": "Provide a non-empty stop name or ID."}
    matches = [s for s in data["stops"] if q in s["stop_id"].casefold() or (s["stop_name"] and q in s["stop_name"].casefold())]
    return {"query": query, "matches": matches, "matches_only_saved_ride": True, "warning": data["warning"]}


def get_vehicle_position() -> dict[str, Any]:
    """Return position reported in the saved response (never claim current location)."""
    wrapper, ride, file = _source()
    status = wrapper.get("vehicleStatus") if isinstance(wrapper.get("vehicleStatus"), dict) else {}
    loc = status.get("location") if isinstance(status.get("location"), dict) else {}
    stamp = _date(status.get("when"))
    seconds_ago = round((datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()) if stamp else None
    return {
        **_file_meta(file),
        "latitude": loc.get("lt"),
        "longitude": loc.get("lg"),
        "bearing_degrees": status.get("bearing"),
        "speed_reported_units_unknown": status.get("speed"),
        "reported_at_local": _local(status.get("when")),
        "seconds_since_report": seconds_ago,
        "stale_over_2_minutes": (seconds_ago > 120 or seconds_ago < -120) if seconds_ago is not None else None,
    }
