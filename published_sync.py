"""Safe, on-demand refresh of Northwestern's OFFICIAL published timetable tables.

No polling daemon. No TripShot requests or secrets. Only fixed Northwestern URLs.
Unknown/changed HTML formats fail closed; last-known-good data remain intact.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent / 'data'
ACTIVE = ROOT / 'published_timetables.active.json'
STATUS = ROOT / 'published_timetables.status.json'
HISTORY = ROOT / 'published_timetables.history'
CHECK_HOURS = 24
ERROR_RETRY_HOURS = 2
MAX_DOCUMENT_BYTES = 2_000_000

ROUTE_LABELS = (
    'Loop Clockwise', 'Loop Counterclockwise',
    'Intercampus Evanston to Chicago', 'Intercampus Chicago to Evanston'
)


class TimetableFormatError(ValueError):
    pass


class _Tables(HTMLParser):
    """Collect HTML table cells, ignoring unrelated page/sidebar HTML."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.table_depth = 0
        self.table = None
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            if self.table_depth == 0:
                self.table = []
            self.table_depth += 1
        elif self.table_depth == 1 and tag == 'tr':
            self.row = []
        elif self.table_depth == 1 and tag in ('td', 'th') and self.row is not None:
            self.cell = []
        elif tag in ('br', 'hr') and self.cell is not None:
            self.cell.append(' ')

    def handle_endtag(self, tag):
        if self.table_depth == 1 and tag in ('td', 'th') and self.cell is not None:
            text = re.sub(r'\s+', ' ', ''.join(self.cell)).strip()
            self.row.append(text)
            self.cell = None
        elif self.table_depth == 1 and tag == 'tr' and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == 'table' and self.table_depth:
            self.table_depth -= 1
            if self.table_depth == 0 and self.table is not None:
                self.tables.append(self.table)
                self.table = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def _norm(s):
    s = str(s).lower().replace('\xa0',' ')
    s = re.sub(r'\b(ave|avenue)\b', '', s)
    s = re.sub(r'\b(depart|arrive)\b', '', s)
    s = re.sub(r'[^a-z0-9]', '', s)
    return s.replace('shermanemersonnb', 'shermanemersonib')


def _label_compatible(got, expected):
    a, b = _norm(got), _norm(expected)
    if a == b or (a and b and (a in b or b in a)):
        return True
    alias_pairs = (
        ('librarynorriscenter','librarynorris'),
        ('lincolnaveelderhalleb','elderhalllincolneb'),
        ('ridgeciviccentersb','ridgeaveciviccentersb'),
        ('shermanemersonnb','shermanemersonib'),
        ('centrallevanstoneb','centralleb'),
    )
    for x, y in alias_pairs:
        ax, ay = _norm(x), _norm(y)
        if {a,b} == {ax,ay}:
            return True
    return False


_AMPM_TIME = re.compile(r'(?<!\w)(1[0-2]|0?[1-9]):([0-5]\d)\s*([ap])\.?m\.?(?!\w)', re.I)
_MINUTE = re.compile(r'(?<!\d):([0-5]\d)(?!\d)')


def _clock_codes(text):
    out=[]
    for m in _AMPM_TIME.finditer(text):
        h,minute,period=int(m[1]),int(m[2]),m[3].lower()
        h=(h%12)+(12 if period=='p' else 0)
        out.append(f'{h:02d}{minute:02d}')
    return out


