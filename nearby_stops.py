"""Find geographically nearest imported stops, without network or browser access.
Distances are straight-line estimates, not walking routes.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
from stops_catalog import LOCAL_CATALOG


def find_nearby_stops(latitude: float, longitude: float, limit: int = 5) -> dict:
    if isinstance(latitude, bool) or isinstance(longitude, bool):
        raise ValueError("Provide numeric latitude and longitude")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Invalid latitude or longitude")
    if not 1 <= limit <= 20:
        raise ValueError("limit must be 1..20")
    if not LOCAL_CATALOG.is_file():
        return {"error": "Import stops before finding nearby stops", "hint": "python import_stops.py data\\stops_response.json"}
    raw = json.loads(LOCAL_CATALOG.read_text(encoding="utf-8"))
    results = []
    for stop in raw:
        la,lo=stop.get('latitude'),stop.get('longitude')
        if not isinstance(la,(int,float)) or not isinstance(lo,(int,float)):
            continue
        dist = haversine_m(latitude, longitude, float(la), float(lo))
        results.append({"stop_id":stop['stop_id'],"name":stop['name'],
                        "straight_line_meters":round(dist),
                        "latitude":la, "longitude":lo,
                        "description":stop.get('description')})
    results.sort(key=lambda s:s['straight_line_meters'])
    return {"stops":results[:limit],"count":len(results),
            "method":"haversine_straight_line_not_walking_distance",
            "location_storage":"not stored by this tool",
            "warning":"Closest geographically does not mean the right route or direction. Check route and service."}

def haversine_m(la1:float,lo1:float,la2:float,lo2:float)->float:
    p1,p2=math.radians(la1),math.radians(la2)
    dphi=p2-p1
    dlambda=math.radians(lo2-lo1)
    h=math.sin(dphi/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dlambda/2)**2
    return 6371000*2*math.asin(min(1,math.sqrt(h)))
