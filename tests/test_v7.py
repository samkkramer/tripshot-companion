import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch

import shuttle_now
from compare_etas import compare

CHI = ZoneInfo('America/Chicago')

class Version7Tests(unittest.TestCase):
    def test_evening_queries_today_and_tomorrow(self):
        self.assertEqual(shuttle_now.service_days_for(datetime(2026, 10, 16, 23, 45, tzinfo=CHI)),
                         ['2026-10-16', '2026-10-17'])
    def test_early_morning_queries_yesterday_and_today(self):
        self.assertEqual(shuttle_now.service_days_for(datetime(2026, 10, 17, 0, 45, tzinfo=CHI)),
                         ['2026-10-16', '2026-10-17'])
    def test_afternoon_only_current_day(self):
        self.assertEqual(shuttle_now.service_days_for(datetime(2026, 10, 17, 13, tzinfo=CHI)),
                         ['2026-10-17'])
    def test_eta_compare(self):
        def fake(expected, updated):
            return {'arrivals':[{'route_group':'Loop','ride_id':'ride1','stop_id':'stop1',
                                 'stop_name':'Emerson','route_name':'Loop','record_type':'ride_in_live_group',
                                 'reported_expected_arrival_local':expected,
                                 'last_eta_update_local':updated,
                                 'data_fetched_at':'2026-10-17T20:01:00-05:00'}]}
        result = compare(fake('2026-10-17T20:06:00-05:00','2026-10-17T20:00:00-05:00'),
                         fake('2026-10-17T20:07:15-05:00','2026-10-17T20:00:45-05:00'))
        self.assertEqual(result['rows'][0]['change_in_expected_seconds'],75)
        self.assertTrue(result['rows'][0]['eta_update_advanced'])
        self.assertFalse(result['rows'][0]['gps_eta_verified'])
    def test_overnight_dedup_and_horizon(self):
        # combine's now() is mocked with a Clock, without actually sending HTTP.
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None): return datetime(2026, 10, 17, 0, 20, tzinfo=CHI)
        upcoming = {'stop_name':'Emerson/Maple','stop_id':'A','direction':'NonDirectional',
                    'ride_id':'ride-16','route_name':'Loop','record_type':'ride_in_live_group',
                    'reported_expected_arrival_local':'2026-10-17T00:35:00-05:00',
                    'scheduled_departure_local':'2026-10-17T00:35:00-05:00'}
        report = {'arrivals':[upcoming], 'rides_examined':1,'matching_stops':[{'name':'Emerson/Maple'}],
                  'fetched_at_local':'2026-10-17T00:20:00-05:00'}
        with patch.object(shuttle_now, 'datetime', Clock):
            with patch.object(shuttle_now, 'load_once', return_value=report) as fn:
                out=shuttle_now.combine('Emerson', {'Loop':'dummy'},limit=8)
        self.assertEqual(fn.call_count, 2)
        self.assertEqual(out['queried_service_days'],['2026-10-16','2026-10-17'])
        self.assertEqual(len(out['arrivals']),1)

if __name__ == '__main__': unittest.main()

# Separate test module class so existing fixture handling stays unchanged.
class DirectionDiagnosticTests(unittest.TestCase):
    def test_summarize_preserves_unknown_direction_without_guessing(self):
        from inspect_route_directions import summarize
        payload={'InternalRouteGroupLiveData':{'exactLiveData':[{'direction':'NonDirectional',
            'liveRides':[{'ride':{'routeName':'Loop Shuttle','routeId':'loop-route','navigationId':'nav123',
                'stopStatus':[{'Awaiting':{'stopId':'A'}},{'Awaiting':{'stopId':'B'}}]}}]}]}}
        names=[{'stop_id':'A','name':'Emerson/Maple (WB)'},{'stop_id':'B','name':'Some later stop'}]
        with patch('inspect_route_directions._read_stops',return_value=names):
            records=summarize(payload)
        self.assertEqual(records[0]['group_direction'],'NonDirectional')
        self.assertEqual([s['name'] for s in records[0]['first_stops_in_order']],['Emerson/Maple (WB)','Some later stop'])
