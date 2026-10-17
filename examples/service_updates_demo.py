r"""Offline October 16 demonstration; synthetic paraphrase and explicit year review.

No HTTP, production configuration, or persistent application-cache changes.
Run: .\.venv\Scripts\python.exe examples/service_updates_demo.py
"""
import json
import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['TRIPSHOT_DISABLE_SCHEDULE_REFRESH']='1'
os.environ['TRIPSHOT_DISABLE_SERVICE_REFRESH']='1'
import published_full as published
import service_updates as updates
from service_updates_parser import parse_page
from service_updates_source import PageResponse


def main():
    html='''<html><body><h2>Shuttle Service Updates</h2>
    <h3>Intercampus change - Friday, October 16</h3>
    <p>Intercampus operations are shortened between 4:30 p.m. and 11:10 p.m.</p>
    <p>No service at Central L, Central / Jackson, or Ryan Field stops.</p>
    <p>Northbound shuttles from Chicago end at Patten Gym.</p>
    <p>Southbound shuttles from Evanston begin at Noyes L.</p></body></html>'''
    notice=parse_page(html)['notices'][0]
    now=datetime(2026,10,16,21,tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as root:
        for label,context in (('No reviewed year: retain and downgrade',{}),
                              ('Explicit demonstration review of year 2026', {notice['revision']:{
                                  'year':2026,'reviewer':'Offline demonstration',
                                  'reason':'Explicit fixture context, not automatic source inference',
                                  'reviewed_at':now.isoformat()}})):
            state=updates.refresh(root=root,now=now,force=True,
                                  fetcher=lambda **k:PageResponse(200,html),reviewed_years=context)
            token=updates.PINNED.set(state)
            try:
                departures=published.lookup('Central L (EB)',
                    datetime.fromisoformat('2026-10-16T16:20-05:00'),
                    datetime.fromisoformat('2026-10-16T17:00-05:00'))
                trip=published.plan_trip('Central L (EB)','Ward Building','2026-10-16T16:20')
            finally:updates.PINNED.reset(token)
            print(label)
            print(json.dumps({'published_departure':departures['arrivals'][0]['scheduled_departure_local'],
                              'service_impact':departures['arrivals'][0]['service_impact'],
                              'recommended_journeys':len(trip['options']),
                              'excluded_journeys':trip['total_excluded_options'],
                              'normal_service_confirmed':departures['normal_service_confirmed']},indent=2))


if __name__=='__main__':main()
