"""Explain the Loop/Intercampus route signatures without guessing direction.

Use: python inspect_route_directions.py Loop
Makes one GET request to the configured route only; prints no driver/rider data.
"""
from __future__ import annotations
import argparse
from datetime import datetime
from tripshot_provider import CHICAGO, fetch_once, get_sources
from live_groups import _iter_directions, _ride_data, _stop_status, _stop_id, _read_stops


def summarize(payload: dict, limit: int = 4) -> list[dict]:
    node = payload.get('InternalRouteGroupLiveData', payload)
    names = {str(s['stop_id']): str(s['name']) for s in _read_stops()}
    output = []
    for _, group in _iter_directions(node):
        live = group.get('liveRides', [])
        for entry in live[:limit]:
            outer, ride = _ride_data(entry)
            stops = []
            for stop in ride.get('stopStatus', []):
                if not isinstance(stop, dict):
                    continue
                state, info = _stop_status(stop)
                sid = _stop_id(stop, info)
                if sid:
                    stops.append({'name': names.get(sid, 'Unknown stop'), 'state': state})
            output.append({
                'group_direction': group.get('direction', 'Unknown'),
                'route_name': ride.get('routeName'),
                'route_id': ride.get('routeId'),
                'navigation_id': ride.get('effectiveNavigationId') or ride.get('navigationId'),
                'first_stops_in_order': stops[:12],
                'stop_total': len(stops),
            })
    return output


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('route', choices=['Intercampus', 'Loop'])
    args = cli.parse_args()
    today = datetime.now(CHICAGO).date().isoformat()
    payload = fetch_once(get_sources()[args.route], day=today)
    rows = summarize(payload)
    if not rows:
        print('No active rides: retry once while this service is operating, or inspect a saved response.')
        return
    for i, row in enumerate(rows, 1):
        print(f'\nRide {i} | route: {row["route_name"]} | API group direction: {row["group_direction"]}')
        print(f'Route ID: {row["route_id"]} | navigation ID: {row["navigation_id"]}')
        for stop in row['first_stops_in_order']:
            print(f'  {stop["name"]} [{stop["state"]}]')
        print(f'  (Showing up to 12 of {row["stop_total"]} stops)')
    print('\nDo NOT infer clockwise/counterclockwise from NonDirectional or WB alone.')
    print('Compare observed stop sequence with official route map before creating a verified direction mapping.')


if __name__ == '__main__':
    main()
