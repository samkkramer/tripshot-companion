import unittest
from stops_catalog import parse_stops

class TestStops(unittest.TestCase):
    def test_parse(self):
        data = [{"stopId": "abc", "name": "Emerson/Maple", "location": {"lt": 42.05, "lg": -87.68}}, {"not": "stop"}]
        result = parse_stops(data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Emerson/Maple")
        self.assertEqual(result[0]["longitude"], -87.68)

if __name__ == "__main__":
    unittest.main()
