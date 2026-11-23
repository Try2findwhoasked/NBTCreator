"""Read bounded public HTTPS pages and extract relevant visible passages."""

import codecs
from html.parser import HTMLParser
from http.client import HTTPSConnection, HTTPException
from ipaddress import ip_address, ip_network
import re
import socket
import ssl
from time import monotonic
from urllib.parse import parse_qsl, quote, urljoin, urlsplit, urlunsplit

from nbt_knowledge.text_search import tokens

USER_AGENT = 'NBTCreator-Research/1 (https://github.com/Try2findwhoasked/NBTCreator)'
MAX_BYTES = 2*1024*1024
BAD_PARAMETER = re.compile(r'(?:auth|token|pass|secret|key|session|signature|credential|code|jwt)', re.I)
STOPWORDS = set('how when what which where does did with from that this about have were the for and'.split())
WEB_TERMS = {'玫瑰窗': ('rose','rose of the apocalypse'), '重建': ('rebuilt','reconstructed','replaced'),
             '年代': ('century','around','built'), '圣礼拜堂': ('sainte-chapelle','upper chapel')}
IPV6_TRANSITION = tuple(map(ip_network,('64:ff9b::/96','64:ff9b:1::/48','2001::/32','2002::/16','::ffff:0:0/96')))
DATE_QUERY = re.compile(r'年代|年份|哪年|何時|何时|何年|什么时候|\b(?:when|rebuilt|construction date|what year)\b',re.I)
HISTORICAL_DATE = re.compile(r'\b\d{3,4}\b|\b(?:century|siècle)\b',re.I)


class WebError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def public_url(value, *, keep_fragment=False):
    if not isinstance(value, str) or not value or len(value)>1600 or re.search(r'[\s\\\x00-\x1f\x7f]', value):
        raise WebError('INVALID_URL', '请输入有效的公开 HTTPS 地址')
    try:
        parts = urlsplit(value)
        host = (parts.hostname or '').encode('idna').decode('ascii').lower().rstrip('.')
        if (parts.scheme!='https' or parts.username is not None or parts.password is not None or parts.port not in (None,443)
            or not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}',host)
            or host.rsplit('.',1)[-1] in ('local','localhost','internal','lan','home','test','invalid','example','onion')):
            raise ValueError
        if any(BAD_PARAMETER.search(key) for key,_ in parse_qsl(parts.query,max_num_fields=30,keep_blank_values=True)):
            raise ValueError
    except (ValueError, UnicodeError):
        raise WebError('INVALID_URL', '地址须为公开 HTTPS，且不含登录凭据或认证参数') from None
    return urlunsplit(('https',host,quote(parts.path or '/',safe="/%:@!$&'()*+,;=-._~"),
                       quote(parts.query,safe="%/?&=+,:@!$'()*;-._~"),
                       quote(parts.fragment,safe="%-._~:/") if keep_fragment else ''))


def public_address(host):
    addresses = socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
    ips = [ip_address(entry[4][0]) for entry in addresses]
    if not ips or any(not ip.is_global or ip.is_multicast or any(ip in network for network in IPV6_TRANSITION) for ip in ips):
        raise WebError('PRIVATE_ADDRESS','来源解析到了非公网地址')
    return str(next((ip for ip in ips if ip.version==4),ips[0]))


def remaining(deadline):
    budget = deadline-monotonic()
    if budget<=0:
        raise WebError('TIMEOUT','来源未在取证预算内返回')
    return budget


