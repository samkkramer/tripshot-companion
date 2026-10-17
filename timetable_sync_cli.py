"""Manage official timetable refresh without starting an MCP client.

Usage:
    python timetable_sync_cli.py status
    python timetable_sync_cli.py check
    python timetable_sync_cli.py force
"""
import argparse
import json
from published_full import check_timetable_updates, timetable_status


def main():
    p=argparse.ArgumentParser(description='Check the four Northwestern official shuttle timetable pages')
    p.add_argument('action',choices=['status','check','force'],help='status is offline; check respects 24h throttle; force checks now')
    args=p.parse_args()
    if args.action=='status':
        out=timetable_status()
    else:
        out=check_timetable_updates(force=args.action=='force')
    print(json.dumps(out,indent=2,ensure_ascii=False))
    if out.get('status')=='error':
        print('\nRefresh failed. Existing timetable remains active; see error above.')


if __name__=='__main__':main()