def _find_rows(html, expected_stops, *, mode):
    doc = _Tables()
    doc.feed(html)
    candidates=[]
    for table in doc.tables:
        recorded=[]
        for row in table:
            if not row:
                continue
            name=row[0]
            details=' '.join(row[1:])
            # A very long university table may split a stop across rows.
            if not name and recorded and details:
                prev_name,prev_text=recorded[-1]
                recorded[-1]=(prev_name,prev_text+' '+details)
            else:
                recorded.append((name,details))
        picked=[]
        for name,values in recorded:
            if not name:
                continue
            for expected in expected_stops:
                if _label_compatible(name,expected):
                    picked.append((name,values))
                    break
        if picked:
            candidates.append((len(picked),len(recorded),recorded,picked))
    if not candidates:
        raise TimetableFormatError('No recognized Northwestern timetable table found (page may have changed format).')
    _, _, all_rows, matched=max(candidates,key=lambda c:c[0])
    # Fail closed on added/reordered stops. Silently dropping them could
    # make boarding/alighting recommendations incorrect.
    if len(matched) != len(expected_stops):
        raise TimetableFormatError(f'Expected {len(expected_stops)} stops; found {len(matched)}. Manual review required.')
    for i,((source_name,values),expected) in enumerate(zip(matched,expected_stops)):
        if not _label_compatible(source_name,expected):
            raise TimetableFormatError(f'Stop order/name changed at {i+1}: {source_name!r} vs {expected!r}.')
    # Reject newly added/renamed stops; ignoring them would silently
    # omit valid boarding locations and distort journey recommendations.
    for source_name, raw in all_rows:
        if not source_name:
            continue
        time_count=(len(_MINUTE.findall(raw)) if mode=='loop'
                    else len(_clock_codes(raw)))
        if time_count >= (2 if mode=='loop' else 5) and not any(
               _label_compatible(source_name,known) for known in expected_stops):
            raise TimetableFormatError(f'New or renamed time-bearing stop {source_name!r}; manual review required.')
    if mode=='loop':
        rows=[]
        for name,raw in matched:
            mins=[int(x) for x in _MINUTE.findall(raw)]
            if len(mins)!=2:
                raise TimetableFormatError(f'Expected 2 Loop passing minutes at {name!r}, got {mins!r}.')
            rows.append(mins)
        return rows
    rows=[]
    for name,raw in matched:
        times=_clock_codes(raw)
        if len(times) < 5 or len(times)>80:
            raise TimetableFormatError(f'Unexpected number of timetable columns at {name!r}: {len(times)}.')
        rows.append(times)
    widths={len(row) for row in rows}
    if len(widths) != 1:
        raise TimetableFormatError(f'Inconsistent Intercampus trip counts across rows: {sorted(widths)}.')
    # A single trip must move forward in local time as it visits stops.
    for col in range(len(rows[0])):
        mins=[int(row[col][:2])*60+int(row[col][2:]) for row in rows]
        if any(y<x for x,y in zip(mins,mins[1:])) or mins[-1]-mins[0]>240:
            raise TimetableFormatError(f'Invalid stop-to-stop time sequence in trip column {col+1}.')
    return rows


def parse_four_pages(pages, base):
    """Produce a fully validated replacement. No network access or disk writes."""
    if set(pages) != set(ROUTE_LABELS) or set(base) != set(ROUTE_LABELS):
        raise TimetableFormatError('Must provide all four supported route-direction tables.')
    proposed={}
    for label in ROUTE_LABELS:
        original=base[label]
        stops=original['stops']
        if label.startswith('Loop'):
            parsed=_find_rows(pages[label], stops, mode='loop')
            departure_minute=15 if label=='Loop Clockwise' else 0
            offsets=[]
            for a,b in parsed:
                off=(a-departure_minute)%60
                expected_second=(departure_minute+off+30)%60
                if b!=expected_second or off>50:
                    raise TimetableFormatError(f'Inconsistent Loop intervals/offset for {label}: {a}, {b}.')
                offsets.append(off)
            if offsets[0]!=0 or any(b<a for a,b in zip(offsets,offsets[1:])):
                raise TimetableFormatError(f'Invalid stop order or offsets for {label}.')
            proposed[label]={'stops':stops,'offsets_minutes':offsets}
        else:
            rows=_find_rows(pages[label],stops,mode='intercampus')
            proposed[label]={'stops':stops,'rows_hhmm':rows}
    return proposed


def signature(routes):
    canonical=json.dumps(routes,sort_keys=True,separators=(',',':'),ensure_ascii=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _json(path, default=None):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeError,ValueError,OSError):
        return default


def load_active():
    data=_json(ACTIVE)
    if not isinstance(data,dict) or data.get('schema')!=1:
        return None
    routes=data.get('routes')
    if not isinstance(routes,dict) or set(routes)!=set(ROUTE_LABELS):
        return None
    if data.get('revision')!=signature(routes):
        return None
    return data


def get_status():
    return _json(STATUS,{})


