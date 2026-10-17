"""Bounded, unauthenticated GET of one official announcement page."""
from dataclasses import dataclass
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

SOURCE_URL = 'https://www.northwestern.edu/transportation-parking/service-updates/'
MAX_BYTES = 2_000_000


@dataclass(frozen=True)
class PageResponse:
    status: int
    html: str = ''
    etag: str | None = None
    last_modified: str | None = None
    effective_url: str = SOURCE_URL


def validate_source(url):
    p=urlsplit(url)
    if (p.scheme!='https' or p.hostname not in ('www.northwestern.edu','northwestern.edu')
            or p.port not in (None,443) or p.username or p.password or p.query or p.fragment
            or p.path!='/transportation-parking/service-updates/'):
        raise ValueError('Unapproved Service Updates URL')
    return url


class ScopedRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_source(newurl)  # Validate BEFORE sending another request.
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def fetch_page(*, etag=None, last_modified=None, opener=None):
    headers={'Accept':'text/html','User-Agent':'TripShotCompanion/1.0 (on-demand service notices)'}
    for name,value in (('If-None-Match',etag),('If-Modified-Since',last_modified)):
        if isinstance(value,str) and len(value)<1024 and not any(c in value for c in '\r\n'):
            headers[name]=value
    request=Request(validate_source(SOURCE_URL),headers=headers,method='GET')
    client=opener or build_opener(ScopedRedirects())
    deadline=time.monotonic()+8
    try:
        response=client.open(request,timeout=8)
    except HTTPError as exc:
        if exc.code!=304:raise
        exc.close()
        return PageResponse(304)
    with response as resp:
        effective=validate_source(resp.geturl())
        if resp.status!=200:raise ValueError('Unexpected source HTTP status')
        if resp.headers.get_content_type() not in ('text/html','application/xhtml+xml'):
            raise ValueError('Expected official HTML page')
        chunks=[]
        size=0
        while True:
            if time.monotonic()>deadline:raise TimeoutError('Service page deadline exceeded')
            chunk=resp.read(min(65536,MAX_BYTES+1-size))
            if not chunk:break
            chunks.append(chunk);size+=len(chunk)
            if size>MAX_BYTES:raise ValueError('Service page exceeds 2 MB')
        charset=resp.headers.get_content_charset() or 'utf-8'
        html=b''.join(chunks).decode(charset,errors='strict')
        return PageResponse(200,html,resp.headers.get('ETag'),resp.headers.get('Last-Modified'),effective)
