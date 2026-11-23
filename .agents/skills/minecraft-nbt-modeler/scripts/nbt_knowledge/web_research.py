"""Explicit online research and content-addressed reference receipts."""

from datetime import datetime, timezone
import hashlib
import json
import os
from queue import Empty, Queue
import re
from threading import Thread
from time import monotonic, time
from urllib.parse import quote, urlencode, urlsplit

from nbt_assets.libraries import atomic
from .public_web import WebError, extract, get, public_url

CACHE_TTL = 24*3600
ID = re.compile(r'[a-f0-9]{64}')
# Route known subjects to original institutions before using a general index.
SOURCES = (
    (('sainte-chapelle','sainte chapelle','圣礼拜堂'),('rose','玫瑰窗','rosace'),
     'https://www.sainte-chapelle.fr/en/discover/the-rose-of-the-apocalypse'),
    (('sainte-chapelle','sainte chapelle','圣礼拜堂'),('radiant','rayonnant','哥特','放射','彩窗','vitrail'),
     'https://www.sainte-chapelle.fr/en/discover/the-radiant-gothic'),
    (('notre-dame','notre dame','巴黎圣母院'),('exterior','扶壁','外部','buttress'),
     'https://www.notredamedeparis.fr/en/understand/architecture/exterior-architecture/'),
    (('amiens','亚眠'),('gothic','cathedral','哥特','教堂'),
     'https://www.amiens.fr/Vivre-a-Amiens/Culture-Patrimoine/Patrimoine-mondial/La-cathedrale-Notre-Dame-d-Amiens'),
)
PUBLISHERS = {'www.sainte-chapelle.fr':'Centre des monuments nationaux',
              'www.notredamedeparis.fr':'Cathédrale Notre-Dame de Paris', 'www.amiens.fr':'Ville d’Amiens'}


def raw_json(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def location(workspace, folder, identifier):
    root = (workspace/'.nbtcreator/retrieval/web').resolve()
    path = (root/folder/(identifier+'.json')).resolve()
    if not root.is_relative_to(workspace) or not path.is_relative_to(root):
        raise ValueError('网络参考缓存路径越过工作区')
    return path


def valid_text(value, maximum, name, *, optional=False):
    if value is None and optional:
        return ''
    if not isinstance(value,str) or len(value)>maximum or not value.strip() or any(ord(c)<32 and c not in '\t\r\n' for c in value):
        raise ValueError(f'{name}须为1～{maximum}字的文本')
    return ' '.join(value.split())


def public_query(value):
    query = valid_text(value,180,'公开搜索词',optional=True)
    if query and (re.search(r'(?:https?://|\b[a-z]:[\\/]|\\\\|/(?:Users|home|mnt)/|\b(?:api[_ -]?key|password|bearer|token)\s*[:=]|sk-[a-z0-9_-]{12,})',query,re.I)
                  or re.search(r'\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b|(?:\[|\()\s*-?\d+\s*,\s*-?\d+\s*,\s*-?\d+',query,re.I)):
        raise ValueError('搜索词只填写公开对象和要核实的问题，链接请单独填写')
    return query


def find_urls(query, deadline):
    key = os.environ.get('NBTCREATOR_BRAVE_SEARCH_KEY')
    if key:
        params = urlencode(dict(q=query,count=6))
        _,_,_,raw = get('https://api.search.brave.com/res/v1/web/search?'+params,deadline,json_response=True,
                         headers={'X-Subscription-Token':key})
        return [row.get('url') for row in json.loads(raw).get('web',{}).get('results',[])[:6]]
    lang = 'zh' if re.search(r'[\u3400-\u9fff]',query) else 'en'
    host = f'{lang}.wikipedia.org'
    params = urlencode(dict(action='query',list='search',srsearch=query,srnamespace=0,srlimit=6,srprop='',format='json',formatversion=2))
    _,_,_,raw = get(f'https://{host}/w/api.php?'+params,deadline,json_response=True)
    response = json.loads(raw)
    if 'error' in response:
        raise WebError('SEARCH_UNAVAILABLE','检索服务暂不可用')
    return [f'https://{host}/wiki/'+quote(row['title'].replace(' ','_')) for row in response.get('query',{}).get('search',[])[:6]]


def official_candidates(query):
    text = query.casefold()
    return [url for subjects,terms,url in SOURCES if any(subject in text for subject in subjects) and any(term in text for term in terms)]


def page(url, query, deadline):
    origin,media,charset,raw = get(url,deadline)
    title,publisher,heading,excerpt = extract(raw,media,charset,query)
    domain = urlsplit(origin).hostname
    return dict(source_url=origin,title=title or domain,publisher=publisher or PUBLISHERS.get(domain,domain),
                section=heading or title or '正文',text=excerpt,content_kind='excerpt',
                accessed_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),page_sha256=sha(raw),
                verification='app_opened')


