"""Northwestern 2026-27 *published* Loop timetable; NO live status.

Sources (checked 2026-10-17):
https://www.northwestern.edu/transportation-parking/shuttles/routes/loop.html
https://www.northwestern.edu/transportation-parking/shuttles/routes/schedules/loop-shuttle-cw.html
https://www.northwestern.edu/transportation-parking/shuttles/routes/schedules/loop-shuttle-ccw.html
Update when school revises schedules. All times America/Chicago.
"""
from __future__ import annotations
from datetime import datetime, date, time, timedelta
from tripshot_provider import CHICAGO

CW = [
    ('Library / Norris', 0), ('Campus Dr - Fisk Hall (SB)', 1),
    ('619 Clark (WB)', 3), ('Emerson/Maple (WB)', 5),
    ('Ridge/Garnett (NB)', 6), ('Noyes/Maple (EB)', 8),
    ('Noyes L (EB)', 9), ('Elder Hall - Lincoln (EB)', 12),
    ('Schapiro Hall', 13), ('Henry Crown Sports Pavilion', 16),
    ('Sheridan/Haven - Tech (SB)', 19), ('Sheridan/Foster (SB)', 20),
    ('Chicago/Sheridan (SB)', 21),
]
CCW = [
    ('Library / Norris', 0), ('Campus Dr - Fisk Hall (SB)', 1),
    ('Weber Arch', 3), ('Sheridan/Foster (NB)', 4),
    ('Sheridan/Haven - Tech (NB)', 5), ('Schapiro Hall', 6),
    ('Henry Crown Sports Pavilion', 9), ('Lincoln/Sheridan (WB)', 12),
    ('Noyes L (WB)', 14), ('Ridge - Civic Center (SB)', 16),
    ('Ridge/Garnett (SB)', 17), ('Emerson/Maple (EB)', 18),
    ('Elgin/Sherman (EB)', 19),
]


def in_service(service_day: date) -> bool:
    fall = date(2026, 9, 15) <= service_day <= date(2026, 12, 11)
    winter = date(2027, 1, 4) <= service_day <= date(2027, 6, 10)
    breaks = (date(2026, 11, 25) <= service_day <= date(2026, 11, 29)
              or date(2027, 3, 19) <= service_day <= date(2027, 3, 29)
              or date(2027, 5, 29) <= service_day <= date(2027, 5, 31))
    return (fall or winter) and not breaks


def normalize(s: str) -> str:
    import re
    return re.sub(r'[^a-z0-9]', '', s.casefold())


def lookup(query: str, start: datetime, end: datetime) -> dict:
    """Return approximate published stop passing times in [start, end].

    No claim that the shuttle operates today. Times come from a published table,
    not GPS, and are approximate. A stop query must match one catalog name.
    """
    start, end = start.astimezone(CHICAGO), end.astimezone(CHICAGO)
    q = normalize(query)
    records = []
    # Include prior day's service, since the final departure from Norris
    # is just before 1AM on the FOLLOWING calendar date.
    d = start.date() - timedelta(days=1)
    while d <= end.date():
        if in_service(d):
            for direction, table, base_minutes in [('Clockwise', CW, (15, 45)),
                                                   ('Counterclockwise', CCW, (0, 30))]:
                for stop, offset in table:
                    # 'Emerson' alone matches both; 'Emerson/Maple (EB)' exact one.
                    if q not in normalize(stop):
                        continue
                    for hour in (18, 19, 20, 21, 22, 23, 24):
                        for minute in base_minutes:
                            departure = datetime.combine(d, time(0, 0), CHICAGO) + timedelta(hours=hour, minutes=minute)
                            arrival = departure + timedelta(minutes=offset)
                            if start <= arrival <= end:
                                records.append({
                                    'stop_name': stop,
                                    'stop_id': None,
                                    'direction': direction,
                                    'loop_direction': {'label': direction, 'confidence':'published_schedule', 'basis':'northwestern_official_table'},
                                    'ride_id': None,
                                    'route_name':'Loop Shuttle', 'route_group':'Loop',
                                    'record_type':'published_schedule', 'status':'Scheduled',
                                    'reported_expected_arrival_local': None,
                                    'scheduled_departure_local': arrival.isoformat(timespec='seconds'),
                                    'last_eta_update_local': None,
                                    'data_fetched_at': None,
                                    'eta_timestamp_age_seconds': None,
                                    'eta_confidence':'published_schedule_only',
                                    'eta_explanation':'Approximate timetable entry; no TripShot live ETA or service confirmation.',
                                    'gps_verified': False,
                                    'source_url':'https://www.northwestern.edu/transportation-parking/shuttles/routes/loop.html',
                                    'service_day': d.isoformat(),
                                })
        d += timedelta(days=1)
    records.sort(key=lambda r:r['scheduled_departure_local'])
    return {'arrivals': records, 'schedule_scope':'2026-27 Loop only, within published term dates/breaks',
            'source':'NORTHWESTERN_PUBLISHED_APPROXIMATE_TIMETABLE'}
