"""Fetch each configured route ONCE and display reported upcoming arrivals.

Run: python shuttle_now.py 'Emerson/Maple (EB)'
Run: python shuttle_now.py Emerson --limit 8

* Not a proven GPS ETA; nonlive rides are schedule-based.
* Not a continuous monitoring agent, and not a hosted ChatGPT MCP service.
* Only service-day requests are used; around-midnight trips may need another day.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from tripshot_provider import CHICAGO, fetch_once, get_sources
from live_groups import arrivals
from stops_catalog import LOCAL_CATALOG
from tripshot_enrichment import resolve_query, decorate_rows
from published_loop import lookup as official_loop_lookup, normalize as normalize_stop_name
from published_full import lookup as full_published_lookup


def load_once(query: str, label: str, url: str, service_day: str) -> dict:
    payload = fetch_once(url, day=service_day)
    fetched = datetime.now(timezone.utc)
    # Local parser accepts a file path; write to a temporary file, then delete it.
    with tempfile.TemporaryDirectory(prefix='tripshot_') as folder:
        file = Path(folder) / 'response.json'
        file.write_text(json.dumps(payload), encoding='utf-8')
        result = arrivals(query, file, reference_time_iso=fetched.isoformat())
    result['arrivals'] = decorate_rows(result.get('arrivals', []), payload, label, fetched.astimezone(CHICAGO).isoformat())
    result['source'] = 'ONE_TIME_UNAUTHENTICATED_HTTP_FETCH'
    result['route_label'] = label
    result['fetched_at_local'] = fetched.astimezone(CHICAGO).isoformat(timespec='seconds')
    result['warning'] = ('This is a one-time TripShot web response, not a verified GPS prediction. '
                         'Non-live ride times may be scheduled; the result is not continuously updated.')
    return result


def service_days_for(now: datetime) -> list[str]:
    """Cover both calendar days when service can cross midnight.

    At late night, tomorrow's service day might expose after-midnight runs;
    shortly after midnight, yesterday's service day might still be running.
    Run only on explicit user requests; no background polling.
    """
    local = now.astimezone(CHICAGO)
    today = local.date()
    if local.hour < 3:
        days = (today - timedelta(days=1), today)
    elif local.hour >= 22:
        days = (today, today + timedelta(days=1))
    else:
        days = (today,)
    return [day.isoformat() for day in days]


def combine(query: str, sources: dict[str, str], *, limit: int = 8,
            service_day: str | None = None, horizon_hours: int = 4) -> dict:
    if not isinstance(horizon_hours, int) or not 1 <= horizon_hours <= 12:
        raise ValueError('horizon_hours must be 1..12')
    now = datetime.now(CHICAGO)
    if LOCAL_CATALOG.exists():
        resolved = resolve_query(query)
        if 'error' in resolved:
            return {**resolved, 'stop_query':query, 'arrivals':[], 'total_matched':0, 'coverage':[],
                    'queried_at_local':now.isoformat(timespec='seconds')}
        query_for_parser = resolved['resolved']
    else:
        query_for_parser = query
    days = [service_day] if service_day else service_days_for(now)
    all_rows = []
    coverage = []
    for label, url in sources.items():
        for day in days:
            try:
                report = load_once(query_for_parser, label, url, day)
                for r in report['arrivals']:
                    rec = dict(r)
                    rec['route_group'] = label
                    rec['data_fetched_at'] = report['fetched_at_local']
                    rec['queried_service_day'] = day
                    all_rows.append(rec)
                coverage.append({'route': label, 'service_day': day, 'ok': True,
                                 'rides_examined': report['rides_examined'],
                                 'matched_stops': [r['name'] for r in report['matching_stops']],
                                 'arrival_count': len(report['arrivals'])})
            except Exception as exc:
                coverage.append({'route': label, 'service_day': day, 'ok': False,
                                 'error': f'{type(exc).__name__}: {exc}'})
    # Require an actual, timezone-aware arrival time; do not silently treat an
    # unknown time as a scheduled departure or a trip serving now.
    horizon_end = now + timedelta(hours=horizon_hours)
    retained = []
    for row in all_rows:
        stamp = row.get('reported_expected_arrival_local') or row.get('scheduled_departure_local')
        if not stamp:
            continue
        try:
            at = datetime.fromisoformat(stamp)
        except ValueError:
            continue
        if at.tzinfo is None:
            continue
        if now - timedelta(seconds=30) <= at <= horizon_end:
            retained.append(row)
    retained.sort(key=lambda r: (r.get('reported_expected_arrival_local') or
                                 r.get('scheduled_departure_local'), r['stop_name']))
    distinct = []
    seen = set()
    for row in retained:
        # Deduplicate a ride repeated in both adjacent service-day responses.
        key = (row['route_group'], row.get('ride_id'), row.get('stop_id'),
               row.get('reported_expected_arrival_local') or row.get('scheduled_departure_local'))
        if key not in seen:
            distinct.append(row)
            seen.add(key)
    return {'stop_query': query, 'queried_service_days': days,
            'queried_at_local': now.isoformat(timespec='seconds'),
            'horizon_hours': horizon_hours, 'coverage': coverage,
            'arrivals': distinct[:limit], 'total_matched': len(distinct),
            'warning': ('One-time web retrieval; not verified GPS ETA. '
                        'Overnight uses adjacent service dates with deduplication, '
                        'but TripShot service-day semantics may differ.')}




def _parse_local_target(when_local: str) -> datetime:
    """Explicit YYYY-MM-DDTHH:MM[:SS] local date/time (Chicago)."""
    if not isinstance(when_local, str):
        raise ValueError('when_local must be a Chicago local timestamp, e.g. 2026-10-20T19:30')
    try:
        dt = datetime.fromisoformat(when_local)
    except ValueError as e:
        raise ValueError('Use YYYY-MM-DDTHH:MM in America/Chicago, e.g. 2026-10-20T19:30') from e
    dt = dt.replace(tzinfo=CHICAGO) if dt.tzinfo is None else dt.astimezone(CHICAGO)
    return dt


def planned_at_time(query: str, when_local: str, sources: dict[str,str], *,
                    before_minutes: int=30, after_minutes: int=90, limit: int=12) -> dict:
    """COMPLETE 2026-27 published timetable for all 4 directions, all stops.

    Unlike real-time queries, schedule lookup requires neither an active bus
    nor a successful TripShot request. Every ride retains a run identifier so
    boarding-to-alighting calculations can use the SAME scheduled vehicle.
    """
    now = datetime.now(CHICAGO)
    target = _parse_local_target(when_local)
    if target < now - timedelta(minutes=1):
        return {'error':'requested_time_in_past','message':'Use a future Chicago time.'}
    if target > now + timedelta(days=30):
        return {'error':'date_out_of_range','message':'Queries are limited to the next 30 days.'}
    if not all(isinstance(x,int) and not isinstance(x,bool) for x in (before_minutes, after_minutes)) or not 0<=before_minutes<=120 or not 1<=after_minutes<=180:
        return {'error':'invalid_window','message':'Before window must be 0–120 minutes; after window 1–180 minutes.'}
    start, end = target-timedelta(minutes=before_minutes), target+timedelta(minutes=after_minutes)
    result=full_published_lookup(query,start,end,limit=limit)
    result.update({'requested_time_local':target.isoformat(timespec='minutes'),
                   'window_start_local':start.isoformat(timespec='minutes'),
                   'window_end_local':end.isoformat(timespec='minutes'),
                   'queried_at_local':now.isoformat(timespec='seconds')})
    return result


def _clock(value: str | None):
    if not value:
        return 'time unavailable'
    try:
        return datetime.fromisoformat(value).strftime('%I:%M:%S %p').lstrip('0')
    except ValueError:
        return value


def main():
    parser = argparse.ArgumentParser(description='One-time read-only Northwestern TripShot arrivals')
    parser.add_argument('stop', nargs='?', default='Emerson/Maple (EB)', help='Name/substring of stop')
    parser.add_argument('--limit', type=int, default=8, help='Maximum number of results (1-20)')
    parser.add_argument('--json', action='store_true', help='Print machine-readable results')
    parser.add_argument('--at', metavar='YYYY-MM-DDTHH:MM', help='Look up PUBLISHED planned times near a specified future Chicago time (not live)')
    parser.add_argument('--before-minutes', type=int, default=30)
    parser.add_argument('--after-minutes', type=int, default=90)
    parser.add_argument('--save-json', metavar='FILE', help='Save output to UTF-8 JSON file directly (avoids PowerShell output encoding issues)')
    args = parser.parse_args()
    if not 1 <= args.limit <= 20:
        parser.error('--limit must be 1..20')
    try:
        result = (planned_at_time(args.stop, args.at, {},
                                  before_minutes=args.before_minutes, after_minutes=args.after_minutes,
                                  limit=args.limit) if args.at
                  else combine(args.stop, get_sources(), limit=args.limit))
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    if result.get('error'):
        print(json.dumps(result, indent=2))
        return
    if args.save_json:
        path = Path(args.save_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        if not args.json:
            print(f'Saved UTF-8 JSON to: {path}')
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(f'\nTripShot {"future schedule" if args.at else "one-time current"} lookup: {result["stop_query"]}')
    if args.at:
        print(f'Future SCHEDULE-ONLY window: {result["window_start_local"]} through {result["window_end_local"]}')
    else:
        print(f'Service days: {", ".join(result["queried_service_days"])}; queried {result["queried_at_local"]}')
    for group in result['coverage']:
        if group['ok']:
            if args.at:
                print(f'- {group["route"]}: {group["arrival_count"]} planned stops ({group.get("source", "unknown")})')
            else:
                print(f'- {group["route"]} ({group["service_day"]}): {group["rides_examined"]} rides examined, {group["arrival_count"]} upcoming stop records')
        else:
            print(f'- {group["route"]} ({group.get("service_day", "?")}): request failed ({group["error"]})')
    if not result['arrivals']:
        print('\nNo matching upcoming arrivals returned by the configured routes. This does NOT prove the shuttle is not operating.')
    for item in result['arrivals']:
        src = 'published schedule' if item['record_type']=='published_schedule' else ('schedule/non-live' if item['record_type']=='scheduled_or_nonlive_ride' else 'ride in live data (GPS unverified)')
        display = _clock(item.get('reported_expected_arrival_local') or item.get('scheduled_departure_local'))
        shown_direction = item.get('loop_direction', {}).get('label', item.get('direction'))
        print(f'\n{display} | {item["stop_name"]} | {item["route_name"]} [{shown_direction}]')
        print(f'  Status: {item["status"]}; confidence: {item.get("eta_confidence","unclassified")}; ETA update: {_clock(item.get("last_eta_update_local"))}')
    print('\nNote: Future times are planned/approximate only; current arrivals are not GPS-verified. Overnight service day interpretation may vary.')


if __name__ == '__main__':
    main()