def persist(workspace, flow, evidence):
    data = raw_json(dict(workflow=flow,schema_version=1,evidence=evidence))
    digest = sha(data)
    file = location(workspace,'evidence',digest)
    if not file.exists() or file.stat().st_size!=len(data) or file.read_bytes()!=data:
        atomic(file,data)
    return citation(digest,evidence)


def citation(digest, record):
    return dict(id='web:'+digest,document_id='web:'+digest,sha256=digest,kind='knowledge',
                reference_type='web',label=record['title'],heading=record['section'],text=record['text'],
                locator=record['source_url'],passage_sha256=sha(record['text'].encode('utf8')),
                bibliography={key:value for key,value in record.items() if key not in ('text','title','section')})


def read(workspace, flow, identifier):
    digest = identifier[4:] if isinstance(identifier,str) and identifier.startswith('web:') else ''
    if not ID.fullmatch(digest):
        raise ValueError('网络证据编号无效')
    try:
        file = location(workspace,'evidence',digest)
        with file.open('rb') as stream:
            data = stream.read(8193)
        if len(data)>8192 or sha(data)!=digest:
            raise ValueError
        record = json.loads(data)
        if record['schema_version']!=1 or record['workflow']!=flow:
            raise ValueError
    except (OSError,ValueError,KeyError,TypeError) as error:
        raise ValueError('网络证据已变化、丢失或不属于本工作流') from error
    return citation(digest,record['evidence'])


def import_evidence(workspace, flow, request):
    if set(request)-{'workflow','evidence'}:
        raise ValueError('导入仅接收已打开来源的证据')
    entries = request.get('evidence')
    if not isinstance(entries,list) or not 1<=len(entries)<=6:
        raise ValueError('导入须包含1～6条已打开的网页证据')
    prepared = []
    for entry in entries:
        required = {'source_url','title','publisher','section','text','accessed_at','content_kind','reader'}
        if not isinstance(entry,dict) or set(entry)!=required or entry['content_kind'] not in ('excerpt','summary'):
            raise ValueError('请填写原页、访问时间、读取工具和正文摘录或提要')
        updated = dict(entry,source_url=public_url(entry['source_url'],keep_fragment=True))
        for key,limit in (('title',200),('publisher',160),('section',200),('text',220),('reader',80),('accessed_at',32)):
            updated[key] = valid_text(entry[key],limit,key)
        seen = datetime.fromisoformat(updated['accessed_at'])
        if seen.tzinfo is None or seen.timestamp()>time()+300:
            raise ValueError('访问时间须为已发生并带时区的 ISO 8601 时间')
        prepared.append(dict(updated,verification='host_reported'))
    return dict(workflow=flow,evidence=[persist(workspace,flow,item) for item in prepared])


def racing(tasks, deadline, enough):
    done = Queue()
    def run(label, call):
        try:
            done.put((label,call(),None))
        except WebError as error:
            done.put((label,None,dict(code=error.code,message=str(error))))
        except (OSError,ValueError,KeyError,TypeError,AttributeError):
            done.put((label,None,dict(code='UNAVAILABLE',message='来源未返回有效内容')))
    pending = set(tasks)
    for label,call in tasks.items():
        Thread(target=run,args=(label,call),daemon=True).start()
    while pending and enough()>0:
        try:
            label,result,error = done.get(timeout=max(0,deadline-monotonic()))
        except Empty:
            for label in sorted(pending):
                yield label,None,dict(code='TIMEOUT',message='来源未在取证预算内返回')
            break
        pending.remove(label)
        yield label,result,error


