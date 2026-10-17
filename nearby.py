"""CLI: python nearby.py 42.052 -87.685 --limit 5"""
from __future__ import annotations
import argparse
import json
from nearby_stops import find_nearby_stops

def main():
    p=argparse.ArgumentParser(description='Nearest TripShot stops from local catalog, straight-line distance')
    p.add_argument('latitude',type=float)
    p.add_argument('longitude',type=float)
    p.add_argument('--limit',type=int,default=5)
    a=p.parse_args()
    print(json.dumps(find_nearby_stops(a.latitude,a.longitude,a.limit),indent=2))
if __name__=='__main__': main()
