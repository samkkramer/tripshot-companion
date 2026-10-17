import unittest
from unittest.mock import patch
import json
import tempfile
from pathlib import Path
import nearby_stops

class NearbyStopTests(unittest.TestCase):
    def test_zero_distance(self):
        self.assertAlmostEqual(nearby_stops.haversine_m(42.05,-87.68,42.05,-87.68),0.0)
    def test_distance_order(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'stops.json'
            f.write_text(json.dumps([
                {'stop_id':'a','name':'Far','latitude':42.15,'longitude':-87.68},
                {'stop_id':'b','name':'Near','latitude':42.0502,'longitude':-87.68}
            ]),encoding='utf-8')
            with patch.object(nearby_stops,'LOCAL_CATALOG',f):
                r=nearby_stops.find_nearby_stops(42.05,-87.68)
            self.assertEqual(r['stops'][0]['name'],'Near')
            self.assertLess(r['stops'][0]['straight_line_meters'],100)
    def test_bad_coords(self):
        with self.assertRaises(ValueError):
            nearby_stops.find_nearby_stops(142,-87)
    def test_no_catalog(self):
        with patch.object(nearby_stops,'LOCAL_CATALOG',Path('/nonexistent/none.json')):
            self.assertIn('error',nearby_stops.find_nearby_stops(42,-87))
if __name__=='__main__': unittest.main()
