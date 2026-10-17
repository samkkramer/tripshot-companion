import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import live_groups

ROOT = Path(__file__).resolve().parents[1]


class LiveParserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.stops_file = self.folder / "stops_catalog.local.json"
        self.stops_file.write_text(json.dumps([
            {"stop_id": "demo-stop-001", "name": "DEMO Emerson/Maple", "latitude": 42.0, "longitude": -87.0},
            {"stop_id": "demo-stop-002", "name": "DEMO Hub", "latitude": 42.1, "longitude": -87.1}
        ]), encoding="utf-8")
        self.patch = patch.object(live_groups, "LOCAL_CATALOG", self.stops_file)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_overview(self):
        result = live_groups.overview(ROOT / "data" / "example_live.json")
        self.assertEqual(result["directions"][0]["liveRides_count"], 1)
        self.assertTrue(result["directions"][0]["first_live_ride_has_stopStatus"])

    def test_arrivals(self):
        result = live_groups.arrivals(
            "Emerson", ROOT / "data" / "example_live.json", reference_time_iso="2026-10-16T23:20:00Z"
        )
        self.assertEqual(len(result["arrivals"]), 1)
        self.assertEqual(result["arrivals"][0]["stop_name"], "DEMO Emerson/Maple")
        self.assertEqual(result["arrivals"][0]["reported_expected_arrival_local"], "2026-10-16T18:26:00-05:00")
        self.assertFalse(result["arrivals"][0]["is_verified_gps_prediction"])

    def test_excludes_past(self):
        result = live_groups.arrivals("Emerson", ROOT / "data" / "example_live.json", reference_time_iso="2026-10-16T23:40:00Z")
        self.assertEqual(result["arrivals"], [])

    def test_nested_stop_id_in_state_object(self):
        # Reproduce the real TripShot structure: stopId and clocks are nested.
        fixture = {
            "InternalRouteGroupLiveData": {"sharedRouteId": "DEMO", "exactLiveData": [{
                "direction": "Inbound", "liveTimetable": [[{"sharedStopId": "demo-stop-001"}]],
                "liveRides": [{"ride": {"rideId": "nested", "routeName": "DEMO",
                    "stopStatus": [
                        {"Awaiting": {"stopId": "demo-stop-001", "scheduledAt": "18:25:00", "scheduledDepartureTime": "2026-10-16T23:25:00Z", "expectedArrivalTime": "2026-10-16T23:26:00Z"}},
                        {"Skipped": {"stopId": "demo-stop-002", "scheduledAt": "18:30:00", "scheduledDepartureTime": "2026-10-16T23:30:00Z"}}
                    ]}}], "nonliveRides": [], "liveTrips": []}], "inexactLiveData": []}}
        file = self.folder / "nested.json"
        file.write_text(json.dumps(fixture))
        found = live_groups.arrivals("Emerson", file, reference_time_iso="2026-10-16T23:20:00Z")
        self.assertEqual(len(found["arrivals"]), 1)
        self.assertEqual(found["arrivals"][0]["stop_id"], "demo-stop-001")
        self.assertEqual(found["arrivals"][0]["scheduled_local_clock"], "18:25:00")
        self.assertEqual(found["arrivals"][0]["scheduled_departure_local"], "2026-10-16T18:25:00-05:00")
        self.assertEqual(found["matching_stop_states"]["Awaiting"], 1)

    def test_nested_skipped_not_upcoming(self):
        file = self.folder / "skipped.json"
        file.write_text(json.dumps({"exactLiveData":[{
            "direction":"Inbound","liveRides":[{"ride":{"rideId":"skip1", "stopStatus":[{
              "Skipped":{"stopId":"demo-stop-001", "expectedArrivalTime":"2026-10-16T23:29:00Z"}
            }]}}], "nonliveRides": []}]}))
        out = live_groups.arrivals("Emerson", file, reference_time_iso="2026-10-16T23:20:00Z")
        self.assertEqual(out["arrivals"], [])
        self.assertEqual(out["matching_stop_states"], {"Skipped":1})
        self.assertEqual(out["filtered"]["non_upcoming_state"], 1)

    def test_rejects_unrelated_json(self):
        invalid = self.folder / "bad.json"
        invalid.write_text('{"routes": []}')
        with self.assertRaises(ValueError):
            live_groups.load_live(invalid)


if __name__ == "__main__":
    unittest.main()
