"""Limited 2026-27 Northwestern Intercampus schedule fallback for Emerson-area stops.

The official schedule states Mon–Fri except designated Northwestern holidays.
Source: https://www.northwestern.edu/transportation-parking/shuttles/routes/
        schedules/intercampus-evanston-to-chicago.html
This is a versioned *approximate* schedule, NOT a TripShot live prediction.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from tripshot_provider import CHICAGO
from published_loop import normalize

# Official row times, local Chicago clock, as published for Evanston->Chicago.
# NB: imported TripShot catalog calls Sherman/Emerson (IB), while official
# page calls the location Sherman / Emerson (NB).
STOP_TIMES = {
    'Emerson/Maple (EB)': '''06:44 06:59 07:14 07:44 08:29 09:09 09:29 10:09 10:39 11:14 11:59 12:39 12:59 13:34 14:04 14:44 15:04 15:29 15:54 16:09 16:39 17:09 17:19 17:34 17:59 18:14 18:29 19:24 20:34 21:39'''.split(),
    'Sherman/Emerson (IB)': '''06:46 07:01 07:16 07:46 08:31 09:11 09:31 10:11 10:41 11:16 12:01 12:41 13:01 13:36 14:06 14:46 15:06 15:31 15:56 16:11 16:41 17:11 17:21 17:36 18:01 18:16 18:31 19:26 20:36 21:41'''.split(),
}
HOLIDAYS = {date(2026,9,7),date(2026,11,26),date(2026,11,27),date(2026,12,24),date(2026,12,25),
            date(2026,12,28),date(2026,12,29),date(2026,12,30),date(2026,12,31),date(2027,1,1),
            date(2027,1,18),date(2027,5,31),date(2027,6,18),date(2027,7,5)}


def lookup(query: str, start: datetime, end: datetime) -> dict:
    q = normalize(query)
    rows = []
    day = start.astimezone(CHICAGO).date()
    while day <= end.astimezone(CHICAGO).date():
        # Schedule applies during the 2026-27 cycle; do not extrapolate forever.
        if day.weekday() < 5 and day not in HOLIDAYS and date(2026,9,1) <= day <= date(2027,8,31):
            for name, times in STOP_TIMES.items():
                if q not in normalize(name): continue
                for clock in times:
                    hh, mm = map(int,clock.split(':'))
                    at = datetime(day.year, day.month, day.day, hh, mm, tzinfo=CHICAGO)
                    if start <= at <= end:
                        rows.append({'stop_name':name,'stop_id':None,'direction':'Evanston to Chicago',
                                     'route_name':'Intercampus-Evanston to Chicago','route_group':'Intercampus',
                                     'record_type':'published_schedule','status':'Scheduled',
                                     'reported_expected_arrival_local':None,
                                     'scheduled_departure_local':at.isoformat(timespec='seconds'),
                                     'eta_confidence':'published_schedule_only',
                                     'eta_explanation':'Approximate Northwestern weekday timetable, not a live ETA.',
                                     'last_eta_update_local':None, 'gps_verified':False, 'ride_id':None,
                                     'source_url':'https://www.northwestern.edu/transportation-parking/shuttles/routes/schedules/intercampus-evanston-to-chicago.html'})
        day += timedelta(days=1)
    rows.sort(key=lambda a:a['scheduled_departure_local'])
    return {'arrivals':rows,'source':'NORTHWESTERN_PUBLISHED_APPROXIMATE_TIMETABLE'}
