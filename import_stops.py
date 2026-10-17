"""Import only the saved JSON RESPONSE body, not a HAR or request headers."""
from __future__ import annotations

import json
import sys
from stops_catalog import import_stop_response, search_stops

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python import_stops.py data\\stops_response.json")
    result = import_stop_response(sys.argv[1])
    print(json.dumps(result, indent=2))
    print("\nEmerson matches:")
    print(json.dumps(search_stops("Emerson"), indent=2))
