"""Offline published timetable explorer; reads no secrets or live APIs.

Examples:
  python published_schedule_cli.py routes
  python published_schedule_cli.py departures "Central L" 2026-10-19T08:15
  python published_schedule_cli.py trip "Emerson/Maple (EB)" "Sheridan/Haven - Tech (SB)" 2026-10-19T08:00
  python published_schedule_cli.py nearby 42.0520 -87.6850
  python published_schedule_cli.py to-location "Emerson/Maple (EB)" 42.057 -87.677 2026-10-19T08:00
"""
import argparse
import json
from datetime import datetime, timedelta
from tripshot_provider import CHICAGO
from published_full import route_stops, lookup, plan_trip, served_stops_near, plan_to_coordinates


def output(value):
    print(json.dumps(value,indent=2,ensure_ascii=False))


def main():
    p=argparse.ArgumentParser(description='All Northwestern 2026-27 published shuttle stops and times (not live)')
    subs=p.add_subparsers(dest='action',required=True)
    subs.add_parser('routes')
    q=subs.add_parser('departures'); q.add_argument('stop');q.add_argument('when_local'); q.add_argument('--before',type=int,default=30);q.add_argument('--after',type=int,default=90)
    q=subs.add_parser('trip'); q.add_argument('from_stop');q.add_argument('to_stop');q.add_argument('when_local')
    q=subs.add_parser('nearby');q.add_argument('latitude',type=float);q.add_argument('longitude',type=float)
    q=subs.add_parser('to-location');q.add_argument('from_stop');q.add_argument('latitude',type=float);q.add_argument('longitude',type=float);q.add_argument('when_local')
    a=p.parse_args()
    if a.action=='routes': return output({'routes':route_stops()})
    if a.action=='departures':
        at=datetime.fromisoformat(a.when_local)
        at=at.replace(tzinfo=CHICAGO) if at.tzinfo is None else at.astimezone(CHICAGO)
        return output(lookup(a.stop,at-timedelta(minutes=a.before),at+timedelta(minutes=a.after)))
    if a.action=='trip':return output(plan_trip(a.from_stop,a.to_stop,a.when_local))
    if a.action=='nearby':return output(served_stops_near(a.latitude,a.longitude))
    if a.action=='to-location':return output(plan_to_coordinates(a.from_stop,a.latitude,a.longitude,a.when_local))

if __name__=='__main__':main()
