import unittest
from tripshot_core import get_ride_summary, list_ride_stops, find_stop, get_vehicle_position


class TestCore(unittest.TestCase):
    def test_summary(self):
        result = get_ride_summary()
        self.assertIn("DEMO", result["route_name"])
        self.assertEqual(result["stop_count_in_snapshot"], 2)
        self.assertEqual(result["source"], "MANUAL_LOCAL_JSON_SNAPSHOT")

    def test_stop_times(self):
        result = list_ride_stops()
        self.assertEqual(len(result["stops"]), 2)
        self.assertEqual(result["stops"][0]["stop_name"], "Example Stop A")
        self.assertTrue(result["stops"][0]["expected_time_matches_scheduled_clock"])
        self.assertFalse(result["stops"][1]["expected_time_matches_scheduled_clock"])
        self.assertFalse(result["stops"][1]["prediction_verified_live"])

    def test_stop_lookup(self):
        self.assertEqual(len(find_stop("example stop b")["matches"]), 1)
        self.assertEqual(len(find_stop("not found")["matches"]), 0)

    def test_position(self):
        pos = get_vehicle_position()
        self.assertEqual(pos["latitude"], 41.9)
        self.assertTrue(pos["stale_over_2_minutes"])


if __name__ == "__main__":
    unittest.main()
