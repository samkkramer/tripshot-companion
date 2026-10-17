r"""Local, read-only diagnostics for TripShot MCP Starter v3 saved JSON.

Place this file beside live_groups.py inside your existing v3 folder and run:
    python tripshot_diagnose_live.py data\live_response.json Emerson

No network access. Does not inspect browser storage, cookies or request headers.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json
import sys

import live_groups


def parse_date(x):
    return live_groups._date(x)


def local_fmt(value):
    dt = parse_date(value)
    return dt.astimezone(live_groups.CHICAGO).strftime('%Y-%m-%d %I:%M:%S %p') if dt else None


def stops_in_timetable(section):
    out = set()
    def visit(node):
        if isinstance(node, dict):
            for key, val in node.items():
                if key in ('sharedStopId', 'stopId') and isinstance(val, str):
                    out.add(val)
                elif isinstance(val, (dict, list)):
                    visit(val)
        elif isinstance(node, list):
            for val in node:
                visit(val)
    visit(section.get('liveTimetable', []))
    return out


def run(file_path, query):
    node, file = live_groups.load_live(file_path)
    stops = live_groups._read_stops()
    q = query.strip().casefold()
    matches = [s for s in stops if q in s.get('name','').casefold() or q in s.get('stop_id','').casefold()]
    match_ids = {s['stop_id'] for s in matches}
    names = {s['stop_id']: s['name'] for s in stops}
    ref = datetime.fromtimestamp(file.stat().st_mtime, timezone.utc)
    seen = set()
    total_states = Counter()
    found = []
    first_unmatched = None
    info = []
    for section_name, section in live_groups._iter_directions(node):
        timetable = stops_in_timetable(section)
        sc = Counter()
        state_counts = Counter()
        ride_stop_ids = set()
        for arr_name in ('liveRides','nonliveRides'):
            for item in section.get(arr_name, []) if isinstance(section.get(arr_name), list) else []:
                outer, ride = live_groups._ride_data(item)
                raw_statuses = ride.get('stopStatus')
                if not isinstance(raw_statuses, list):
                    sc['rides_without_stopStatus'] += 1
                    continue
                sc['rides_with_stopStatus'] += 1
                for st in raw_statuses:
                    if not isinstance(st, dict):
                        continue
                    state, details = live_groups._stop_status(st)
                    sid = live_groups._stop_id(st, details)
                    if sid:
                        ride_stop_ids.add(sid)
                    total_states[state] += 1
                    if first_unmatched is None and sid not in match_ids:
                        first_unmatched = {'stop_id': sid, 'name_in_catalog': names.get(sid), 'keys': sorted(st)}
                    if sid not in match_ids:
                        continue
                    sc['matching_status_entries'] += 1
                    state_counts[state] += 1
                    arrival = details.get('expectedArrivalTime') or st.get('expectedArrivalTime')
                    sched = details.get('scheduledDepartureTime') or st.get('scheduledDepartureTime')
                    dt = parse_date(arrival) or parse_date(sched)
                    reason = 'would_be_included'
                    if state not in ('Awaiting', 'Arriving'):
                        reason = 'filtered_by_state'
                    elif dt and dt < ref:
                        reason = 'filtered_as_past'
                    # v3 currently retains future status even if no time is available; marks unknown here.
                    elif dt is None:
                        reason = 'time_unavailable'
                    sc[reason] += 1
                    key = (sid, ride.get('rideId') or outer.get('rideId'), state, str(arrival), str(sched))
                    if key in seen: continue
                    seen.add(key)
                    found.append({
                        'stop_name': names.get(sid),
                        'direction': section.get('direction'),
                        'record': arr_name,
                        'state': state,
                        'rider_status': details.get('riderStatus'),
                        'expected_local': local_fmt(arrival),
                        'scheduled_departure_local': local_fmt(sched),
                        'reason': reason,
                        'ride_id': ride.get('rideId') or outer.get('rideId'),
                    })
        info.append({
            'direction': section.get('direction'),
            'collection': section_name,
            'rides_with_stop_status': sc['rides_with_stopStatus'],
            'distinct_stops_in_rides': len(ride_stop_ids),
            'matched_ids_in_timetable': [names.get(sid, sid) for sid in sorted(timetable & match_ids)],
            'matched_ids_in_ride_status': [names.get(sid, sid) for sid in sorted(ride_stop_ids & match_ids)],
            'matching_status_entries': sc['matching_status_entries'],
            'state_counts_for_matched': dict(state_counts),
            'why_no_arrivals': {k: sc[k] for k in ('filtered_by_state','filtered_as_past','time_unavailable','would_be_included')},
        })
    reason_counts = Counter(x['reason'] for x in found)
    found.sort(key=lambda x: x['expected_local'] or x['scheduled_departure_local'] or '')
    output = {
        'snapshot_local_file': str(file),
        'snapshot_file_saved_local': ref.astimezone(live_groups.CHICAGO).isoformat(timespec='seconds'),
        'route_group': node.get('sharedRouteId'),
        'matching_catalog_stops': [{'name': s['name'], 'stop_id': s['stop_id']} for s in matches],
        'direction_diagnostics': info,
        'total_distinct_matching_ride_records': len(found),
        'reasons_for_matching_records': dict(reason_counts),
        'example_matching_records_first_12': found[:12],
        'example_other_stop_status': first_unmatched,
        'notes': [
          'Saved JSON is historical, not a live feed. Snapshot file save time is not necessarily API response time.',
          'State-specific fields such as stopId are stored inside Awaiting/Skipped objects, not necessarily the outer stopStatus item.',
          'If stop IDs match but filtered_as_past is high, try a freshly saved snapshot or compare with a reference time from the response.',
          'If stops match the timetable but not ride statuses, inspect liveTrips and nonliveRides structures for separate ride-stop relationships.',
          'No requests are sent to TripShot; no secrets are accessed.'
        ]
    }
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    file_name = sys.argv[1] if len(sys.argv)>1 else 'data/live_response.json'
    stop_query = ' '.join(sys.argv[2:]) or 'Emerson'
    try:
        run(file_name, stop_query)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        sys.exit(f'ERROR: {e}')
