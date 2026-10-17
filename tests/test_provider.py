import unittest
from unittest.mock import patch
from datetime import datetime

from tripshot_provider import verify_route_url, set_service_day
import shuttle_now

GOOD = 'https://northwestern.tripshot.com/v2/p/shared/route/IRGI:2CA5DC76-DD3F-4AB4-BD10-056785A989ED/live?day=2026-10-16&includePreviousDayRidesSpanningMidnight=true'

class ProviderTests(unittest.TestCase):
    def test_replace_only_day(self):
        self.assertIn('day=2026-10-17', set_service_day(GOOD, '2026-10-17'))
        self.assertIn('includePreviousDayRidesSpanningMidnight=true', set_service_day(GOOD, '2026-10-17'))
    def test_bad_host(self):
        with self.assertRaises(ValueError): verify_route_url(GOOD.replace('northwestern.tripshot.com', 'phish.example'))
    def test_reject_credentials(self):
        with self.assertRaises(ValueError): verify_route_url(GOOD+'&api_key=secret')
    def test_only_one_day(self):
        with self.assertRaises(ValueError): verify_route_url(GOOD+'&day=2026-10-16')
    def test_avoid_wrong_path(self):
        with self.assertRaises(ValueError): verify_route_url('https://northwestern.tripshot.com/v1/whoami?day=2026-10-16')
    def test_one_shot_sanitized_output(self):
        fake = {'InternalRouteGroupLiveData': {'sharedRouteId':'IRGI:demo','exactLiveData': [],'inexactLiveData':[]}}
        with patch.object(shuttle_now,'fetch_once',return_value=fake):
            with patch.object(shuttle_now, 'arrivals', return_value={'arrivals':[], 'rides_examined':0,'matching_stops':[]}):
                report = shuttle_now.load_once('Emerson','Intercampus',GOOD,'2026-10-16')
        self.assertEqual(report['source'], 'ONE_TIME_UNAUTHENTICATED_HTTP_FETCH')
        self.assertEqual(report['arrivals'],[])
        self.assertIn('fetched_at_local',report)

if __name__ == '__main__': unittest.main()
