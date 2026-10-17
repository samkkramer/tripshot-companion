"""Offline patch regression checks. Run python test_tripshot_v8.py."""
import json
import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

# Allows unit testing server tool wrappers even if MCP SDK isn't installed
# in a separate isolated testing environment. On user's machine, real SDK is used.
try:
    from mcp.server import MCPServer
except ImportError:
    mock_mcp = types.ModuleType('mcp')
    mock_server = types.ModuleType('mcp.server')
    class MCPServer:
        def __init__(self, name): self.name=name
        def tool(self): return lambda fn: fn
        def run(self,**kwargs): pass
    mock_server.MCPServer = MCPServer
    mock_mcp.server=mock_server
    sys.modules['mcp']=mock_mcp
    sys.modules['mcp.server']=mock_server

import tripshot_enrichment as enr
import published_loop
import published_intercampus
import shuttle_now
import server
CHI = shuttle_now.CHICAGO

class UpgradeTests(unittest.TestCase):
    def test_loop_direction_clockwise_from_multiple_stops(self):
        meta={'ordered_stop_names':['Campus Dr - Norris Center','619 Clark (WB)','Emerson/Maple (WB)',
                                    'Ridge/Garnett (NB)','Sheridan/Haven - Tech (SB)']}
        x=enr.direction_for(meta)
        self.assertEqual(x['label'],'Clockwise')
        self.assertEqual(x['confidence'],'high')

    def test_loop_direction_counterclockwise(self):
        meta={'ordered_stop_names':['Weber Arch','Sheridan/Haven - Tech (NB)',
                                    'Noyes L (WB)','Ridge/Garnett (SB)','Emerson/Maple']}
        self.assertEqual(enr.direction_for(meta)['label'],'Counterclockwise')

    def test_loop_id_provisional_not_verified(self):
        x=enr.direction_for({'navigation_id':'aeee6def-98e5-4c4e-bbbb-9f6ca51c8548'})
        self.assertEqual(x['confidence'],'provisional')

    def test_eta_timestamp_not_equal_prediction_changed(self):
        row = {'record_type':'ride_in_live_group','reported_expected_arrival_local':'2026-10-17T21:20:00-05:00',
               'scheduled_departure_local':'2026-10-17T21:20:00-05:00',
               'last_eta_update_local':'2026-10-17T21:19:59-05:00'}
        x=enr.label_arrival(row,'2026-10-17T21:20:01-05:00')
        self.assertEqual(x['eta_confidence'],'active_ride_schedule_matched')
        self.assertFalse(x['predictions_observed_changing'])
        row['reported_expected_arrival_local']='2026-10-17T21:22:15-05:00'
        x=enr.label_arrival(row,'2026-10-17T21:20:01-05:00')
        self.assertEqual(x['eta_confidence'],'active_ride_adjusted_eta_unverified')
        self.assertFalse(x['gps_verified'])

    def test_eta_schedule_nonlive_even_fresh(self):
        x=enr.label_arrival({'record_type':'scheduled_or_nonlive_ride',
             'last_eta_update_local':'2026-10-17T21:19:59-05:00'}, '2026-10-17T21:20:01-05:00')
        self.assertEqual(x['eta_confidence'],'scheduled_nonlive')

    def test_reverse_stop_order_returns_suggestions_without_network(self):
        with tempfile.TemporaryDirectory() as d:
            cat=Path(d)/'catalog.json'
            cat.write_text(json.dumps([{'stop_id':'s1','name':'Emerson/Maple (EB)'}]),encoding='utf8')
            with patch.object(enr,'LOCAL_CATALOG',cat), patch.object(shuttle_now,'LOCAL_CATALOG',cat):
                found=enr.resolve_query('Maple/Emerson')
                self.assertEqual(found['error'],'stop_name_order')
                with patch.object(shuttle_now,'load_once') as fetch:
                    x=shuttle_now.combine('Maple/Emerson', {'Loop':'URL'})
                    self.assertEqual(x['error'],'stop_name_order')
                    fetch.assert_not_called()

    def test_published_loop_after_midnight_uses_previous_service_day(self):
        start=datetime(2026,10,17,0,18,tzinfo=CHI)
        end=datetime(2026,10,17,0,21,tzinfo=CHI)
        rows=published_loop.lookup('Emerson/Maple',start,end)['arrivals']
        self.assertTrue(any(r['direction']=='Counterclockwise' and r['scheduled_departure_local'].startswith('2026-10-17T00:18') for r in rows))
        self.assertTrue(any(r['direction']=='Clockwise' and r['scheduled_departure_local'].startswith('2026-10-17T00:20') for r in rows))

    def test_published_loop_break_no_service_rows(self):
        a=datetime(2026,11,26,20,0,tzinfo=CHI)
        b=datetime(2026,11,26,20,40,tzinfo=CHI)
        self.assertEqual(published_loop.lookup('Emerson',a,b)['arrivals'],[])

    def test_published_intercampus_weekday_and_saturday(self):
        monday=datetime(2026,10,19,9,0,tzinfo=CHI)
        rows=published_intercampus.lookup('Emerson/Maple (EB)',monday,monday.replace(hour=9,minute=40))['arrivals']
        self.assertTrue(any(r['scheduled_departure_local'].startswith('2026-10-19T09:09') for r in rows))
        saturday=datetime(2026,10,17,9,0,tzinfo=CHI)
        self.assertEqual(published_intercampus.lookup('Emerson/Maple (EB)',saturday,saturday.replace(hour=9,minute=40))['arrivals'],[])

    def test_future_published_only_and_no_live_claim(self):
        future=datetime.now(CHI)+__import__('datetime').timedelta(days=2)
        target=future.replace(hour=20,minute=15,second=0,microsecond=0)
        with patch.object(shuttle_now,'LOCAL_CATALOG',Path('/DOES_NOT_EXIST')):
            x=shuttle_now.planned_at_time('Emerson/Maple (WB)',target.isoformat(timespec='minutes'),{'Loop':'notused'})
        self.assertEqual(x['data_type'],'SCHEDULE_ONLY_NOT_LIVE')
        self.assertTrue(all(r.get('gps_verified') is False for r in x['arrivals']))

    def test_tools_present_and_future_error_graceful(self):
        self.assertTrue(callable(server.get_next_shuttles))
        self.assertTrue(callable(server.get_shuttles_at_time))
        self.assertEqual(server.get_shuttles_at_time('', '2026-10-21T19:30')['error'],'invalid_stop_query')
        with patch.object(server,'get_sources',return_value={'Loop':'dummy'}),patch.object(server,'planned_at_time',return_value={'arrivals':[]}) as fn:
            r=server.get_shuttles_at_time('Emerson','2026-10-21T19:30',limit=30)
            self.assertIn('limit_notice',r)
            self.assertEqual(fn.call_args.kwargs['limit'],20)

if __name__=='__main__': unittest.main(verbosity=2)
