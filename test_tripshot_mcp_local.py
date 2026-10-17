r"""Smoke-test TripShot MCP over REAL local stdio transport (MCP Python SDK v2).

Place this file beside server.py in TripShot_MCP_Starter_v6 (after the v7 patch).
Run with the SAME Python interpreter/virtual environment that installed mcp:
    .\.venv\Scripts\python.exe test_tripshot_mcp_local.py

No external network calls: invokes the bundled synthetic ride fixture.
The script launches and terminates its own server subprocess.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys

from mcp import Client, StdioServerParameters
from mcp.types import TextContent


async def main() -> None:
    project = Path(__file__).resolve().parent
    server_file = project / "server.py"
    if not server_file.is_file():
        raise SystemExit("ERROR: Put this script in the same folder as server.py")

    print(f"Using Python: {sys.executable}")
    print(f"Server: {server_file}")
    print("Connecting to a newly launched LOCAL stdio MCP server ...")

    env = os.environ.copy()
    env['TRIPSHOT_DISABLE_SCHEDULE_REFRESH'] = '1'
    env['TRIPSHOT_JSON_PATH'] = str(project / 'data' / 'example_ride.json')
    env['TRIPSHOT_STOP_NAMES_PATH'] = str(project / 'data' / 'stop_names.example.json')
    server = StdioServerParameters(
        command=sys.executable,
        args=["-u", str(server_file)],
        env=env,
    )
    async with Client(server) as client:
        print(f"Connected. MCP protocol: {client.protocol_version}")
        listed = await client.list_tools()
        names = {tool.name for tool in listed.tools}
        print(f"Discovered {len(names)} MCP tools:")
        for tool in listed.tools:
            print(f"  - {tool.name}")

        expected = {
            'get_ride_summary', 'list_ride_stops', 'find_stop', 'search_all_stops',
            'get_vehicle_position', 'inspect_saved_route_group',
            'find_saved_upcoming_arrivals', 'get_next_shuttles',
            'get_shuttles_at_time', 'get_nearby_stops', 'list_published_route_stops',
            'plan_scheduled_shuttle_trip', 'get_scheduled_stops_near',
            'plan_scheduled_trip_to_location', 'refresh_published_timetables',
            'get_published_timetable_status',
        }
        if names != expected:
            raise RuntimeError(f'Tool inventory changed: missing={expected-names}, added={names-expected}')

        target = "get_ride_summary"

        print("\nCalling get_ride_summary() against the synthetic fixture ...")
        response = await client.call_tool(target, {})
        if response.is_error:
            for block in response.content:
                if isinstance(block, TextContent):
                    print(block.text)
            raise RuntimeError("MCP tool invocation returned an error.")
        import json
        payload = response.structured_content
        if payload is None:
            payload = json.loads(next(b.text for b in response.content if isinstance(b, TextContent)))
        if payload.get('stop_count_in_snapshot') != 2 or 'DEMO' not in payload.get('route_name', ''):
            raise RuntimeError('Tool did not return the expected synthetic ride summary.')
        print("SUCCESS: MCP tool call returned without error.")
        if response.structured_content is not None:
            import json
            print(json.dumps(response.structured_content, indent=2, default=str)[:3500])
        else:
            for block in response.content:
                if isinstance(block, TextContent):
                    print(block.text[:3500])

    print("\nPASS: Local MCP handshake + discovery + read-only tool invocation.")
    print("This is a LOCAL test only. No ChatGPT tunnel is connected yet.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
