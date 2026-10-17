"""Offline regression tests for v10 official timetable synchronization."""
import copy
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from unittest.mock import patch

os.environ['TRIPSHOT_DISABLE_SCHEDULE_REFRESH']='1'
import published_full as pf
import published_sync as ps


def baseline_html(base):
    """Representative HTML fixtures in the public site timetable structure."""
    pages={}
    for label,route in base.items():
        is_loop=label.startswith('Loop')
        body=['<table><caption>Official approximate timetable</caption>',
              '<thead><tr><th>Station</th><th colspan="30">Approximate Time</th></tr></thead><tbody>']
        for i,name in enumerate(route['stops']):
            if is_loop:
                depart=15 if label=='Loop Clockwise' else 0
                offset=route['offsets_minutes'][i]
                cells=[f':{(depart+offset)%60:02d}',f':{(depart+30+offset)%60:02d}']
            else:
                cells=[]
                for hhmm in route['rows_hhmm'][i]:
                    hour=int(hhmm[:2]);minute=int(hhmm[2:])
                    marker='am' if hour<12 else 'pm'
                    hour12=hour%12 or 12
                    cells.append(f'{hour12}:{minute:02d} {marker}')
            body.append(f'<tr><th>{escape(name)}</th>'+''.join(f'<td>{v}</td>' for v in cells)+'</tr>')
        body.append('</tbody></table>')
        pages[label]='<html><nav>Site unrelated text changed</nav>'+''.join(body)+'</html>'
    return pages


class TimetableRefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.patchers=(patch.object(ps,'ACTIVE',self.dir/'active.json'),
                       patch.object(ps,'STATUS',self.dir/'status.json'),
                       patch.object(ps,'HISTORY',self.dir/'history'))
        for p in self.patchers:p.start();self.addCleanup(p.stop)
        self.base=pf.bundled_timetables()
        self.pages=baseline_html(self.base)
        self.now=datetime(2026,10,17,13,0,tzinfo=timezone.utc)

    def fetcher(self,lookup):
        return lambda url: lookup[next(k for k,v in pf.SOURCES.items() if v==url)]

    def test_complete_round_trip_same_schedule(self):
        parsed=ps.parse_four_pages(self.pages,self.base)
        self.assertEqual(parsed,self.base)

    def test_official_sherman_emerson_nb_alias(self):
        pages=dict(self.pages)
        label='Intercampus Evanston to Chicago'
        pages[label]=pages[label].replace('Sherman/Emerson (IB)', 'Sherman / Emerson (NB)')
        self.assertEqual(ps.parse_four_pages(pages,self.base),self.base)

    def test_changed_one_trip_promoted_and_diff_reported(self):
        new=copy.deepcopy(self.base)
        route=new['Intercampus Evanston to Chicago']
        for row in route['rows_hhmm']:
            num=int(row[0][:2])*60+int(row[0][2:])+2
            row[0]=f'{num//60:02d}{num%60:02d}'
        pages=baseline_html(new)
        outcome=ps.check_updates(self.base,pf.SOURCES,now=self.now,fetcher=self.fetcher(pages))
        self.assertEqual(outcome['status'],'updated')
        self.assertEqual(ps.load_active()['routes'],new)
        self.assertEqual(outcome['changes'][0]['route'],'Intercampus Evanston to Chicago')
        self.assertEqual(len(outcome['changes']),1)

    def test_no_network_for_not_due_check(self):
        first=ps.check_updates(self.base,pf.SOURCES,now=self.now,fetcher=self.fetcher(self.pages))
        self.assertEqual(first['status'],'unchanged')
        calls=[]
        out=ps.check_updates(self.base,pf.SOURCES,
                             now=self.now+timedelta(hours=1),fetcher=lambda u:calls.append(u))
        self.assertEqual(out['status'],'not_due')
        self.assertFalse(calls)

    def test_failure_keeps_last_good(self):
        ok=ps.check_updates(self.base,pf.SOURCES,now=self.now,fetcher=self.fetcher(self.pages))
        old=ps.load_active()
        corrupted=dict(self.pages)
        corrupted['Loop Clockwise']='<html>Could not parse the timetable</html>'
        out=ps.check_updates(self.base,pf.SOURCES,force=True,
                             now=self.now+timedelta(minutes=2),fetcher=self.fetcher(corrupted))
        self.assertEqual(out['status'],'error')
        self.assertEqual(ps.load_active(),old)
        self.assertIn('previous validated schedule',out['warning'])

    def test_new_stop_fails_closed(self):
        changed=copy.deepcopy(self.pages)
        key='Loop Clockwise'
        # Add a new route stop as a real table row. Do not drop it silently.
        changed[key]=changed[key].replace('</tbody>', '<tr><th>New University Stop</th><td>:25</td><td>:55</td></tr></tbody>')
        # This is a stricter desired policy; any additional time-bearing row
        # would otherwise cause the number of route stops to be wrong.
        with self.assertRaises(ps.TimetableFormatError):
            ps.parse_four_pages(changed,self.base)

    def test_route_change_reflected_in_future_lookup(self):
        with patch.object(pf,'active_timetables',return_value=self.base):
            result=pf.lookup('Emerson/Maple (EB)',
                             datetime.fromisoformat('2026-10-19T08:00:00-05:00'),
                             datetime.fromisoformat('2026-10-19T10:00:00-05:00'))
        self.assertTrue(any(x['scheduled_departure_local'].endswith('08:29:00-05:00')
                            for x in result['arrivals']))
        self.assertEqual(result['data_type'],'SCHEDULE_ONLY_NOT_LIVE')

    def test_service_calendar_not_guessed(self):
        info=pf.timetable_status()
        self.assertIn('not auto-applied',info['timetable_warning'])


if __name__=='__main__':unittest.main(verbosity=2)