def live(workspace, flow, query, urls, queries, limit, timeout, *, finder, opener):
    started = monotonic()
    deadline = started + timeout/1000
    seen,origins,passages = set(),set(),set()
    result = dict(workflow=flow,status='no_evidence',evidence=[],failures=[],metrics=dict(searches=0,pages_started=0,cache_hit=False,first_evidence_ms=None))
    metrics = result['metrics']

    def take(candidates):
        pending = []
        for raw in candidates:
            try:
                url = public_url(raw)
            except WebError:
                continue
            if url not in seen and url not in pending:
                pending.append(url)
        for offset in range(0,len(pending),2):
            if len(result['evidence'])>=limit or metrics['pages_started']>=6 or monotonic()>=deadline:
                break
            batch = pending[offset:offset+min(2,6-metrics['pages_started'])]
            seen.update(batch)
            metrics['pages_started'] += len(batch)
            stop = min(deadline,monotonic()+4.5)
            work = {url:(lambda url=url:opener(url,query,stop)) for url in batch}
            for url,evidence,error in racing(work,stop,lambda:limit-len(result['evidence'])):
                if error:
                    result['failures'].append(dict(url=url,**error))
                elif evidence['source_url'] not in origins and evidence['text'] not in passages:
                    origins.add(evidence['source_url'])
                    passages.add(evidence['text'])
                    result['evidence'].append(persist(workspace,flow,evidence))
                    if metrics['first_evidence_ms'] is None:
                        metrics['first_evidence_ms'] = round((monotonic()-started)*1000,1)

    take(urls)
    if len(result['evidence'])<limit and query:
        take(official_candidates(query))
    for term in queries:
        if len(result['evidence'])>=limit or metrics['pages_started']>=6 or monotonic()>=deadline:
            break
        metrics['searches'] += 1
        stop = min(deadline,monotonic()+3.0)
        _,candidates,error = next(racing({'search':lambda:finder(term,stop)},stop,lambda:1))
        if error:
            result['failures'].append(dict(stage='search',**error))
            if error['code']=='RATE_LIMIT':
                break
        else:
            take(candidates)
    result['status'] = 'complete' if len(result['evidence'])>=limit else 'partial' if result['evidence'] else 'no_evidence'
    metrics['elapsed_ms'] = round((monotonic()-started)*1000,1)
    return result


def research(workspace, flow, request, *, finder=find_urls, opener=page):
    if set(request)-{'workflow','query','urls','fallback_queries','limit','timeout_ms','refresh'}:
        raise ValueError('联网取证仅接收公开查询、直接链接和取证预算')
    query = public_query(request.get('query'))
    urls,alternatives = request.get('urls',[]),request.get('fallback_queries',[])
    limit,timeout,refresh = request.get('limit',1),request.get('timeout_ms',9000),request.get('refresh',False)
    if not isinstance(urls,list) or len(urls)>6 or not isinstance(alternatives,list) or len(alternatives)>2:
        raise ValueError('每次至多提供6个链接和2条备用查询')
    if type(limit) is not int or not 1<=limit<=6 or type(timeout) is not int or not 500<=timeout<=12000 or type(refresh) is not bool:
        raise ValueError('证据数量须为1～6，时间预算为500～12000毫秒')
    if not query and not urls:
        raise ValueError('请填写公开搜索词或公开原页链接')
    urls = list(dict.fromkeys(public_url(url) for url in urls))
    queries = list(dict.fromkeys(filter(None,[query,*map(public_query,alternatives)])))
    provider = 'brave' if os.environ.get('NBTCREATOR_BRAVE_SEARCH_KEY') else 'wikimedia'
    key = sha(raw_json(dict(flow=flow,urls=urls,queries=queries,limit=limit,provider=provider,schema_version=1)))
    file = location(workspace,'queries',key)
    now = monotonic()
    if not refresh and file.is_file():
        try:
            with file.open('rb') as stream:
                cached = json.loads(stream.read(8192))
            if 0 <= time()-cached['saved'] <= CACHE_TTL and len(cached['ids'])==limit:
                evidence = [read(workspace,flow,identifier) for identifier in cached['ids']]
                elapsed = round((monotonic()-now)*1000,1)
                return dict(workflow=flow,status='complete',evidence=evidence,failures=[],
                            metrics=dict(searches=0,pages_started=0,cache_hit=True,first_evidence_ms=elapsed,elapsed_ms=elapsed))
        except (OSError,ValueError,KeyError,TypeError):
            pass
    result = live(workspace,flow,query,urls,queries,limit,timeout,finder=finder,opener=opener)
    if result['status']=='complete':
        atomic(file,raw_json(dict(saved=time(),ids=[item['id'] for item in result['evidence']])))
    return result
