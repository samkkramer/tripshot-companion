"""Run offline demo with Python's standard library (no MCP install required)."""
import json
from tripshot_core import get_ride_summary, list_ride_stops, get_vehicle_position, find_stop

if __name__ == "__main__":
    for name, result in (
        ("Ride summary", get_ride_summary()),
        ("Stop list", list_ride_stops()),
        ("Stop lookup", find_stop("Example Stop")),
        ("Vehicle position", get_vehicle_position()),
    ):
        print(f"\n--- {name} ---")
        print(json.dumps(result, indent=2))
