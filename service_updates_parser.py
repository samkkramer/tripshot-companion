"""Conservative deterministic interpretation of public shuttle announcements.

Unknown wording is retained for review. No current-date year guesses, execution,
arbitrary links, timetable synthesis, or prediction adjustments.
"""
import hashlib
import json
import re
from datetime import date, datetime, time, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

from service_updates_source import SOURCE_URL, MAX_BYTES

PARSER_VERSION='1'
CHICAGO=ZoneInfo('America/Chicago')
MONTHS={m.lower():i for i,m in enumerate(('January','February','March','April','May','June',
          'July','August','September','October','November','December'),1)}
DATE_RE=re.compile(r'\b('+'|'.join(MONTHS)+r')\s+(\d{1,2})(?!\d)(?:,?\s+(20\d{2})(?![-\d]))?',re.I)
ISO_RE=re.compile(r'\b20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?\b')
CLOCK_RE=re.compile(r'\b(1[0-2]|0?[1-9])(?::([0-5]\d))?\s*([ap])\.?m\.?',re.I)
STOP_FAMILIES={
    'Central L':r'\bcentral\s*[\x27\u2018\u2019\u201c\u201d\x22]*l(?:[\x27\u2018\u2019\u201c\u201d\x22]*\s+station)?\b',
    'Central/Jackson':r'\bcentral\s*/\s*jackson\b',
    'Ryan Field':r'\bryan\s+field\b',
    'Noyes L':r'\bnoyes\s*[\x27\u2018\u2019\x22]*l\b',
    'Emerson/Maple':r'\bemerson\s*/\s*maple\b',
    'Sheridan/Haven - Tech':r'\bsheridan\s*/\s*haven(?:\s*-\s*tech)?\b',
    'Ward Building':r'\bward(?:\s+building)?\b',
}


class NoticeFormatError(ValueError):pass


def normalized(text):
    return re.sub(r'\s+',' ',text.replace('\xa0',' ')).strip()


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
                                    separators=(',',':')).encode()).hexdigest()


def safe_link(value):
    url=urljoin(SOURCE_URL,value)
    p=urlsplit(url)
    if (p.scheme=='https' and p.hostname in ('www.northwestern.edu','northwestern.edu')
            and p.port in (None,443) and not (p.username or p.password or p.query)):
        return url
    return None


