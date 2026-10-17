"""Inspect a manually saved TripShot live?day response, locally."""
from __future__ import annotations
import sys, json
from live_groups import overview, arrivals


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data/live_response.json"
    query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Emerson"
    try:
        print("=== LIVE GROUP STRUCTURE (saved snapshot) ===")
        print(json.dumps(overview(path), indent=2))
        print(f"\n=== ARRIVALS MATCHING {query!r} (saved snapshot) ===")
        print(json.dumps(arrivals(query, path), indent=2))
    except Exception as ex:
        print(f"ERROR: {type(ex).__name__}: {ex}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
