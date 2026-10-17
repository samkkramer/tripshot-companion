"""Offline regression tests for complete 2026-27 timetables. No Internet access."""
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from tripshot_provider import CHICAGO
import published_full as pub
import shuttle_now
try:
    from mcp.server import MCPServer
except ImportError:
    # Only for isolated offline test runner; production requires real MCP SDK.
    import sys, types
    mod=types.ModuleType('mcp')
    srv=types.ModuleType('mcp.server')
    class MCPServer:
        def __init__(self,name): self.name=name
        def tool(self): return lambda fn: fn
        def run(self,**kwargs): pass
    srv.MCPServer=MCPServer
    mod.server=srv
    sys.modules['mcp']=mod
    sys.modules['mcp.server']=srv
import server


def ts(s): return datetime.fromisoformat(s).replace(tzinfo=CHICAGO)

class CompleteSchedules(unittest.TestCase):
    def test_four_directions_every_published_stop(self):
        rs=pub.route_stops()
        self.assertEqual([(r['route'],r['direction'],len(r['stops'])) for r in rs], [
            ('Loop','Clockwise',13),('Loop','Counterclockwise',13),
            ('Intercampus','Evanston to Chicago',18),('Intercampus','Chicago to Evanston',12)])

    def test_column_counts(self):
        self.assertEqual(len(pub.E2C_DEPARTURES),30)
        self.assertEqual(len(pub.E2C_WARD),30)
        self.assertEqual(len(pub.C2E_ROWS),12)
        self.assertEqual(set(len(row.split()) for _,row in pub.C2E_ROWS),{29})

    def test_departures_consistent_by_run(self):
        for day in [__import__('datetime').date(2026,10,19)]:
            for route,direction,ride,stops in pub._events_on_day(day):
                self.assertTrue(all(a[1] <= b[1] for a,b in zip(stops,stops[1:])),ride)

    def test_intercampus_evanston_to_chicago_entire_route(self):
        runs=[r for r in pub._events_on_day(__import__('datetime').date(2026,10,19)) if r[1]=='Evanston to Chicago']
        self.assertEqual(len(runs),30)
        trip=runs[4]
        self.assertEqual(trip[3][0][1].strftime('%H:%M'),'08:20')
        self.assertEqual(trip[3][6][1].strftime('%H:%M'),'08:29')
        self.assertEqual(trip[3][10][1].strftime('%H:%M'),'08:35')
        self.assertEqual(trip[3][-1][1].strftime('%H:%M'),'09:26')

    def test_intercampus_chicago_to_evanston_entire_route(self):
        runs=[r for r in pub._events_on_day(__import__('datetime').date(2026,10,19)) if r[1]=='Chicago to Evanston']
        self.assertEqual(len(runs),29)
        third=runs[2][3]
        self.assertEqual(third[0][1].strftime('%H:%M'),'08:00')
        self.assertEqual(third[7][1].strftime('%H:%M'),'08:46')
        self.assertEqual(third[-1][1].strftime('%H:%M'),'08:53')

    def test_any_intercampus_stop_published_future(self):
        result=pub.lookup('Chicago/Davis',ts('2026-10-19T08:00'),ts('2026-10-19T09:30'))
        self.assertEqual(result['total_matched'],4)
        self.assertEqual(result['arrivals'][1]['stop_name'],'Chicago/Davis (NB)')

    def test_loop_gym_henry_crown_not_morning(self):
        morning=pub.lookup('Henry Crown',ts('2026-10-19T08:00'),ts('2026-10-19T10:00'))
        evening=pub.lookup('Henry Crown',ts('2026-10-19T19:00'),ts('2026-10-19T20:00'))
        self.assertEqual(morning['arrivals'],[])
        self.assertGreaterEqual(evening['total_matched'],2)
        self.assertEqual({x['direction'] for x in evening['arrivals']},{'Clockwise','Counterclockwise'})

    def test_loop_after_midnight_uses_friday_service(self):
        data=pub.lookup('Emerson/Maple',ts('2026-10-17T00:17'),ts('2026-10-17T00:21'))
        self.assertIn('2026-10-17T00:18:00-05:00',[x['scheduled_departure_local'] for x in data['arrivals']])
        self.assertIn('2026-10-17T00:20:00-05:00',[x['scheduled_departure_local'] for x in data['arrivals']])

    def test_intercampus_holiday_and_weekend(self):
        self.assertFalse(pub.intercampus_service(__import__('datetime').date(2026,10,17)))
        self.assertFalse(pub.intercampus_service(__import__('datetime').date(2026,11,26)))

    def test_same_ride_board_and_alight(self):
        x=pub.plan_trip('Emerson/Maple (EB)','Sheridan/Haven - Tech (SB)','2026-10-19T08:00')
        self.assertTrue(x['options'])
        self.assertEqual(x['options'][0]['board_time_local'][11:16],'08:29')
        self.assertEqual(x['options'][0]['alight_time_local'][11:16],'08:35')
        self.assertEqual(x['options'][0]['estimated_in_vehicle_minutes'],6)
        self.assertFalse(x['walking_time_included'])

    def test_wrong_direction_no_reverse_same_ride(self):
        x=pub.plan_trip('Sheridan/Haven - Tech (SB)','Emerson/Maple (EB)','2026-10-19T08:00')
        self.assertFalse(any(y['direction']=='Evanston to Chicago' for y in x['options']))

    def test_published_schedule_lookup_never_fetches_live(self):
        with patch.object(shuttle_now,'load_once',side_effect=AssertionError('Live endpoint should not be called')):
            # Patch now so target remains in future whenever test runs.
            x=pub.lookup('Noyes L',ts('2026-10-19T08:00'),ts('2026-10-19T10:00'))
        self.assertTrue(x['arrivals'])
        self.assertTrue(all(y['reported_expected_arrival_local'] is None for y in x['arrivals']))

    def test_server_adds_four_tools(self):
        self.assertTrue(callable(server.list_published_route_stops))
        self.assertTrue(callable(server.plan_scheduled_shuttle_trip))
        self.assertTrue(callable(server.get_scheduled_stops_near))
        self.assertTrue(callable(server.plan_scheduled_trip_to_location))
        self.assertEqual(len(server.list_published_route_stops()['routes']),4)

    def test_unknown_query_not_assert_no_route_exists(self):
        x=pub.lookup('Not A Stop',ts('2026-10-19T08:00'),ts('2026-10-19T09:00'))
        self.assertEqual(x['total_matched'],0)
        self.assertIn('not a live',x['warning'].lower())

if __name__=='__main__': unittest.main(verbosity=2)