class _Section(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_section=False;self.found=False;self.heading=None;self.heading_text=[]
        self.heading_anchor=None;self.current=None;self.notices=[];self.section_text=[]
        self.hidden=0;self.section_count=0
        self.body_seen=False;self.body_closed=False

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='body':self.body_seen=True
        if tag in ('script','style','noscript','template'):
            self.hidden+=1;return
        if self.hidden:return
        if re.fullmatch(r'h[1-6]',tag):
            if self.heading:raise NoticeFormatError('Nested announcement heading')
            self.heading=tag;self.heading_text=[];self.heading_anchor=attrs.get('id')
        elif self.in_section:
            if tag in ('p','li','br'):self._text('\n')
            if tag=='a' and self.current:
                link=safe_link(attrs.get('href',''))
                if link and link!=SOURCE_URL:self.current['links'].append(link)

    def _text(self,text):
        self.section_text.append(text)
        if self.current:self.current['body'].append(text)

    def handle_data(self,data):
        if self.hidden:return
        if self.heading:self.heading_text.append(data)
        elif self.in_section:self._text(data)

    def handle_endtag(self,tag):
        if tag=='body':self.body_closed=True
        if tag in ('script','style','noscript','template'):
            self.hidden=max(0,self.hidden-1);return
        if self.hidden:return
        if tag==self.heading:
            text=normalized(''.join(self.heading_text))
            if tag=='h2':
                self.in_section=text.casefold()=='shuttle service updates'
                if self.in_section:
                    self.found=True;self.section_count+=1
                self.current=None
            elif self.in_section and tag=='h3':
                self.current={'heading':text,'body':[],'links':[], 'anchor':self.heading_anchor}
                self.notices.append(self.current)
            elif self.in_section:
                self._text(text)
            self.heading=None;self.heading_text=[]
        elif self.in_section and tag in ('p','li'):self._text('\n')


def _local(value):
    """Reject ambiguous/nonexistent naive wall times; preserve explicit offsets."""
    if value.tzinfo is not None:return value.astimezone(CHICAGO)
    candidates=[value.replace(tzinfo=CHICAGO,fold=f) for f in (0,1)]
    valid=[x for x in candidates if x.astimezone(timezone.utc).astimezone(CHICAGO).replace(tzinfo=None)==value]
    if not valid or len({x.utcoffset() for x in valid})!=1:
        raise ValueError('Ambiguous or nonexistent Chicago wall time')
    return valid[0]


def validity(text,reviewed_year=None):
    reasons=[];windows=[];phrases=[]
    iso=ISO_RE.findall(text)
    if iso:
        try:
            values=[_local(datetime.fromisoformat(x.replace('Z','+00:00'))) for x in iso]
            if len(values)!=2 or values[1]<=values[0]:raise ValueError('Expected increasing interval')
            windows=[{'start':values[0].isoformat(),'end':values[1].isoformat(),'end_inclusive':False}]
        except ValueError as exc:reasons.append(str(exc))
        return windows,iso,reasons,'explicit_timestamp'
    dates=list(DATE_RE.finditer(text))
    if not dates:return [],[],['No precise effective date stated.'],'unknown'
    resolved=[]
    for m in dates:
        phrases.append(m[0])
        year=int(m[3]) if m[3] else reviewed_year
        if year is None:
            reasons.append('Effective year omitted; no reviewed year context.');continue
        try:day=date(year,MONTHS[m[1].lower()],int(m[2]))
        except ValueError:
            reasons.append('Invalid calendar date.');continue
        before=text[max(0,m.start()-12):m.start()].lower()
        weekdays=('monday','tuesday','wednesday','thursday','friday','saturday','sunday')
        if any(w in before and weekdays[day.weekday()]!=w for w in weekdays):
            reasons.append('Weekday disagrees with effective date.');continue
        resolved.append(day)
    if len(resolved)!=len(dates):return [],phrases,list(dict.fromkeys(reasons)),'unresolved'
    # A repeated date in heading/body describes one interval, not duplicate effects.
    days=list(dict.fromkeys(resolved))
    clocks=list(CLOCK_RE.finditer(text))
    if clocks:
        if len(clocks)!=2 or len(days)>2:
            return [],phrases,['Time interval is not unambiguous.'],'unresolved'
        def clock(m):return time(int(m[1])%12+(12 if m[3].lower()=='p' else 0),int(m[2] or 0))
        try:
            start=_local(datetime.combine(days[0],clock(clocks[0])))
            end_day=days[-1]
            end_naive=datetime.combine(end_day,clock(clocks[1]))
            if end_naive<start.replace(tzinfo=None) and len(days)==1:
                return [],phrases,['End time precedes start; overnight date not explicit.'],'unresolved'
            end=_local(end_naive)
            if end<=start:raise ValueError('Invalid effective interval')
            windows=[{'start':start.isoformat(),'end':end.isoformat(),
                      'end_inclusive':bool(re.search(r'\b(?:until|through|between)\b',text,re.I))}]
        except ValueError as exc:reasons.append(str(exc))
    elif re.search(r'\buntil further notice\b',text,re.I):
        windows=[{'start':_local(datetime.combine(days[0],time())).isoformat(),'end':None,'end_inclusive':False}]
    else:
        range_dates=len(days)==2 and len(dates)>=2 and re.search(r'\b(?:through|until|to)\b|\s-\s',
                    text[dates[0].end():dates[1].start()],re.I)
        if range_dates and days[1]<days[0]:return [],phrases,['Invalid date range.'],'unresolved'
        windows=[{'start':_local(datetime.combine(d,time())).isoformat(),
                  'end':_local(datetime.combine(d+timedelta(days=1),time())).isoformat(),
                  'end_inclusive':False} for d in days]
        if range_dates:windows=[{**windows[0],'end':windows[-1]['end']}]
        if re.search(r'\bevery\b|\bweekdays\b',text,re.I):
            return [],phrases,['Recurring operational rule requires review.'],'unresolved'
    return windows,phrases,reasons,'explicit_year' if all(m[3] for m in dates) else 'reviewed_year_context'


def interpret(raw,reviewed_years=None):
    title=raw['heading'];body='\n'.join(normalized(x) for x in ''.join(raw['body']).splitlines() if normalized(x))
    text=title+'\n'+body
    evidence_hash=digest([normalized(title),normalized(body),sorted(set(raw['links']))])
    review=(reviewed_years or {}).get(evidence_hash)
    if review is not None and (type(review) is not int or not 2000<=review<=2100):
        raise NoticeFormatError('Invalid reviewed year context')
    windows,phrases,reasons,basis=validity(text,review)
    routes=[r for r,pattern in (('Intercampus',r'\bintercampus\b'),('Loop',r'\bloop\b'),
            ('Chicago Express',r'\bchicago express\b')) if re.search(pattern,text,re.I)]
    def explicit_directions(value):
        return [d for d in ('Counterclockwise','Clockwise','Evanston to Chicago','Chicago to Evanston')
                if re.search(r'\b'+re.escape(d)+r'\b',value,re.I)]
    directions=explicit_directions(title)
    effects=[]
    for clause in re.split(r'[\n.;]+(?!\d)',body):
        lower=clause.lower()
        if re.search(r'\bno service at\b|\bstops? (?:are |will be )?(?:closed|not served)\b|\bwill not (?:serve|stop at)\b',lower):
            names=[name for name,pattern in STOP_FAMILIES.items() if re.search(pattern,clause,re.I)]
            residual=re.sub(r'^.*?(?:no service at|will not (?:serve|stop at))','',clause,flags=re.I)
            for pattern in STOP_FAMILIES.values():residual=re.sub(pattern,'',residual,flags=re.I)
            residual=re.sub(r'\b(?:the|and|or|stop|stops|station|are|is|will|be|closed|not|served|until|further|notice)\b',
                            '',residual,flags=re.I)
            unknown=bool(re.search(r'[A-Za-z]',residual))
            # Generic physical-stop names are explicit families, not guessed stop IDs.
            effects.append({'type':'stop_not_served','stop_families':names,'directions':[],
                            'certain':bool(names) and not unknown,'evidence':normalized(clause)})
            if not names or unknown:reasons.append('Affected stop names or directional variants require review.')
        if re.search(r'\b(?:cancel(?:ed|led|lation)|suspend(?:ed)?|no (?:shuttle )?service)\b',lower) and not re.search(r'\bno service at\b',lower):
            uncertain=bool(re.search(r'\b(?:may|might|possible|possibly|could|north of|south of|at)\b|\bbetween\s+[a-z]',lower))
            specific=explicit_directions(clause) or directions
            if re.search(r'\b(?:northbound|southbound|eastbound|westbound)\b',lower) and not specific:
                uncertain=True;reasons.append('Route direction requires explicit mapping/review.')
            effects.append({'type':'service_canceled','stop_families':[],'directions':specific,
                            'certain':not uncertain,'evidence':normalized(clause)})
        if re.search(r'\b(?:shorted|shortened|end at|begin at|truncated)\b',lower):
            d=[]
            if 'northbound' in lower and 'chicago' in lower:d=['Chicago to Evanston']
            if 'southbound' in lower and 'evanston' in lower:d=['Evanston to Chicago']
            effects.append({'type':'route_truncated','stop_families':[],'directions':d,
                            'certain':False,'evidence':normalized(clause)})
        elif re.search(r'\bdetour\b',lower):
            effects.append({'type':'detour','stop_families':[],'directions':directions,
                            'certain':False,'evidence':normalized(clause)})
    special=bool(re.search(r'\bchicago express\b|\bspecial (?:shuttle|service)\b',text,re.I))
    withdrawn=bool(re.search(r'\b(?:withdrawn|rescinded|retracted|closure (?:is |has been )?lifted)\b',body,re.I)) and not bool(
        re.search(r'\b(?:may|might|possible|possibly|could|not)\b',body,re.I))
    if special:effects.append({'type':'special_service','stop_families':[],'directions':[],
                               'certain':False,'evidence':title})
    if not effects:
        informational=bool(re.search(r'\bwildcard\b|\btap.reader\b',title,re.I))
        effects=[{'type':'informational' if informational or withdrawn else 'unresolved',
                  'stop_families':[],'directions':[],'certain':False,'evidence':title}]
    operational=any(e['type'] not in ('informational','special_service') for e in effects)
    if not routes and operational:reasons.append('Affected route is unresolved.')
    if re.search(r'\bone direction\b|\bsome stops\b|\bunspecified\b',text,re.I):
        reasons.append('Operational scope is ambiguous.')
        for e in effects:e['certain']=False
    if operational and not windows:reasons.append('Effective interval unresolved; automatic cancellation disabled.')
    if any(e['type']=='unresolved' for e in effects):reasons.append('Operational wording is not supported; review required.')
    if any(e['type'] in ('route_truncated','detour') for e in effects):
        reasons.append('Changed path/terminus timing and stop linkage are not validated.')
    for e in effects:
        e['certain']=e['certain'] and bool(routes and windows)
    anchor=raw['anchor'] if raw['anchor'] and re.fullmatch(r'[A-Za-z0-9_-]{1,120}',raw['anchor']) else None
    first_date=phrases[0].lower() if phrases else ''
    identity=digest([anchor] if anchor else [title.casefold(),routes,first_date])
    return {'schema':1,'id':identity,'revision':evidence_hash,'heading':title,'evidence':body,
            'source_url':SOURCE_URL,'source_anchor':anchor,'links':sorted(set(raw['links'])),
            'routes':routes,'directions':directions,'effects':effects,'windows':windows,
            'original_date_phrases':phrases,'date_basis':basis,'reviewed_year':review,
            'warnings':list(dict.fromkeys(reasons)),'withdrawn':withdrawn,
            'published_at':None,'source_updated_at':None,'lifecycle':'present',
            'parser_version':PARSER_VERSION}


def parse_page(html,*,reviewed_years=None):
    if not isinstance(html,str) or len(html.encode('utf-8'))>MAX_BYTES:
        raise NoticeFormatError('Invalid or oversized announcement document')
    p=_Section();p.feed(html);p.close()
    if p.heading or p.hidden or not p.body_seen or not p.body_closed or not p.found or p.section_count!=1:
        raise NoticeFormatError('Missing, incomplete or duplicated shuttle section')
    if not p.notices:
        if not re.search(r'\bno (?:current |active )?(?:shuttle )?(?:notices|updates|announcements)\b',
                         normalized(' '.join(p.section_text)),re.I):
            raise NoticeFormatError('Empty shuttle section without explicit empty-state evidence')
    notices=[interpret(n,reviewed_years) for n in p.notices]
    if len({n['id'] for n in notices})!=len(notices):
        raise NoticeFormatError('Ambiguous duplicate notice identity')
    if len(notices)>100 or any(len(n['evidence'])>16000 for n in notices):
        raise NoticeFormatError('Unexpected announcement size/count')
    return {'notices':notices,'section_hash':digest([(n['id'],n['revision']) for n in notices]),
            'document_hash':hashlib.sha256(html.encode()).hexdigest(),'parser_version':PARSER_VERSION}
