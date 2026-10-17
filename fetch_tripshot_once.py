"""Fetch ONE permitted, unauthenticated TripShot JSON response for local analysis.

Usage from TripShot_MCP_Starter_v4 folder:
    python fetch_tripshot_once.py

Paste a Request URL from Chrome DevTools when prompted.

Deliberately:
- only GET to https://northwestern.tripshot.com
- no cookies, tokens, authorization headers or session sharing
- no pagination, loops, retries or polling
- refuses URL query parameters that look like credentials
- writes fetched content only to the local data folder

Use only where your university/vendor authorization permits automated access.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HOST = "northwestern.tripshot.com"
CHICAGO = ZoneInfo("America/Chicago")
MAX_BYTES = 12 * 1024 * 1024
SUSPECT_WORDS = ("token", "secret", "key", "auth", "credential", "signature", "password", "session", "ticket", "jwt", "access")


def validate_url(value: str) -> str:
    value = value.strip()
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname != HOST or parsed.username or parsed.password:
        raise ValueError("URL must use HTTPS and the exact host northwestern.tripshot.com, without embedded credentials.")
    if parsed.port not in (None, 443):
        raise ValueError("Unexpected port; use the normal HTTPS URL.")
    if not parsed.path.startswith("/v2/p/"):
        raise ValueError("This script only accepts a TripShot /v2/p/ data request observed in Chrome.")
    if parsed.fragment:
        raise ValueError("Remove the URL fragment before continuing.")
    for key, val in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        if any(word in key.casefold() for word in SUSPECT_WORDS):
            raise ValueError(f"Query parameter {key!r} could be sensitive. Don't use this URL with the script.")
        if any(word in val.casefold() for word in ("bearer ", "authorization:")):
            raise ValueError("URL contains what looks like a credential; stop and inspect it.")
    return value


class RestrictRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Block redirects rather than sending requests to unexpected hosts.
        raise urllib.error.HTTPError(req.full_url, code, "Redirect blocked to protect URL scope", headers, fp)


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
    opener = urllib.request.build_opener(RestrictRedirects())
    with opener.open(req, timeout=20) as response:
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("JSON response exceeds 12 MB; nothing was saved.")
        content_type = response.headers.get("Content-Type", "")
    try:
        value = json.loads(data.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f"Response was not valid UTF-8 JSON (Content-Type: {content_type}).") from exc
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object. Response was not saved.")
    if "InternalRouteGroupLiveData" not in value and not isinstance(value.get("exactLiveData"), list):
        raise ValueError("Response does not look like the route-group data used by inspect_live.py.")
    return value


def main() -> int:
    print("TripShot single-request test (read-only; no cookies or stored credentials)")
    print("In Chrome DevTools select the 'live?day=...' request, Headers > General > Request URL.")
    print("Do not use URLs containing keys, tokens, credentials, or other secrets.\n")
    url = input("Paste the Request URL here (it stays in this PowerShell session): ")
    try:
        url = validate_url(url)
    except ValueError as exc:
        print(f"URL rejected: {exc}")
        return 2
    print("Sending one GET request from this computer (without your browser session)...")
    try:
        obj = get_json(url)
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: The endpoint may require browser authentication, block direct requests, or disallow this access.")
        print("Do not copy cookies or Authorization headers. Continue using manual browser exports if necessary.")
        return 1
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"Fetch failed: {exc}")
        return 1

    now = datetime.now(CHICAGO)
    folder = Path(__file__).resolve().parent / "data"
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f"live_fetched_{now.strftime('%Y%m%d_%H%M%S')}.json"
    payload = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    # Write atomically to avoid leaving incomplete JSON on errors.
    fd, path = tempfile.mkstemp(prefix=".tripshot_", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        os.replace(path, output)
    finally:
        if os.path.exists(path):
            os.unlink(path)
    print(f"Saved: {output}")
    print(f"Fetched at: {now.isoformat(timespec='seconds')}")
    print(f"Route group ID: {(obj.get('InternalRouteGroupLiveData') or obj).get('sharedRouteId', '(not reported)')}")
    print("This is a one-time response; it does not automatically update or prove GPS-derived ETA freshness.")
    print(f'Now run: python inspect_live.py "{output}" Emerson')
    return 0


if __name__ == "__main__":
    sys.exit(main())
