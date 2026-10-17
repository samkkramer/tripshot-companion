# TripShot Starter v7 — local improvements

This is a local read-only prototype. It is **not** a hosted ChatGPT MCP server, does **not** verify GPS-based ETAs, and is not an official TripShot client. Use in accordance with Northwestern and TripShot policies.

## Quick upgrade from v6 (without reinstalls)

The **v6-to-v7 patch ZIP** is easiest. Unzip it, and copy its source files into your existing `TripShot_MCP_Starter_v6` folder, replacing `server.py` and `shuttle_now.py` when prompted. Copy the included `tests/test_v7.py` into that project's `tests` folder. Keep your existing `.venv` and `data/sources.local.json` and `data/stops_catalog.local.json` untouched. **Do not delete them.**

Run in that same v6 folder:

```powershell
python -m unittest discover -s tests -v
python shuttle_now.py Emerson
.\.venv\Scripts\python.exe server.py
```

If `server.py` starts silently instead of throwing a traceback, use Ctrl+C to stop it. It must be connected to a local stdio MCP client to actually test a tool call. This does **not** connect ChatGPT.

## Direction analysis — no guessing CW versus CCW

TripShot Loop rides may be `NonDirectional` and a stop may be called `Emerson/Maple (WB)`. Those values do not by themselves establish a clockwise or counterclockwise route. Compare the **ordered stop sequence** and `routeId`/`navigationId` values with Northwestern's published route map.

```powershell
python inspect_route_directions.py Loop > directions.txt
```

This sends a single read-only request for today's configured Loop route, then prints up to four live rides, their route signature and up to twelve named stops each. It omits vehicle/driver IDs and passenger counts. If no active rides are available, run it while the route operates. Don't label a signature CW/CCW until its direction is independently confirmed.

## ETA observation comparison — not proof of GPS accuracy

Run these commands at two separate times that you choose. Each `shuttle_now.py` command makes one request per configured route (near midnight it can make two per route):

```powershell
python shuttle_now.py Emerson --json > eta_before.json
python shuttle_now.py Emerson --json > eta_after.json
python compare_etas.py eta_before.json eta_after.json > eta_comparison.txt
```

This compares matching `route_group + rideId + stopId` values and flags changed reported arrival times, changed `lastEtaUpdate` timestamps, and how recent each reported update is. A recent timestamp or moving ETA **does not prove** that a prediction is GPS-derived or accurate. Compare a few results with TripShot's displayed arrivals and actual observed arrivals before trusting them for a departure decision.

## Overnight queries

`shuttle_now.py` queries the current Chicago service date normally; at 10 PM–midnight it queries **today and tomorrow**, and from midnight–3 AM it queries **yesterday and today**. It deduplicates equivalent stop/ride/time records across both responses and limits returned results to a four-hour lookahead. This is a conservative *provisional* approach: TripShot's internal service-day semantics and DST edge cases haven't been independently validated. The server is still one-shot and does not poll continuously.

The parser assumes the `sources.local.json` URLs are read-only route-group URLs with `day=...` parameters; it updates only that parameter and preserves `includePreviousDayRidesSpanningMidnight=true` when present. No authentication secrets are stored or used.

## Known limitations

- No hosted HTTPS MCP/OAuth connection yet.
- No guaranteed GPS ETA accuracy; `liveRides` is not equivalent to a GPS-verified ETA.
- Loop clockwise/counterclockwise mapping must be established from route sequence or a route metadata source.
- Overnight duplicate handling has offline tests but needs a real after-midnight test.
- Some routes/stops may be absent or have stale data on a given run; an empty response does not prove a route is not operating.
