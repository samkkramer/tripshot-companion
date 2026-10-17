"""2026-27 Northwestern *published approximate* Loop & Intercampus timetables.

Every stop in all four official route-direction tables is represented. This is
SCHEDULE data, never a real-time arrival prediction. Sources were checked
October 17, 2026. Do not extrapolate beyond the published 2026-27 calendar.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

from tripshot_provider import CHICAGO
from published_loop import CW, CCW, in_service as loop_in_service
from published_intercampus import HOLIDAYS

SOURCES = {
    'Loop Clockwise': 'https://www.northwestern.edu/transportation-parking/shuttles/routes/schedules/loop-shuttle-cw.html',
    'Loop Counterclockwise': 'https://www.northwestern.edu/transportation-parking/shuttles/routes/schedules/loop-shuttle-ccw.html',
    'Intercampus Evanston to Chicago': 'https://www.northwestern.edu/transportation-parking/shuttles/routes/schedules/intercampus-evanston-to-chicago.html',
    'Intercampus Chicago to Evanston': 'https://www.northwestern.edu/transportation-parking/shuttles/routes/schedules/intercampus-chicago-to-evanston.html',
}

# Source: complete Northwestern University Evanston -> Chicago table. 30 columns,
# one run per departure. Every intermediate station has the published fixed
# offset from Ryan Field; Ward Building has a trip-specific arrival table.
E2C_DEPARTURES = '''0635 0650 0705 0735 0820 0900 0920 1000 1030 1105 1150 1230 1250 1325 1355 1435 1455 1520 1545 1600 1630 1700 1710 1725 1750 1805 1820 1915 2025 2130'''.split()
E2C_STOPS = [
    ('Ryan Field - Ashland/Walker Way (SB)', 0),
    ('Central/Jackson (EB)', 1),
    ('Central L (EB)', 2),
    ('Noyes L (WB)', 4),
    ('Ridge Ave - Civic Center (SB)', 6),
    ('Ridge/Garnett (SB)', 7),
    ('Emerson/Maple (EB)', 9),
    ('Sherman/Emerson (IB)', 11),  # NU webpage calls it (NB), TripShot says (IB)
    ('Sherman/Foster (NB)', 12),
    ('Sherman/Gaffield (NB)', 13),
    ('Sheridan/Haven - Tech (SB)', 15),
    ('Sheridan/Foster (SB)', 17),
    ('Chicago/Sheridan (SB)', 19),
    ('Chicago/Grove (SB)', 22),
    ('Chicago/Greenleaf (SB)', 25),
    ('Chicago/Main (SB)', 26),
    ('Sheridan/Loyola (SB)', 36),
]
# Published Ward arrival times vary with traffic; never replace them with a
# made-up constant offset. Exact times from the source's final row (30 columns).
E2C_WARD = '''0751 0806 0821 0851 0926 1006 1021 1053 1123 1158 1243 1323 1343 1418 1448 1528 1556 1621 1646 1711 1736 1811 1821 1841 1856 1911 1926 2011 2118 2223'''.split()

# Source: complete official Chicago -> Evanston table. Each 29-value row
# corresponds to the same ride index. Trip-specific variation is preserved.
C2E_ROWS = [
 ('Ward Building', '''0640 0720 0800 0815 0830 0900 0930 1010 1100 1135 1200 1230 1300 1340 1425 1445 1535 1605 1625 1650 1705 1720 1750 1820 1830 1930 2015 2135 2225'''),
 ('Sheridan/Loyola (NB)', '''0705 0748 0826 0841 0856 0926 0956 1032 1123 1158 1225 1255 1322 1402 1445 1505 1556 1632 1652 1717 1732 1747 1817 1842 1852 1952 2037 2155 2243'''),
 ('Chicago/Kedzie (NB)', '''0715 0758 0836 0851 0906 0936 1006 1042 1133 1208 1235 1305 1332 1412 1455 1515 1606 1642 1702 1727 1742 1757 1827 1852 1902 2002 2047 2205 2253'''),
 ('Chicago/Greenleaf (NB)', '''0717 0800 0838 0853 0908 0938 1008 1044 1135 1210 1237 1307 1334 1414 1457 1517 1608 1644 1704 1729 1744 1759 1829 1854 1904 2004 2049 2207 2255'''),
 ('Chicago/Davis (NB)', '''0720 0803 0841 0856 0911 0941 1011 1047 1138 1213 1240 1310 1337 1417 1500 1520 1611 1647 1707 1732 1747 1802 1832 1857 1907 2007 2052 2210 2258'''),
 ('Weber Arch', '''0723 0806 0844 0859 0914 0944 1014 1050 1141 1216 1243 1313 1340 1420 1503 1523 1614 1650 1710 1735 1750 1805 1835 1900 1910 2010 2055 2213 2301'''),
 ('Sheridan/Foster (NB)', '''0724 0807 0845 0900 0915 0945 1015 1051 1142 1217 1244 1314 1341 1421 1504 1524 1615 1651 1711 1736 1751 1806 1836 1901 1911 2011 2056 2214 2302'''),
 ('Sheridan/Haven - Tech (NB)', '''0725 0808 0846 0901 0916 0946 1016 1052 1143 1218 1245 1315 1342 1422 1505 1525 1616 1652 1712 1737 1752 1807 1837 1902 1912 2012 2057 2215 2303'''),
 ('Sheridan/Lincoln (NB)', '''0726 0809 0847 0902 0917 0947 1017 1053 1144 1219 1246 1316 1343 1423 1506 1526 1617 1653 1713 1738 1753 1808 1838 1903 1913 2013 2058 2216 2304'''),
 ('Central L (WB)', '''0729 0812 0850 0905 0920 0950 1020 1056 1147 1222 1249 1319 1346 1426 1509 1529 1620 1656 1716 1741 1756 1811 1841 1906 1916 2016 2101 2219 2307'''),
 ('Central/Jackson (WB)', '''0730 0813 0851 0906 0921 0951 1021 1057 1148 1223 1250 1320 1347 1427 1510 1530 1621 1657 1717 1742 1757 1812 1842 1907 1917 2017 2102 2220 2308'''),
 ('Ryan Field - Ashland/Walker Way (SB)', '''0732 0815 0853 0908 0923 0953 1023 1059 1150 1225 1252 1322 1349 1429 1512 1532 1623 1659 1719 1744 1759 1814 1844 1909 1919 2019 2104 2222 2310'''),
]


def norm(s: str) -> str:
    s = str(s).lower().replace('northbound', 'nb').replace('southbound', 'sb')
    s = re.sub(r'\b(?:ave|avenue)\b', '', s)
    return re.sub('[^a-z0-9]', '', s)


def _minutes(code: str) -> int:
    if not re.fullmatch(r'\d{4}', code):
        raise ValueError(f'Invalid HHMM {code!r}')
    h, m = int(code[:2]), int(code[2:])
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError(f'Invalid HHMM {code!r}')
    return h * 60 + m


def _validate_tables():
    if len(E2C_DEPARTURES) != 30 or len(E2C_WARD) != 30:
        raise ValueError('Evanston -> Chicago timetable incomplete')
    if len(C2E_ROWS) != 12 or any(len(x[1].split()) != 29 for x in C2E_ROWS):
        raise ValueError('Chicago -> Evanston timetable incomplete')
    for code in E2C_DEPARTURES + E2C_WARD:
        _minutes(code)
    for _, s in C2E_ROWS:
        for code in s.split(): _minutes(code)
    assert len(E2C_STOPS) == 17

_validate_tables()



# v10: updateable schedule overlay. The legacy constants above are the
# bundled LAST-KNOWN-GOOD fallback; they are never modified at runtime.
def bundled_timetables() -> dict:
    e2c_rows = [[f'{(_minutes(code) + offset)//60:02d}{(_minutes(code) + offset)%60:02d}'
                 for code in E2C_DEPARTURES] for _stop, offset in E2C_STOPS]
    e2c_rows.append(list(E2C_WARD))
    return {
      'Loop Clockwise': {'stops':[s for s,_ in CW],
                         'offsets_minutes':[m for _,m in CW]},
      'Loop Counterclockwise': {'stops':[s for s,_ in CCW],
                                'offsets_minutes':[m for _,m in CCW]},
      'Intercampus Evanston to Chicago': {
          'stops':[s for s,_ in E2C_STOPS]+['Ward Building'], 'rows_hhmm':e2c_rows},
      'Intercampus Chicago to Evanston': {
          'stops':[s for s,_ in C2E_ROWS],
          'rows_hhmm':[v.split() for _,v in C2E_ROWS]},
    }


def timetable_status() -> dict:
    from published_sync import get_status, load_active, signature
    active=load_active()
    state=get_status()
    return {'timetable_revision': active['revision'] if active else signature(bundled_timetables()),
            'timetable_source': 'auto_refreshed' if active else 'bundled_2026_27',
            'timetable_checked_at_utc':state.get('checked_at_utc'),
            'timetable_check_status':state.get('status','not_checked'),
            'timetable_check_error':state.get('error'),
            'timetable_warning': 'Published schedule changes and service exceptions are distinct. '
                                 'Temporary route closures and holiday changes are not auto-applied; '
                                 'check Northwestern service updates.'}


def check_timetable_updates(*, force: bool = False) -> dict:
    from published_sync import check_updates
    return check_updates(bundled_timetables(),SOURCES,force=force)


def active_timetables(*, auto_check: bool = True) -> dict:
    from published_sync import load_active
    if auto_check and os.getenv('TRIPSHOT_DISABLE_SCHEDULE_REFRESH') != '1':
        check_timetable_updates()
    active=load_active()
    return active['routes'] if active else bundled_timetables()

def intercampus_service(day: date) -> bool:
    return date(2026, 9, 1) <= day <= date(2027, 8, 31) and day.weekday() < 5 and day not in HOLIDAYS


def route_stops() -> list[dict]:
    data=active_timetables()
    return [{'route':'Loop' if name.startswith('Loop') else 'Intercampus',
             'direction':name.split(' ',1)[1],
             'stops':item['stops'], 'source_url':SOURCES[name]}
            for name,item in data.items()]


def _events_on_day(day: date, data=None):
    """Yield route/direction/run ID and stop times from active validated tables."""
    data = data or active_timetables()
    if loop_in_service(day):
        for direction, base_minutes in (('Clockwise',(15,45)),('Counterclockwise',(0,30))):
            table=data['Loop '+direction]
            for hour in range(18,25):
                for minute in base_minutes:
                    depart=datetime.combine(day,time(0),CHICAGO)+timedelta(hours=hour,minutes=minute)
                    seq=[(name,depart+timedelta(minutes=offset))
                         for name,offset in zip(table['stops'],table['offsets_minutes'])]
                    yield ('Loop',direction,f'{day}:{direction}:{hour:02d}{minute:02d}',seq)
    if intercampus_service(day):
        for label,direction,short in (
              ('Intercampus Evanston to Chicago','Evanston to Chicago','E2C'),
              ('Intercampus Chicago to Evanston','Chicago to Evanston','C2E')):
            tab=data[label]
            n=len(tab['rows_hhmm'][0])
            for i in range(n):
                seq=[(name,datetime.combine(day,time(0),CHICAGO)+
                      timedelta(minutes=_minutes(tab['rows_hhmm'][j][i])))
                      for j,name in enumerate(tab['stops'])]
                yield ('Intercampus',direction,f'{day}:{short}:{i}',seq)


def generate_runs(start: datetime, end: datetime):
    d = start.astimezone(CHICAGO).date() - timedelta(days=1)
    through = end.astimezone(CHICAGO).date()
    data = active_timetables()
    while d <= through:
        yield from _events_on_day(d,data)
        d += timedelta(days=1)


def _matched(name: str, query: str) -> bool:
    q = norm(query)
    if not q:
        return False
    # Abbreviation mismatch: Northwestern's website says NB whereas TripShot
    # calls Sherman/Emerson "IB". 'Sherman/Emerson (IB)' should still match.
    q = q.replace('shermanemersonib','shermanemersonnb')
    # TripShot's local stop catalog and Northwestern's published table use
    # different names at a few shared physical locations.
    aliases = {
        'campusdrnorriscenter': 'librarynorris',
        'norriscenter': 'librarynorris',
        'lincolnaveelderhalleb': 'elderhalllincolneb',
        'elginandshermaneb': 'elginshermaneb',
    }
    q = aliases.get(q, q)
    if q == 'norris': return 'norris' in norm(name)
    if q in {'ward','wardbuilding'}: return 'ward' in norm(name)
    return q in norm(name)


def _scheduled_record(route, direction, ride, stop, at):
    return {
        'stop_name': stop, 'stop_id': None, 'direction': direction,
        'route_name': 'Loop Shuttle' if route == 'Loop' else f'Intercampus - {direction}',
        'route_group': route, 'ride_id': ride,
        'record_type': 'published_schedule', 'status': 'Scheduled',
        'reported_expected_arrival_local': None,
        'scheduled_departure_local': at.isoformat(timespec='seconds'),
        'eta_confidence': 'published_schedule_only',
        'eta_explanation': 'Northwestern published approximate timetable, not a live or GPS ETA.',
        'last_eta_update_local': None, 'gps_verified': False,
        'source_url': SOURCES[f'{route} {direction}'],
        'service_day': ride.split(':')[0],
    }


def lookup(query: str, start: datetime, end: datetime, limit: int = 20) -> dict:
    if not query or not query.strip():
        return {'error':'invalid_stop_query', 'message':'Supply stop name; use list_published_routes to browse all routes/stops.'}
    rows, coverage = [], []
    for route, direction, ride, seq in generate_runs(start,end):
        for stop, at in seq:
            if start <= at <= end and _matched(stop,query):
                rows.append(_scheduled_record(route,direction,ride,stop,at))
    rows.sort(key=lambda r: (r['scheduled_departure_local'], r['route_group']))
    return {'stop_query':query,'arrivals':rows[:limit],'total_matched':len(rows),
            'data_type':'SCHEDULE_ONLY_NOT_LIVE',
            'coverage':[{'route':'Loop','direction':'both','all_published_stops':26,'ok':True},
                        {'route':'Intercampus','direction':'both','all_published_stops':30,'ok':True}],
            'source_urls': SOURCES,
            **timetable_status(),
            'schedule_scope':'Northwestern published 2026-27 timetable; known calendar exceptions in bundled rules',
            'warning':'Approximate published timetable, not a live arrival prediction; no confirmation a vehicle is operating or on time. An empty matching list does not prove the route never runs. Walking distances are not included.'}


def _get_candidates(query: str, routes: list[dict]):
    """Return matched names for orientation; never invent absent stops."""
    matches = []
    for route in routes:
        for name in route['stops']:
            if _matched(name,query):
                matches.append({'stop_name':name,'route':route['route'],'direction':route['direction']})
    return matches


def plan_trip(origin: str, destination: str, when_local: str, *, limit: int = 8, horizon_hours: int = 4):
    """Same-vehicle scheduled stop-to-stop itinerary; no unverified transfers.

    Returns rides with a valid later destination *on the same run*, their exact
    published stop-to-stop times, and whether the route serves each location.
    """
    try:
        at = datetime.fromisoformat(when_local)
    except Exception:
        return {'error':'invalid_date_time','message':'Use YYYY-MM-DDTHH:MM in America/Chicago.'}
    at = at.replace(tzinfo=CHICAGO) if at.tzinfo is None else at.astimezone(CHICAGO)
    end = at + timedelta(hours=horizon_hours)
    options=[]
    for route, direction, ride, seq in generate_runs(at,end):
        for oi,(oname,otime) in enumerate(seq):
            if not _matched(oname,origin) or not (at <= otime <= end): continue
            for di in range(oi+1,len(seq)):
                dname,dtime=seq[di]
                if not _matched(dname,destination):continue
                if dtime <= otime:continue
                options.append({'route':route, 'direction':direction,'ride_id':ride,
                                'board_stop':oname,'board_time_local':otime.isoformat(timespec='seconds'),
                                'alight_stop':dname,'alight_time_local':dtime.isoformat(timespec='seconds'),
                                'estimated_in_vehicle_minutes':round((dtime-otime).total_seconds()/60,1),
                                'stop_count':di-oi,'data_type':'PUBLISHED_SCHEDULE_NOT_LIVE',
                                'source_url':SOURCES[f'{route} {direction}']})
    options.sort(key=lambda x:(x['board_time_local'],x['estimated_in_vehicle_minutes']))
    known=route_stops()
    response={'from_query':origin,'to_query':destination,'after_local':at.isoformat(timespec='minutes'),
              'options':options[:limit],'total_matching_scheduled_rides':len(options),
              **timetable_status(),
              'walking_time_included':False,'real_time_included':False,
              'note':'Same-vehicle published approximate times; no transfers, traffic or walking time included.'}
    if not options:
        response['origin_stops_found'] = _get_candidates(origin,known)
        response['destination_stops_found'] = _get_candidates(destination,known)
        response['warning'] = 'No same-vehicle itinerary in this 4-hour window does not establish that no shuttle service exists. Try different hours or routes.'
    return response


def served_stops_near(latitude: float, longitude: float, limit: int = 12, radius_m: int = 3000) -> dict:
    """Filter locally imported TripShot stop coordinates to published route stops.

    Distances are geographic straight-line, not walking routes. The catalog
    was imported by the user; no tracking, external geocoding or location API.
    """
    from nearby_stops import haversine_m
    from stops_catalog import LOCAL_CATALOG
    if not LOCAL_CATALOG.is_file():
        return {'error':'missing_stop_catalog','message':'Import TripShot stops first.'}
    if isinstance(latitude,bool) or isinstance(longitude,bool) or not (-90<=latitude<=90) or not (-180<=longitude<=180):
        return {'error':'invalid_coordinates'}
    catalog = json.loads(LOCAL_CATALOG.read_text(encoding='utf-8'))
    routes = route_stops()
    matches=[]
    for s in catalog:
        la,lo=s.get('latitude'),s.get('longitude')
        if not isinstance(la,(int,float)) or not isinstance(lo,(int,float)):
            continue
        d = round(haversine_m(latitude,longitude,la,lo))
        if d > radius_m: continue
        serviced=[]
        for route in routes:
            if any(norm(s['name']) == norm(n) or _matched(n,s['name']) or _matched(s['name'],n)
                   for n in route['stops']):
                serviced.append({'route':route['route'],'direction':route['direction']})
        if serviced:
            matches.append({'stop_name':s['name'],'stop_id':s.get('stop_id'),
                            'latitude':la,'longitude':lo,'straight_line_meters':d,
                            'published_routes':serviced})
    matches.sort(key=lambda s:s['straight_line_meters'])
    return {'stops':matches[:limit], 'total':len(matches),
            'method':'straight_line_distance_no_walking_network',
            'warning':'A stop being near a place does not prove the route is useful or that walking access is direct.'}


def plan_to_coordinates(origin_query: str, destination_latitude: float, destination_longitude: float,
                        when_local: str, limit: int = 8):
    """Compare SAME-VEHICLE transit to geo-nearby dropoff stops.

    A straight-line walking-distance estimate is for ranking, NOT a navigation
    or real walking-time recommendation. We do not assert best stop by ETA alone.
    """
    nearby = served_stops_near(destination_latitude,destination_longitude,limit=20,radius_m=3000)
    if nearby.get('error'):return nearby
    rides=[]
    for stop in nearby['stops']:
        trip = plan_trip(origin_query,stop['stop_name'],when_local,limit=30)
        for opt in trip['options']:
            item = dict(opt)
            item['dropoff_straight_line_meters'] = stop['straight_line_meters']
            item['destination_stop_id'] = stop['stop_id']
            # Walking effort is an explicitly labeled rough proxy: 1.3 m/s,
            # *not* a road/walkable route computation.
            item['rough_walk_minutes_not_routed'] = round(stop['straight_line_meters']/78,1)
            item['rough_end_to_end_arrival_local'] = (
                datetime.fromisoformat(item['alight_time_local'])+
                timedelta(minutes=item['rough_walk_minutes_not_routed'])).isoformat(timespec='seconds')
            rides.append(item)
    rides.sort(key=lambda r:(r['rough_end_to_end_arrival_local'],r['board_time_local']))
    unique,seen=[],set()
    for r in rides:
        key=(r['ride_id'],r['destination_stop_id'])
        if key in seen:continue
        seen.add(key); unique.append(r)
    return {'origin_query':origin_query,'destination_latitude':destination_latitude,
            'destination_longitude':destination_longitude,
            'options':unique[:limit],'total_options':len(unique),
            'data_type':'PUBLISHED_SCHEDULE_ONLY',
            'walking_distance_method':'straight_line_not_walkable_route',
            'warning':'Do not call this the fastest walking route or guaranteed arrival; confirm accessibility and walking directions separately.'}
