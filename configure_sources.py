"""One-time, local configuration of public route-group URL templates.

No request is made and the config is excluded from Git. Do not enter credentials.
"""
import json
from tripshot_provider import CONFIG, ALLOWED_NAMES, verify_route_url

print('TripShot route setup (nothing is fetched during configuration).')
print('In Chrome > Network > Fetch/XHR, choose the route live?day= request,')
print('then Headers > General > Request URL. Do not copy request headers, cookies, tokens or keys.')
print('Skip a route for now by pressing Enter. Paste its URL later by running setup again.\n')
result = {}
if CONFIG.exists():
    result = json.loads(CONFIG.read_text(encoding='utf-8'))
for route in ALLOWED_NAMES:
    existing = ' [existing URL saved]' if route in result else ''
    value = input(f'{route} URL{existing} (Enter to keep/skip): ').strip()
    if not value:
        continue
    try:
        result[route] = verify_route_url(value)
    except ValueError as exc:
        print(f'Invalid {route} URL: {exc}')
        raise SystemExit(1)
if not result:
    raise SystemExit('No URLs saved.')
CONFIG.parent.mkdir(parents=True, exist_ok=True)
CONFIG.write_text(json.dumps(result, indent=2), encoding='utf-8')
print(f'Configured: {", ".join(result)}')
print('Next: python shuttle_now.py "Emerson/Maple (EB)"')
