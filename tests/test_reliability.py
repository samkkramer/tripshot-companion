"""Migration prerequisite regressions; no live configuration or network needed."""
import copy
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import published_full as pf
import published_sync as ps
import server
import shuttle_now


class ReliabilityTests(unittest.TestCase):
    def test_future_mcp_does_not_read_live_sources(self):
        with patch.object(server,'get_sources',side_effect=AssertionError('live config read')), \
             patch.object(server,'planned_at_time',return_value={'arrivals':[]}) as call:
            self.assertEqual(server.get_shuttles_at_time('Emerson','2026-10-19T08:00')['arrivals'],[])
            self.assertEqual(call.call_args.args[2],{})

    def test_future_cli_does_not_read_live_sources(self):
        with patch('sys.argv',['shuttle_now.py','Emerson','--at','2026-10-19T08:00','--json']), \
             patch.object(shuttle_now,'get_sources',side_effect=AssertionError('live config read')), \
             patch.object(shuttle_now,'planned_at_time',return_value={'arrivals':[]}), \
             patch('sys.stdout',new_callable=io.StringIO):
            shuttle_now.main()

    def test_location_invalid_date_propagates(self):
        with patch.object(pf,'served_stops_near',return_value={'stops':[{'stop_name':'Ward Building'}]}):
            self.assertEqual(server.plan_scheduled_trip_to_location('Emerson',42,-87,'invalid')['error'],
                             'invalid_date_time')

    def test_status_shapes_and_timestamps(self):
        now=datetime(2026,10,17,tzinfo=timezone.utc)
        for stamp in (None,12,[], 'bad','2026-10-17T00:00:00','2027-01-01T00:00:00+00:00'):
            self.assertTrue(ps._due({'checked_at_utc':stamp},now,False))
        with tempfile.TemporaryDirectory() as d, patch.object(ps,'STATUS',Path(d)/'status.json'):
            for data in ('[]','null','{bad'):
                ps.STATUS.write_text(data,encoding='utf-8')
                self.assertIn('cache_warning',ps.get_status())
            ps.STATUS.write_text(json.dumps({'checked_at_utc':'2026-10-17T00:00:00','status':'unchanged'}))
            self.assertIsNone(ps.get_status()['checked_at_utc'])
            self.assertEqual(ps.get_status()['status'],'error')

    def test_corrupt_active_falls_back_and_history_recovers(self):
        with tempfile.TemporaryDirectory() as d, patch.object(ps,'ACTIVE',Path(d)/'active.json'), \
             patch.object(ps,'HISTORY',Path(d)/'history'):
            base=pf.bundled_timetables()
            for value in ([],None,{'schema':1,'routes':{}},'bad'):
                ps.ACTIVE.write_text(json.dumps(value),encoding='utf-8')
                self.assertEqual(pf.active_timetables(auto_check=False),base)
            malformed=copy.deepcopy(base)
            malformed['Loop Clockwise']['offsets_minutes']=[True]*13
            ps.ACTIVE.write_text(json.dumps({'schema':1,'routes':malformed,'revision':ps.signature(malformed)}))
            self.assertIsNone(ps.load_active())
            ps.HISTORY.mkdir()
            ps.HISTORY.joinpath('good.json').write_text(json.dumps(
                {'schema':1,'routes':base,'revision':ps.signature(base)}))
            self.assertIn('cache_warning',ps.load_active())
            self.assertEqual(pf.active_timetables(auto_check=False),base)
