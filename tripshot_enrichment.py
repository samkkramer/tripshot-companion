"""Interpret TripShot stop and ride records conservatively.

No network access. The API's liveRides/lastEtaUpdate flags do NOT, by
 themselves, establish GPS-based predictions or realized arrivals.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from difflib import get_close_matches
from typing import Any

from stops_catalog import LOCAL_CATALOG
from live_groups import _ride_data, _iter_directions, _stop_status, _stop_id
from tripshot_provider import CHICAGO

# Observed in the user's Northwestern Loop data, verified against the
# published stop orders. IDs are advisory, NOT a universal permanent ID.
KNOWN_NAV = {
    '06d49c0d-a65e-4a46-96cd-0e6fd62ec7fe': 'Counterclockwise',
    'aeee6def-98e5-4c4e-bbbb-9f6ca51c8548': 'Clockwise',
}
CW_MARKERS = {'619 clark', 'emerson/maple (wb)', 'ridge/garnett (nb)',
              'noyes l (eb)', 'sheridan/haven - tech (sb)'}
CCW_MARKERS = {'weber arch', 'emerson/maple (eb)', 'ridge/garnett (sb)',
               'noyes l (wb)', 'sheridan/haven - tech (nb)'}


def _catalog() -> list[dict]:
    if not LOCAL_CATALOG.is_file():
        raise FileNotFoundError('Stop catalog missing; copy data\\stops_catalog.local.json')
    raw = json.loads(LOCAL_CATALOG.read_text(encoding='utf-8-sig'))
    return raw if isinstance(raw, list) else []


def resolve_query(query: str) -> dict:
    """Find literal matches; accept a reversed intersection as a *suggestion*.

    Never silently map ambiguous or absent stops to an unrelated stop.
    """
    stops = _catalog()
    q = query.strip().casefold()
    if not q:
        return {'error':'invalid_stop_query','message':'Supply a stop name or ID.'}
    matches = [s for s in stops if q in str(s.get('name','')).casefold() or q in str(s.get('stop_id','')).casefold()]
    if matches:
        return {'resolved': query.strip(), 'matched_stops': matches, 'alias_used': False}
    if '/' in q:
        parts = q.split('/', 1)
        reversed_query = '/'.join([parts[1].strip(), parts[0].strip()])
        swapped = [s for s in stops if reversed_query in str(s.get('name','')).casefold()]
        if swapped:
            return {'error':'stop_name_order','message':f'No stop named {query!r}. Did you mean a stop under {reversed_query!r}?',
                    'suggestions': [s.get('name') for s in swapped]}
    names = [str(s.get('name')) for s in stops if s.get('name')]
    suggestions = get_close_matches(query, names, n=5, cutoff=0.35)
    return {'error':'stop_not_found', 'message':f'No stops match {query!r} in the imported stop catalog.',
            'suggestions': suggestions}


def ride_metadata(payload: dict) -> dict[str, dict]:
    """Inspect live/non-live ride objects, keyed by rideId."""
    node = payload.get('InternalRouteGroupLiveData', payload)
    try:
        names = {str(s.get('stop_id')): str(s.get('name', '')) for s in _catalog()}
    except FileNotFoundError:
        names = {}  # parser fixtures and empty responses need no stop catalog
    found: dict[str, dict] = {}
    for _, group in _iter_directions(node):
        for collection in ('liveRides', 'nonliveRides'):
            for entry in group.get(collection, []) if isinstance(group.get(collection), list) else []:
                outer, ride = _ride_data(entry)
                rid = ride.get('rideId') or outer.get('rideId')
                if not isinstance(rid, str):
                    continue
                stop_names = []
                for rec in ride.get('stopStatus', []) if isinstance(ride.get('stopStatus'), list) else []:
                    if isinstance(rec, dict):
                        _, details = _stop_status(rec)
                        sid = _stop_id(rec, details)
                        if sid and sid in names:
                            stop_names.append(names[sid])
                found[rid] = {'navigation_id': ride.get('effectiveNavigationId') or ride.get('navigationId'),
                              'ordered_stop_names': stop_names, 'collection': collection,
                              'late_by_sec': ride.get('lateBySec'),
                              'gps_reported_at': (ride.get('vehicleStatus') or {}).get('when') if isinstance(ride.get('vehicleStatus'),dict) else None}
    return found


def direction_for(meta: dict) -> dict:
    names = {s.casefold().strip() for s in meta.get('ordered_stop_names', []) if isinstance(s, str)}
    cw, ccw = len(names & CW_MARKERS), len(names & CCW_MARKERS)
    if cw >= 2 and ccw == 0:
        return {'label':'Clockwise', 'basis':'ordered_stop_sequence', 'confidence':'high'}
    if ccw >= 2 and cw == 0:
        return {'label':'Counterclockwise', 'basis':'ordered_stop_sequence', 'confidence':'high'}
    nav = meta.get('navigation_id')
    if nav in KNOWN_NAV and not (cw and ccw):
        return {'label':KNOWN_NAV[nav], 'basis':'previously_observed_navigation_id', 'confidence':'provisional'}
    return {'label':'Unknown', 'basis':'insufficient_or_conflicting_route_metadata', 'confidence':'unknown'}


def _timestamp(s: str | None):
    if not isinstance(s, str) or not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace('Z','+00:00'))
        return dt if dt.tzinfo else None
    except ValueError:
        return None


def label_arrival(row: dict, fetched_at: str | None = None, *, future: bool = False) -> dict:
    """Annotate result without misrepresenting polling as GPS freshness."""
    rec = dict(row)
    is_live = rec.get('record_type') == 'ride_in_live_group'
    predicted = _timestamp(rec.get('reported_expected_arrival_local'))
    scheduled = _timestamp(rec.get('scheduled_departure_local'))
    updated = _timestamp(rec.get('last_eta_update_local'))
    fetched = _timestamp(fetched_at or rec.get('data_fetched_at'))
    age = (fetched - updated).total_seconds() if updated and fetched else None
    delta = (predicted - scheduled).total_seconds() if predicted and scheduled else None
    rec['eta_timestamp_age_seconds'] = round(age) if age is not None else None
    rec['offset_from_scheduled_seconds'] = round(delta) if delta is not None else None
    rec['gps_verified'] = False
    rec['predictions_observed_changing'] = False  # requires two snapshots of SAME ride + stop
    if future:
        status = 'future_schedule_unconfirmed'
    elif not is_live:
        status = 'scheduled_nonlive'
    elif age is None or age < -30 or age > 120:
        status = 'active_ride_eta_stale_or_unknown'
    elif delta is None or abs(delta) < 1:
        status = 'active_ride_schedule_matched'
    else:
        status = 'active_ride_adjusted_eta_unverified'
    rec['eta_confidence'] = status
    rec['eta_explanation'] = {
        'future_schedule_unconfirmed':'Future departure information; not a real-time prediction or proof of service.',
        'scheduled_nonlive':'Non-live ride; treat as a schedule/plan. A fresh retrieval timestamp is NOT a fresh prediction.',
        'active_ride_eta_stale_or_unknown':'Active ride listing; ETA-update timestamp unavailable or older than two minutes.',
        'active_ride_schedule_matched':'Active ride with a recent ETA timestamp, but expected arrival equals schedule.',
        'active_ride_adjusted_eta_unverified':'Active ride with a recent ETA timestamp and a time different from schedule; GPS basis unverified.',
    }[status]
    return rec


def decorate_rows(rows: list[dict], payload: dict, label: str, fetched_at: str | None, *, future: bool = False) -> list[dict]:
    meta = ride_metadata(payload)
    result = []
    for row in rows:
        rec = label_arrival(row, fetched_at, future=future)
        if label == 'Loop':
            m = meta.get(str(row.get('ride_id')), {})
            rec['loop_direction'] = direction_for(m)
            rec['navigation_id'] = m.get('navigation_id')
        result.append(rec)
    return result