def get(url, deadline, *, json_response=False, headers=None):
    url = public_url(url)
    original_host = urlsplit(url).hostname
    for _ in range(4):
        parts = urlsplit(url)
        host = parts.hostname
        if headers and host!=original_host:
            raise WebError('INVALID_REDIRECT','搜索服务重定向到了其他来源')
        connection = HTTPSConnection(host,timeout=remaining(deadline),context=ssl.create_default_context())
        try:
            address = public_address(host)
            # Dial the validated IP while retaining the original TLS name and Host header.
            connection._create_connection = lambda _host, _timeout, source: socket.create_connection((address,443),remaining(deadline),source)
            path = urlunsplit(('', '', parts.path, parts.query, ''))
            request_headers = {'User-Agent':USER_AGENT, 'Accept-Encoding':'identity',
                               'Accept':'application/json' if json_response else 'text/html, text/plain;q=0.9'}
            connection.request('GET',path,headers={**request_headers,**(headers or {})})
            with connection.getresponse() as response:
                if response.status in (301,302,303,307,308) and response.getheader('Location'):
                    url = public_url(urljoin(url,response.getheader('Location')))
                    continue
                if response.status==429:
                    raise WebError('RATE_LIMIT','来源限流，请稍后重试')
                if response.status!=200:
                    raise WebError('HTTP_ERROR',f'来源返回 HTTP {response.status}')
                if response.getheader('Content-Encoding','identity').lower()!='identity':
                    raise WebError('UNSUPPORTED_ENCODING','来源未返回可直接读取的内容')
                media = response.headers.get_content_type()
                allowed = ('application/json',) if json_response else ('text/html','application/xhtml+xml','text/plain')
                if media not in allowed:
                    raise WebError('UNSUPPORTED_CONTENT','该来源需要用宿主工具查看原页或图版')
                size = 0
                chunks = []
                while size <= MAX_BYTES:
                    remaining(deadline)
                    chunk = response.read1(min(65536,MAX_BYTES+1-size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                if size>MAX_BYTES:
                    raise WebError('SIZE_LIMIT','原页超过读取上限')
                return url,media,response.headers.get_content_charset(),b''.join(chunks)
        except TimeoutError:
            raise WebError('TIMEOUT','来源未在取证预算内返回') from None
        except (OSError, HTTPException):
            raise WebError('UNAVAILABLE','无法读取该来源，请检查网络或用宿主工具打开') from None
        finally:
            connection.close()
    raise WebError('INVALID_REDIRECT','原页重定向次数超限')


def decode(raw, charset):
    if not charset:
        match = re.search(rb'<meta\b[^>]{0,150}charset\s*=\s*["\']?([\w-]+)',raw[:8192],re.I)
        charset = match[1].decode('ascii') if match else 'utf-8-sig'
    try:
        return raw.decode(codecs.lookup(charset).name,errors='replace')
    except (LookupError, UnicodeError):
        return raw.decode('utf-8-sig',errors='replace')


def tidy(value):
    return ' '.join(value.split())


class Article(HTMLParser):
    SKIP = {'script','style','noscript','svg','template','nav','footer','form','aside'}
    BLOCKS = {'title','h1','h2','h3','h4','p','figcaption','blockquote'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = []
        self.title = ''
        self.publisher = ''
        self.heading = ''
        self.block = ''
        self.pieces = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.hidden.append(tag)
        if self.hidden:
            return
        attrs = dict(attrs)
        if tag=='meta' and attrs.get('content'):
            if attrs.get('property')=='og:site_name':
                self.publisher = tidy(attrs['content'])
            elif attrs.get('property')=='og:title':
                self.title = tidy(attrs['content'])
        if tag in self.BLOCKS:
            self.flush()
            self.block = tag
        elif tag=='br':
            self.pieces.append(' ')

    def handle_endtag(self, tag):
        if self.hidden:
            if self.hidden[-1]==tag:
                self.hidden.pop()
            return
        if tag==self.block:
            self.flush()

    def handle_data(self, data):
        if self.block and not self.hidden:
            self.pieces.append(data)

    def flush(self):
        text = tidy(''.join(self.pieces))
        if self.block=='title' and not self.title:
            self.title = text
        elif self.block.startswith('h'):
            self.heading = text
            if self.block=='h1' and not self.title:
                self.title = text
        elif len(text)>=30 and len(self.rows)<1800:
            self.rows.append((self.heading,text))
        self.block = ''
        self.pieces.clear()


def extract(raw, media, charset, query):
    text = decode(raw,charset)
    article = Article()
    if media=='text/plain':
        article.rows = [('',tidy(line)) for line in text.splitlines() if len(tidy(line))>=30][:1800]
    else:
        article.feed(text)
        article.close()
        article.flush()
    if re.search(r'^(?:just a moment|access denied|forbidden|verify you are human|attention required)\b',article.title,re.I):
        raise WebError('UNREADABLE','原页需要人工完成访问验证')
    terms = sorted(set(tokens(query))-STOPWORDS)
    if query and re.search(r'[\u3400-\u9fff]',query):
        from nbt_knowledge.architecture_books import ALIASES
        terms.extend(word for dictionary in (ALIASES,WEB_TERMS) for term,aliases in dictionary.items() if term in query for word in aliases)
    patterns = {term:re.compile(r'(?<!\w)'+re.escape(term)+r'(?!\w)' if term.isascii() else re.escape(term),re.I)
                for term in terms}
    wants_date = DATE_QUERY.search(query)
    def weight(heading, passage):
        matched = sum((3 if ' ' in term else 1) for term,pattern in patterns.items() if pattern.search(passage))
        if not matched:
            return 0
        if wants_date and HISTORICAL_DATE.search(passage):
            matched += 6
        return matched + sum(bool(pattern.search(heading)) for pattern in patterns.values())
    best = None
    for heading,passage in article.rows:
        matched = weight(heading,passage)
        if (not terms or matched) and (best is None or matched>best[0]):
            best = (matched,heading,passage)
    if best is None:
        raise WebError('NO_PASSAGE','原页可访问，但未找到匹配的正文段落')
    _,heading,passage = best
    # Keep the quoted excerpt centered on a matching term or the opening sentence.
    matches = [match.start() for pattern in patterns.values() if (match:=pattern.search(passage))]
    start = max(0,min(matches,default=0)-55)
    clip = passage[start:start+220].strip()
    words = list(re.finditer(r'\S+',clip))
    if len(words)>23:
        clip = clip[:words[22].end()]
    return article.title[:200],article.publisher[:160],heading[:200],clip
