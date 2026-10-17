r"""Run: .\.venv\Scripts\python.exe test_limit_guardrails.py
Tests exercise the actual server.py tool functions with mock data (no TripShot calls)."""
import unittest
from unittest.mock import patch
import server

class TestLimits(unittest.TestCase):
    def test_normal(self):
        with patch.object(server, 'get_sources', return_value={'Loop': 'dummy'}), patch.object(server, 'combine_arrivals', return_value={'arrivals': []}) as fn:
            out = server.get_next_shuttles('Emerson', 8)
            self.assertEqual(out['arrivals'], [])
            self.assertEqual(fn.call_args.kwargs['limit'], 8)

    def test_high_capped_with_notice(self):
        with patch.object(server, 'get_sources', return_value={}), patch.object(server, 'combine_arrivals', return_value={'arrivals': []}) as fn:
            out = server.get_next_shuttles('Emerson', 100)
            self.assertEqual(fn.call_args.kwargs['limit'], 20)
            self.assertIn('capped at 20', out['limit_notice'])

    def test_invalid_returns_error(self):
        for value in (0, -1, 'fifty', True):
            with self.subTest(value=value):
                self.assertEqual(server.get_next_shuttles('Emerson', value)['error'], 'invalid_limit')

    def test_invalid_stop_returns_error(self):
        self.assertEqual(server.get_next_shuttles('  ', 8)['error'], 'invalid_stop_query')

    def test_nearby_cap(self):
        with patch.object(server, 'geo_nearby_stops', return_value={'stops': []}) as fn:
            out = server.get_nearby_stops(42.0, -87.0, 30)
            self.assertEqual(fn.call_args.args[-1], 20)
            self.assertIn('limit_notice', out)

if __name__ == '__main__':
    unittest.main(verbosity=2)
