"""Compare two user-initiated `shuttle_now.py --json` outputs; no network requests.

Examples:
  python shuttle_now.py Emerson --json > eta_before.json
  python shuttle_now.py Emerson --json > eta_after.json
  python compare_etas.py eta_before.json eta_after.json
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime
from pathlib import Path


def parse_time(text):
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def compare(before: dict, after: dict) -> dict:
    def index(data):
        return {(r.get('route_group'), r.get('ride_id'), r.get('stop_id')): r
                for r in data.get('arrivals', [])}
    old, new = index(before), index(after)
    output = []
    for key in sorted(old.keys() & new.keys(), key=str):
        a, b = old[key], new[key]
        old_eta = parse_time(a.get('reported_expected_arrival_local'))
        new_eta = parse_time(b.get('reported_expected_arrival_local'))
        old_updated = parse_time(a.get('last_eta_update_local'))
        new_updated = parse_time(b.get('last_eta_update_local'))
        fetch_at = parse_time(b.get('data_fetched_at'))
        delta = int((new_eta - old_eta).total_seconds()) if old_eta and new_eta else None
        freshness_sec = int((fetch_at - new_updated).total_seconds()) if fetch_at and new_updated else None
        output.append({
            'stop_name': b.get('stop_name'), 'route': b.get('route_name'),
            'source_type': b.get('record_type'),
            'expected_before': a.get('reported_expected_arrival_local'),
            'expected_after': b.get('reported_expected_arrival_local'),
            'change_in_expected_seconds': delta,
            'eta_update_advanced': new_updated > old_updated if old_updated and new_updated else None,
            'seconds_between_fetch_and_reported_update': freshness_sec,
            'reported_update_recent_within_180s': (0 <= freshness_sec <= 180 if freshness_sec is not None else None),
            'gps_eta_verified': False,
        })
    return {'matched_rides': len(output), 'rows': output,
            'missing_on_second_lookup': len(old.keys() - new.keys()),
            'new_on_second_lookup': len(new.keys() - old.keys()),
            'warning': 'Changed predictions and recent timestamps do not by themselves establish GPS-derived accuracy.'}


def load_json(path: str) -> dict:
    """Read Python JSON or PowerShell 5.1 redirection output (UTF-8/UTF-16)."""
    raw = Path(path).read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        encoding = "utf-16"
    elif raw.startswith(b"\xef\xbb\xbf"):
        encoding = "utf-8-sig"
    else:
        encoding = "utf-8"
    return json.loads(raw.decode(encoding))


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('before')
    cli.add_argument('after')
    args = cli.parse_args()
    before = load_json(args.before)
    after = load_json(args.after)
    print(json.dumps(compare(before, after), indent=2))


if __name__ == '__main__':
    main()
