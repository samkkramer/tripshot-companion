"""Conservative single-shot reader for observed public Northwestern TripShot route data.

No authentication headers, cookies, background polling, automatic retries, or writes.
Not an official GTFS integration. Respect provider and university access policies.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, unquote, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from fetch_tripshot_once import validate_url, get_json

CHICAGO = ZoneInfo('America/Chicago')
ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / 'data' / 'sources.local.json'
ALLOWED_NAMES = ('Intercampus', 'Loop')


def verify_route_url(url: str) -> str:
    """Accept only known observed live-route path shape, not arbitrary endpoints."""
    url = validate_url(url)
    urlparts = urlsplit(url)
    path = unquote(urlparts.path)
    if not re.fullmatch(r'/v2/p/shared/route/IRGI:[0-9A-Fa-f-]+/live', path):
        raise ValueError('Expected a /v2/p/shared/route/IRGI:.../live URL captured in Chrome Network.')
    params = parse_qsl(urlparts.query, keep_blank_values=True)
    if [key for key, _ in params].count('day') != 1:
        raise ValueError('Expected exactly one day=YYYY-MM-DD query parameter.')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', dict(params)['day']):
        raise ValueError('day must be in YYYY-MM-DD format.')
    return url


def set_service_day(url: str, day: str) -> str:
    """Update only day parameter, preserving the validated captured URL's other options."""
    url = verify_route_url(url)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
        raise ValueError('Bad service day')
    datetime.strptime(day, '%Y-%m-%d')
    p = urlsplit(url)
    params = [(k, day if k == 'day' else v) for k, v in parse_qsl(p.query, keep_blank_values=True)]
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(params), ''))


def get_sources(path: Path = CONFIG) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError('No saved sources. Run: python configure_sources.py')
    raw = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or not raw:
        raise ValueError('No configured route sources.')
    for name, url in raw.items():
        if name not in ALLOWED_NAMES or not isinstance(url, str):
            raise ValueError('Sources may only be Intercampus and Loop.')
        verify_route_url(url)
    return raw


def fetch_once(url: str, *, day: str):
    verified = set_service_day(url, day)
    return get_json(verified)
