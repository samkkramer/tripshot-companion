"""Offline stop-catalog utilities for a manually saved TripShot *response body*.

Does not fetch any remote data or read browser credentials.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
LOCAL_CATALOG = BASE / "data" / "stops_catalog.local.json"
LOCAL_NAMES = BASE / "data" / "stop_names.local.json"


def parse_stops(payload: Any) -> list[dict]:
    # Observed response: top-level JSON list containing stop objects.
    if isinstance(payload, dict):
        payload = payload.get("stops", payload.get("data", []))
    if not isinstance(payload, list):
        raise ValueError("Expected an array of stop records")
    results = []
    for rec in payload:
        if not isinstance(rec, dict):
            continue
        sid, name = rec.get("stopId"), rec.get("name")
        if not isinstance(sid, str) or not isinstance(name, str) or not sid or not name:
            continue
        loc = rec.get("location") if isinstance(rec.get("location"), dict) else {}
        lat, lon = loc.get("lt"), loc.get("lg")
        if not isinstance(lat, (int, float)) or not -90 <= lat <= 90:
            lat = None
        if not isinstance(lon, (int, float)) or not -180 <= lon <= 180:
            lon = None
        results.append({"stop_id": sid, "name": name, "latitude": lat, "longitude": lon,
                        "description": rec.get("description") if isinstance(rec.get("description"), str) else None})
    return results


def import_stop_response(file: str | Path) -> dict:
    file = Path(file)
    if file.stat().st_size > 10_000_000:
        raise ValueError("Response exceeds 10 MB")
    raw = json.loads(file.read_text(encoding="utf-8-sig"))
    stops = parse_stops(raw)
    if not stops:
        raise ValueError("No recognized stop records. Check that you saved the Response body for the 'stop?' request.")
    LOCAL_CATALOG.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_CATALOG.write_text(json.dumps(stops, indent=2, ensure_ascii=False), encoding="utf-8")
    LOCAL_NAMES.write_text(json.dumps({s["stop_id"]: s["name"] for s in stops}, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"count": len(stops), "catalog_file": str(LOCAL_CATALOG), "examples": stops[:2]}


def search_stops(query: str) -> dict:
    if not LOCAL_CATALOG.is_file():
        return {"error": "No stop catalog imported yet. Run: python import_stops.py data\\stops_response.json"}
    raw = json.loads(LOCAL_CATALOG.read_text(encoding="utf-8"))
    q = query.strip().casefold()
    if not q:
        return {"error": "Provide a stop name or ID"}
    matches = [s for s in raw if q in s["name"].casefold() or q in s["stop_id"].casefold()]
    return {"matches": matches[:30], "total_matches": len(matches), "source": "MANUAL_LOCAL_STOP_SNAPSHOT"}
