"""Versioned announcement cache, health, and pure applicability evaluation.

One atomic manifest pins last-known-good notices and refresh health. OS file
locks serialize MCP/CLI processes. No background job or TripShot request.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import copy
from datetime import datetime, timedelta, timezone
from functools import wraps
import json
import os
from pathlib import Path
import re
import tempfile

from service_updates_source import SOURCE_URL, PageResponse, fetch_page
from service_updates_parser import PARSER_VERSION, digest, parse_page, CHICAGO

CACHE_DIR=Path(__file__).resolve().parent/'data'/'service_updates'
PINNED=ContextVar('service_updates_snapshot',default=None)
SUCCESS_TTL=timedelta(minutes=15)
WARNING='Published notices are incomplete evidence of operation. No announcement or failed refresh confirms normal service.'


def utcnow():return datetime.now(timezone.utc)


def stamp(value):
    if not isinstance(value,str):return None
    try:
        dt=datetime.fromisoformat(value.replace('Z','+00:00'))
        return dt if dt.tzinfo else None
    except ValueError:return None


def _notice_valid(n):
    if not isinstance(n,dict):return False
    if n.get('schema')!=1 or not all(isinstance(n.get(k),str) for k in
            ('id','revision','heading','evidence','source_url','lifecycle','parser_version')):return False
    if n['source_url']!=SOURCE_URL:return False
    if type(n.get('withdrawn')) is not bool or n['lifecycle'] not in ('present','removed_unconfirmed'):return False
    if not all(re.fullmatch(r'[0-9a-f]{64}',n[k]) for k in ('id','revision')):return False
    if not all(stamp(n.get(k)) is not None for k in ('first_seen_at','last_seen_at')):return False
    if not all(isinstance(n.get(k),list) for k in ('routes','directions','effects','windows','warnings')):return False
    if not all(isinstance(x,str) for k in ('routes','directions','warnings') for x in n[k]):return False
    for effect in n['effects']:
        if not isinstance(effect,dict) or type(effect.get('certain')) is not bool or not isinstance(effect.get('evidence'),str):return False
        if not isinstance(effect.get('type'),str) or not all(isinstance(effect.get(k),list)
                                                         for k in ('stop_families','directions')):return False
        if not all(isinstance(x,str) for k in ('stop_families','directions') for x in effect[k]):return False
    for w in n['windows']:
        if not isinstance(w,dict) or stamp(w.get('start')) is None:return False
        if w.get('end') is not None and (stamp(w['end']) is None or stamp(w['end'])<=stamp(w['start'])):return False
        if type(w.get('end_inclusive')) is not bool:return False
    return True


def _active_valid(a):
    return (isinstance(a,dict) and isinstance(a.get('notices'),list) and
            all(_notice_valid(n) for n in a['notices']) and stamp(a.get('last_success_at')) is not None and
            a.get('checksum')==digest(a['notices']) and a.get('revision')==digest([
                {k:v for k,v in n.items() if k not in ('first_seen_at','last_seen_at')}
                for n in a['notices']]) and isinstance(a.get('parser_version'),str))


def _read(path):
    try:
        if path.stat().st_size>5_000_000:return None
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError,UnicodeError):return None


def load_manifest(root=None):
    root=Path(root or CACHE_DIR)
    data=_read(root/'current.json')
    if isinstance(data,dict) and data.get('schema')==1 and isinstance(data.get('health'),dict):
        if data.get('active') is None or _active_valid(data['active']):return data
    # A corrupt manifest is not a fresh verification. Recover a coherent history.
    try:paths=sorted((root/'history').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    except OSError:paths=[]
    for path in paths:
        old=_read(path)
        if isinstance(old,dict) and _active_valid(old.get('active')):
            return {**old,'health':{'status':'error','error':'Recovered validated history after malformed cache',
                                   'checked_at':None,'failure_count':0}}
    return {'schema':1,'active':None,'health':{'status':'not_checked','failure_count':0}}


def _atomic_write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,suffix='.tmp',delete=False) as f:
            temp=Path(f.name);json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
            f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if temp:temp.unlink(missing_ok=True)


@contextmanager
def cache_lock(root):
    root.mkdir(parents=True,exist_ok=True)
    with (root/'refresh.lock').open('a+b') as handle:
        handle.seek(0,2)
        if not handle.tell():handle.write(b'0');handle.flush()
        handle.seek(0);locked=False
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            locked=True
        except OSError:pass
        try:yield locked
        finally:
            if locked:
                handle.seek(0)
                if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
                else:fcntl.flock(handle,fcntl.LOCK_UN)


def view(manifest,*,now=None):
    now=now or utcnow()
    active=manifest.get('active');health=manifest.get('health',{})
    checked=stamp(health.get('checked_at'));last=stamp((active or {}).get('last_success_at'))
    verified=bool(active and active.get('parser_version')==PARSER_VERSION and checked and
                  timedelta(0)<=now-checked<SUCCESS_TTL and health.get('status')=='success')
    needs_review=bool(active and any(n['warnings'] or n['lifecycle']=='removed_unconfirmed' for n in active['notices']))
    status=('parse_review_required' if verified and needs_review else 'fresh') if verified else (
        'stale' if active else ('not_checked' if health.get('status')=='not_checked' else 'unavailable'))
    return {'service_updates_status':status,'service_updates_checked_at':health.get('checked_at'),
            'service_updates_last_success_at':last.isoformat() if last else None,
            'service_updates_revision':(active or {}).get('revision'),
            'service_updates_age_seconds':max(0,int((now-last).total_seconds())) if last else None,
            'service_updates_error':health.get('error'),
            'service_updates_next_retry_at':health.get('next_retry_at'),
            'service_updates_source_url':SOURCE_URL,'service_updates_warning':WARNING,
            'normal_service_confirmed':False,
            'notices':copy.deepcopy((active or {}).get('notices',[]))}


def refresh(*,force=False,root=None,now=None,fetcher=None,reviewed_years=None):
    if type(force) is not bool:raise ValueError('force must be boolean')
    root=Path(root or CACHE_DIR);now=now or utcnow()
    if now.tzinfo is None:raise ValueError('Refresh clock must be timezone-aware')
    previous=load_manifest(root)
    try:
        with cache_lock(root) as locked:
            if not locked:
                out=view(previous,now=now);out['refresh_status']='in_progress';return out
            previous=load_manifest(root)
            active=previous['active'];health=previous['health']
            retry=stamp(health.get('next_retry_at'))
            compatible=active and active.get('parser_version')==PARSER_VERSION
            if not force and (compatible or active is None) and retry and now<retry:
                out=view(previous,now=now);out['refresh_status']='not_due';return out
            try:
                response=(fetcher or fetch_page)(etag=active.get('etag') if compatible else None,
                              last_modified=active.get('last_modified') if compatible else None)
                if not isinstance(response,PageResponse):raise ValueError('Invalid fetch response')
                if response.status==304:
                    if not compatible:raise ValueError('304 without compatible validated cache')
                    candidate=copy.deepcopy(active)
                    result='unchanged'
                elif response.status==200:
                    parsed=parse_page(response.html,reviewed_years=reviewed_years)
                    old={n['id']:n for n in (active or {}).get('notices',[])}
                    notices=[]
                    for notice in parsed['notices']:
                        prior=old.pop(notice['id'],None)
                        notice.update({'first_seen_at':prior['first_seen_at'] if prior else now.isoformat(),
                                       'last_seen_at':now.isoformat(),
                                       'supersedes_revision':prior['revision'] if prior and prior['revision']!=notice['revision'] else
                                           (prior or {}).get('supersedes_revision')})
                        # last_seen is metadata; exclude it from the content revision below.
                        notices.append(notice)
                    removed=[{**n,'lifecycle':'removed_unconfirmed'} for n in old.values() if not n.get('withdrawn')]
                    # Complete disappearance of several notices can be a broken page/template.
                    if len(removed)>=3 and not notices:raise ValueError('Suspicious mass notice removal')
                    notices.extend(removed)
                    for n in notices:
                        candidates=[o['id'] for o in removed if o['routes']==n['routes'] and o['id']!=n['id']]
                        if n['lifecycle']=='present' and candidates:n['possible_replacements']=candidates
                    candidate={**parsed,'notices':notices,'etag':response.etag,'last_modified':response.last_modified,
                               'effective_url':response.effective_url,'source_url':SOURCE_URL}
                    result='updated' if not active or parsed['section_hash']!=active.get('section_hash') else 'unchanged'
                else:raise ValueError('Unexpected HTTP response')
                candidate['last_success_at']=now.isoformat()
                # Stable revision: time-only metadata updates do not create changes.
                stable=[{k:v for k,v in n.items() if k not in ('first_seen_at','last_seen_at')}
                        for n in candidate['notices']]
                candidate['revision']=digest(stable)
                # Full-record checksum guards metadata separately from semantic revision.
                candidate['checksum']=digest(candidate['notices'])
                if not _active_valid(candidate):raise ValueError('Invalid candidate notice model')
                state={'schema':1,'active':candidate,'health':{'status':'success','error':None,
                    'checked_at':now.isoformat(),'failure_count':0,'next_retry_at':(now+SUCCESS_TTL).isoformat()}}
                if active and active['revision']!=candidate['revision']:
                    key=digest(previous)
                    _atomic_write(root/'history'/f'{key}.json',previous)
                _atomic_write(root/'current.json',state)
                _prune_history(root,now)
                out=view(state,now=now);out['refresh_status']=result;return out
            except Exception as exc:
                # Do not serialize arbitrary error strings/URLs/headers from a remote response.
                count=health.get('failure_count',0)
                count=count if type(count) is int and 0<=count<=100 else 0
                count+=1;minutes=min(60,5*2**min(count-1,4))
                state={'schema':1,'active':active,'health':{'status':'error','error':type(exc).__name__,
                    'checked_at':now.isoformat(),'failure_count':count,
                    'next_retry_at':(now+timedelta(minutes=minutes)).isoformat()}}
                try:_atomic_write(root/'current.json',state)
                except OSError:state['health']['error']='CacheWriteError'
                out=view(state,now=now);out['refresh_status']='error';return out
    except OSError:
        previous['health']={**previous['health'],'status':'error','error':'CacheLockError'}
        out=view(previous,now=now);out['refresh_status']='error';return out


def snapshot(*,auto_refresh=True):
    existing=PINNED.get()
    if existing is not None:return existing
    if auto_refresh and os.getenv('TRIPSHOT_DISABLE_SERVICE_REFRESH')!='1':return refresh()
    return view(load_manifest())


def _prune_history(root,now):
    """Best-effort retention only for cache-created, hash-named history files."""
    history=(root/'history').resolve()
    if not history.is_relative_to(root.resolve()):return
    try:
        for p in history.glob('*.json'):
            if (p.parent.resolve()==history and not p.is_symlink() and
                    re.fullmatch(r'[0-9a-f]{64}\.json',p.name) and
                    now.timestamp()-p.stat().st_mtime>90*86400):p.unlink()
    except OSError:pass


def rollback(revision,*,root=None,now=None):
    """Explicit developer rollback to a validated retained revision; stays stale."""
    root=Path(root or CACHE_DIR);now=now or utcnow()
    with cache_lock(root) as locked:
        if not locked:raise ValueError('Refresh in progress')
        for path in (root/'history').glob('*.json'):
            old=_read(path)
            if isinstance(old,dict) and _active_valid(old.get('active')) and old['active']['revision']==revision:
                current=load_manifest(root)
                if current['active']:_atomic_write(root/'history'/f'{digest(current)}.json',current)
                old['health']={'status':'error','checked_at':now.isoformat(),'error':'Explicit rollback; recheck required',
                               'failure_count':0,'next_retry_at':now.isoformat()}
                _atomic_write(root/'current.json',old)
                return view(old,now=now)
    raise ValueError('No validated retained revision found')


def pinned(fn):
    @wraps(fn)
    def wrapped(*args,**kwargs):
        if PINNED.get() is not None:return fn(*args,**kwargs)
        token=PINNED.set(snapshot())
        try:return fn(*args,**kwargs)
        finally:PINNED.reset(token)
    return wrapped


def metadata(state):
    return {**{k:v for k,v in state.items() if k not in ('notices','refresh_status')},
            'service_notices':copy.deepcopy(state['notices'])}


def _family_match(family,name):
    def norm(x):return re.sub(r'[^a-z0-9]','',x.lower())
    f,n=norm(family),norm(name)
    patterns={'centrall':r'centrall(?:eb|wb|nb|sb)?',
              'centraljackson':r'centraljackson(?:eb|wb|nb|sb)?',
              'ryanfield':r'ryanfield(?:ashlandwalkerway)?(?:sb|nb)?',
              'noyesl':r'noyesl(?:eb|wb)?','emersonmaple':r'emersonmaple(?:eb|wb)?',
              'sheridanhaventech':r'sheridanhaven(?:tech)?(?:nb|sb)?',
              'wardbuilding':r'ward(?:building)?'}
    return bool(re.fullmatch(patterns.get(f,re.escape(f)),n)) if f else False


def _during(notice,start,end):
    if not notice['windows']:return True,False
    overlap=False;boundary=False
    for w in notice['windows']:
        a,b=stamp(w['start']),stamp(w.get('end'))
        if b and start==end==b and w['end_inclusive']:
            overlap=True;boundary=True
        elif end>=a and (b is None or start<b):overlap=True
    return overlap,boundary


def evaluate(state,route,direction,stops,start,end=None,*,journey=False):
    """Pure evaluator. Stops are board/alight for pickup closures; route effects
    apply across travel interval. Uncertain or conflicting effects never erase service.
    """
    end=end or start;alerts=[];blocked=False;uncertain=False
    for n in state['notices']:
        if n.get('withdrawn') or (n['routes'] and route not in n['routes']):continue
        match,boundary=_during(n,start,end)
        if not match:continue
        for effect in n['effects']:
            kind=effect['type']
            if kind in ('informational','special_service'):continue
            dirs=effect['directions'] or n['directions']
            if dirs and direction not in dirs:
                if direction in (None,'Unknown','NonDirectional'):unknown_direction=True
                else:continue
            else:unknown_direction=False
            if kind=='stop_not_served' and effect['stop_families'] and not any(
                    _family_match(f,s) for f in effect['stop_families'] for s in stops):continue
            certain=effect['certain'] and n['lifecycle']=='present' and not boundary and not unknown_direction
            conflicts=[other['id'] for other in state['notices'] if other.get('withdrawn') and
                       other['id']!=n['id'] and (not other['routes'] or route in other['routes']) and
                       _during(other,start,end)[0]]
            if conflicts:certain=False
            # Missing source dates/routes never produce a hard exclusion.
            certain=certain and bool(n['windows'] and n['routes'])
            impact='unavailable' if certain and kind in ('service_canceled','stop_not_served') else 'uncertain'
            blocked |= impact=='unavailable';uncertain |= impact=='uncertain'
            alerts.append({'notice_id':n['id'],'notice_revision':n['revision'],'heading':n['heading'],
                'source_url':n['source_url'],'evidence':effect['evidence'],'effect':kind,'impact':impact,
                'warnings':n['warnings']+(['Effective end boundary is ambiguous.'] if boundary else [])+
                    (['Announcement disappeared without explicit resolution.'] if n['lifecycle']=='removed_unconfirmed' else [])+
                    (['Direction unavailable; scope cannot be confirmed.'] if unknown_direction else []),
                'conflicting_notice_ids':conflicts,
                'original_date_phrases':n.get('original_date_phrases',[]),'date_basis':n.get('date_basis'),
                'lifecycle':n['lifecycle']})
    health_uncertain=state['service_updates_status'] not in ('fresh','parse_review_required')
    return {'service_alerts':alerts,'service_impact':'unavailable' if blocked else ('uncertain' if uncertain or health_uncertain else 'no_applicable_notice_found'),
            'recommendation_status':('excluded' if journey else 'not_recommended') if blocked else
                ('provisional' if uncertain or health_uncertain else 'schedule_only')}


def annotate_departures(rows,state):
    result=[]
    for row in rows:
        at=stamp(row.get('reported_expected_arrival_local') or row.get('scheduled_departure_local'))
        if at:
            direction=row.get('loop_direction',{}).get('label') or row.get('direction')
            impact=evaluate(state,row.get('route_group'),direction,[row.get('stop_name','')],at)
        else:impact={'service_alerts':[],'service_impact':'uncertain','recommendation_status':'provisional'}
        result.append({**row,**impact})
    return result


def annotate_journey(option,state):
    start=stamp(option['board_time_local']);end=stamp(option['alight_time_local'])
    route,direction=option['route'],option['direction']
    results=[evaluate(state,route,direction,[],start,end,journey=True),
             evaluate(state,route,direction,[option['board_stop']],start,journey=True),
             evaluate(state,route,direction,[option['alight_stop']],end,journey=True)]
    alerts={digest(a):a for r in results for a in r['service_alerts']}
    excluded=any(r['recommendation_status']=='excluded' for r in results)
    provisional=any(r['recommendation_status']=='provisional' for r in results)
    return {**option,'service_alerts':list(alerts.values()),
            'service_impact':'unavailable' if excluded else ('uncertain' if provisional else 'no_applicable_notice_found'),
            'recommendation_status':'excluded' if excluded else ('provisional' if provisional else 'schedule_only')}


def query(*,route=None,when_local=None,auto_refresh=True):
    state=snapshot(auto_refresh=auto_refresh)
    at=None
    if when_local is not None:
        from service_updates_parser import _local
        try:at=_local(datetime.fromisoformat(when_local))
        except (ValueError,TypeError):return {'error':'invalid_date_time','message':'Supply an unambiguous Chicago timestamp.'}
    notices=[n for n in state['notices'] if (route is None or not n['routes'] or route in n['routes']) and
             (at is None or _during(n,at,at)[0])]
    return {**metadata(state),'notices':notices,'notice_count':len(notices),
            'special_service_notices':[n for n in notices if any(e['type']=='special_service' for e in n['effects'])]}