def _atomic_write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,
                                         prefix=path.name+'.',suffix='.tmp',delete=False) as f:
            tmp=Path(f.name)
            json.dump(data,f,indent=2,ensure_ascii=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if tmp and tmp.exists():
            tmp.unlink(missing_ok=True)


def _fetch_exact_url(url):
    p=urlparse(url)
    if p.scheme!='https' or p.hostname not in ('www.northwestern.edu','northwestern.edu') or \
       not p.path.startswith('/transportation-parking/shuttles/routes/schedules/'):
        raise ValueError('URL not in fixed Northwestern schedule allowlist.')
    req=Request(url,headers={'User-Agent':'TripShotCompanion/1.0 (personal timetable check)',
                             'Accept':'text/html'})
    with urlopen(req,timeout=8) as resp:
        effective=urlparse(resp.geturl())
        if effective.scheme!='https' or effective.hostname not in ('northwestern.edu','www.northwestern.edu'):
            raise ValueError('Unexpected redirect outside Northwestern.')
        data=resp.read(MAX_DOCUMENT_BYTES+1)
        if len(data)>MAX_DOCUMENT_BYTES:
            raise ValueError('Schedule page exceeded maximum response size.')
        charset=resp.headers.get_content_charset() or 'utf-8'
        return data.decode(charset,errors='replace')


def _differences(old,new):
    changed=[]
    for label in ROUTE_LABELS:
        a,b=old[label],new[label]
        field='offsets_minutes' if label.startswith('Loop') else 'rows_hhmm'
        before,after=a[field],b[field]
        if before==after:continue
        cells=[]
        for i,stop in enumerate(a['stops']):
            aa,bb=before[i],after[i]
            if isinstance(aa,int):
                if aa!=bb:cells.append({'stop':stop,'old_offset_minutes':aa,'new_offset_minutes':bb})
            else:
                for j in range(max(len(aa),len(bb))):
                    x=aa[j] if j<len(aa) else None
                    y=bb[j] if j<len(bb) else None
                    if x!=y:cells.append({'stop':stop,'trip_column':j+1,'old_hhmm':x,'new_hhmm':y})
        changed.append({'route':label,'changed_cells':len(cells),'examples':cells[:15]})
    return changed


def _utcnow():
    return datetime.now(timezone.utc)


def _due(status,now,force):
    if force:return True
    stamp=status.get('checked_at_utc')
    if not stamp:return True
    try:age=now-datetime.fromisoformat(stamp)
    except ValueError:return True
    interval=ERROR_RETRY_HOURS if status.get('status')=='error' else CHECK_HOURS
    return age>=timedelta(hours=interval)


def check_updates(base, urls, *, force=False, now=None, fetcher=None):
    """Check pages only on user-invoked operations and at most daily.

    When the website cannot be fetched or validated, no active timetable is
    replaced and a diagnostic status is saved. Test with an injected fetcher.
    """
    now=now or _utcnow()
    status=get_status()
    active=load_active()
    current=(active or {'routes':base})['routes']
    if not _due(status,now,force):
        return {'status':'not_due','checked_at_utc':status.get('checked_at_utc'),
                'revision':signature(current),'last_check':status.get('status'),
                'last_error':status.get('error'), 'source':'validated_local_snapshot' if active else 'bundled_fallback'}
    fetcher=fetcher or _fetch_exact_url
    try:
        if set(urls)!=set(ROUTE_LABELS):raise ValueError('Invalid route URL set.')
        pages={name:fetcher(urls[name]) for name in ROUTE_LABELS}
        new=parse_four_pages(pages,base)
        new_hash=signature(new)
        old_hash=signature(current)
        diff=_differences(current,new)
        if new_hash!=old_hash:
            if active:
                HISTORY.mkdir(parents=True,exist_ok=True)
                # Historical versions provide an easy manual rollback.
                _atomic_write(HISTORY / (active['revision']+'.json'),active)
            record={'schema':1,'revision':new_hash,'retrieved_at_utc':now.isoformat(),
                    'routes':new,'source_urls':urls,'supersedes_revision':old_hash}
            _atomic_write(ACTIVE,record)
            result='updated'
        else:
            result='unchanged'
        state={'checked_at_utc':now.isoformat(),'status':result,'revision':new_hash,
               'changes':diff, 'error':None}
        _atomic_write(STATUS,state)
        return {**state,'source':'validated_local_snapshot' if load_active() else 'bundled_fallback'}
    except Exception as exc:
        state={'checked_at_utc':now.isoformat(),'status':'error','revision':signature(current),
               'error':f'{type(exc).__name__}: {exc}', 'changes':[]}
        _atomic_write(STATUS,state)
        return {**state,'source':'validated_local_snapshot' if active else 'bundled_fallback',
                'warning':'Schedule refresh failed; the previous validated schedule remains in use.'}
