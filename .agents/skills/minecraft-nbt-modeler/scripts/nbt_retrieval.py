"""Offline reference search, explicit online research and workflow-bound evidence bundles."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import uuid
from itertools import zip_longest
from nbt_knowledge import libraries
from nbt_text_search import chunks, score

ROOT=Path(__file__).resolve().parents[1]
CATALOG=json.loads((ROOT/'tool-catalog.json').read_text(encoding='utf8'))
FLOWS=json.loads((ROOT/'config/ai-style-schema.json').read_text(encoding='utf8'))['workflows']
ACTIONS=('search','source','bundle','read','library','research','import-web','saved-web')
AUDIENCES=('internal_ai','external_agent')
RECEIPT_ID=re.compile('[a-f0-9]{32}')

def digest(raw):return hashlib.sha256(raw).hexdigest()
def encode(data):return (json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8')
def read(file,limit=512*1024):
    raw=file.read_bytes()
    if len(raw)>limit:raise ValueError('参考文件过大')
    return json.loads(raw.decode('utf-8-sig'))

def read_request(target):
    if target=='-':
        raw=sys.stdin.buffer.read(512*1024+1)
        if len(raw)>512*1024:raise ValueError('检索请求超过512KiB')
        return json.loads(raw.decode('utf-8-sig'))
    if target.lstrip().startswith(('{','[')):
        raise ValueError('--request 接收 UTF-8 JSON 文件路径，或用 --request - 从标准输入读取')
    return read(Path(target))

def workflow(request):
    key=request.get('workflow')
    if key not in FLOWS:raise ValueError('请选择有效的AI工作流')
    return key

def external_documents(workspace,issues=None):
    from nbt_exposure import GROUPS, read_config, read_custom
    config=read_config(workspace)
    refs=(ROOT/'references').resolve()
    names=dict.fromkeys(name for group in config['enabled_groups'] for name in GROUPS[group][1])
    for name in names:
        file=(refs/(name+'.md')).resolve()
        if not file.is_relative_to(refs):raise ValueError('资料路径越界')
        with file.open('rb') as stream:raw=stream.read(2*1024*1024+1)
        if len(raw)>2*1024*1024 or b'\x00' in raw:raise ValueError('对外资料须为不超过2MiB的文本')
        text=raw.decode('utf-8-sig')
        label=next((line[2:].strip() for line in text.splitlines() if line.startswith('# ')),file.stem)[:150]
        yield dict(id='external:'+name,label=label or file.stem,sha256=digest(raw),locator='skill:references/'+name+'.md',text=text)
    for item in config['custom_knowledge']:
        if not item['enabled']:continue
        try:raw,text=read_custom(workspace,item)
        except ValueError as failure:
            if issues is not None:issues.append(dict(id=item['id'],label=item['label'],error=str(failure)))
            continue
        yield dict(id=item['id'],label=item['label'] or Path(item['path']).stem,sha256=digest(raw),
                   locator='.nbtcreator/'+item['path'],text=text)

def documents(workspace,flow,audience='internal_ai',issues=None):
    if audience=='external_agent':return external_documents(workspace,issues)
    base=(workspace/'.nbtcreator/internal-ai').resolve();file=base/'config.json'
    if not file.is_file():return []
    config=read(file)
    if config.get('schema_version')!=1:raise ValueError('内部资料配置无效')
    selected=config.get('workflows',{}).get(flow,{}).get('knowledge',[])
    if not isinstance(selected,list) or len(selected)>100+len(CATALOG['knowledge_sources']):raise ValueError('资料选择无效')
    custom={item['id']:item for item in config.get('documents',[])};result=[]
    for identifier in dict.fromkeys(selected):
        if identifier in CATALOG['knowledge_sources']:
            spec=CATALOG['knowledge_sources'][identifier];file=(ROOT/'references'/spec['file']).resolve();base_path=(ROOT/'references').resolve();locator='skill:references/'+spec['file'];label=spec['label']
        else:
            spec=custom.get(identifier)
            if not re.fullmatch('[a-f0-9]{64}',str(identifier)) or not spec or spec.get('path')!='knowledge/'+identifier+'.md':raise ValueError('内部资料编号无效')
            file=(base/spec['path']).resolve();base_path=base/'knowledge';locator='.nbtcreator/internal-ai/'+spec['path'];label=spec['label']
        if not file.is_relative_to(base_path):raise ValueError('资料路径越界')
        raw=file.read_bytes()
        if len(raw)>256*1024 or b'\x00' in raw:raise ValueError('参考资料须为不超过256KiB的文本')
        sha=digest(raw)
        if not identifier.startswith('builtin:') and sha!=identifier:raise ValueError('导入资料已变化，请重新导入')
        result.append(dict(id=identifier,label=label,sha256=sha,locator=locator,text=raw.decode('utf-8-sig')))
    return result

def search(workspace,request,*,audience='internal_ai'):
    flow=workflow(request);query=request.get('query','')
    if not isinstance(query,str) or not query.strip() or len(query)>12000:raise ValueError('请输入1～12000字的本地检索要求')
    keywords=request.get('keywords',query)
    if 'keywords' in request and (not isinstance(keywords,str) or not keywords.strip() or len(keywords)>300):
        raise ValueError('keywords 接收 1～300 字明确检索词')
    include_extensions=request.get('include_extension_assets',False)
    if type(include_extensions) is not bool or include_extensions and audience!='external_agent':
        raise ValueError('include_extension_assets 仅用于外部 Agent 的离线候选浏览')
    size=request.get('size')
    if size is not None and (not isinstance(size,list) or len(size)!=3 or any(type(n) is not int or not 1<=n<=65536 for n in size)):raise ValueError('目标尺寸须为正整数XYZ')
    limit=request.get('limit',6 if audience=='external_agent' else 12)
    if type(limit) is not int or not 1<=limit<=32:raise ValueError('检索数量须为1～32')
    source_kind=request.get('source_kind')
    if source_kind not in (None,'skill','library','web'):raise ValueError('source_kind 须为 skill、library 或 web')
    if source_kind in ('skill','web') and ('filters' in request or 'library_id' in request):raise ValueError('书库筛选只能用于 library 资料')
    assets=[];catalog=dict(items=[],errors=[])
    if flow=='component' and source_kind is None:
        from nbt_components import listing
        catalog=listing(workspace)
    for item in catalog['items']:
        if item.get('archived'):continue
        value=score(keywords,item['name']+' '+ ' '.join(item.get('tags',[])))
        if value<=0:continue
        rotations=[turn for turn in (0,1) if size is None or all(n<=size[i] for i,n in enumerate(item['size'] if turn==0 else [item['size'][2],item['size'][1],item['size'][0]]))]
        # Rotation swaps X/Z only; no implicit resizing or clipping.
        if not rotations:continue
        assets.append(dict(id='asset:'+item['id'],kind='asset',asset_id=item['id'],label=item['name'],tags=item['tags'],size=item['size'],anchor=item['anchor'],content_sha256=item['content_sha256'],score=value,rotations=rotations,reason='名称或标签匹配；尺寸可容纳'+('（需绕Y旋转90°）' if rotations==[1] else ''),locator='.nbtcreator/components/'+item['id']+'.json',thumbnail=item.get('thumbnail')))
    groups,library_errors=(libraries.search(workspace,flow,keywords,limit,request) if source_kind in (None,'library') else ([],[]))
    knowledge=[];saved=[];saved_errors=[];knowledge_errors=[]
    if not request.get('filters') and not request.get('library_id'):
        if source_kind in (None,'web'):
            from nbt_knowledge.saved_references import search as search_saved
            saved,saved_errors=search_saved(workspace,flow,keywords,limit)
        if source_kind in (None,'skill'):
            for document in documents(workspace,flow,audience,knowledge_errors):
                for chunk in chunks(document):
                    value=score(keywords,chunk['heading']+' '+chunk['text'])
                    if value:knowledge.append(dict(chunk,score=value,reason='当前阅读范围内的任务词匹配'))
    assets.sort(key=lambda item:(-item['score'],item['id']));knowledge.sort(key=lambda item:(-item['score'],item['id']))
    if 'limit' not in request and (groups or library_errors or saved):
        knowledge_limit=6
    else:
        knowledge_limit=limit
    selected=select_passages([knowledge,saved,*groups],knowledge_limit)
    scope=dict(workflow=flow,source_kind=source_kind or 'all_enabled',per_document_passages=2,
               library_query_truncated=source_kind in (None,'library') and len(keywords.strip())>300,
               explicit_keywords='keywords' in request)
    result=dict(workflow=flow,query=query,size=size,assets=assets[:limit],knowledge=selected,errors=catalog['errors'],
                knowledge_errors=knowledge_errors,library_errors=library_errors,saved_web_errors=saved_errors,search_scope=scope,
                policy='Only current workspace assets and sources enabled for this workflow; local search never calls a provider.')
    if include_extensions:
        from nbt_asset_libraries import browse
        candidates=browse(workspace,query=keywords.strip()[:300],limit=limit)
        result.update(extension_candidates=candidates['items'],extension_errors=candidates['errors'],
                      extension_next='按返回的 source_id、version 和哈希用 asset-libraries preview 核对实际候选。')
    return result


def select_passages(groups, limit):
    per_doc,seen,selected={},set(),[]
    # Alternate between independently ranked sources, whose scores are not comparable.
    for row in zip_longest(*groups):
        for chunk in row:
            if chunk is None:
                continue
            key=chunk['document_id'];content=' '.join(chunk['text'].split())
            if per_doc.get(key,0)>=2 or content in seen:
                continue
            selected.append(chunk);per_doc[key]=per_doc.get(key,0)+1;seen.add(content)
            if len(selected)>=limit:
                return selected
    return selected

def checked_sources(workspace,flow,sources,*,audience='internal_ai'):
    if not isinstance(sources,list) or not 1<=len(sources)<=16 or len({item['id'] for item in sources})!=len(sources):raise ValueError('参考来源列表无效')
    docs=None;issues=[];references=[];external=[]
    for source in sources:
        if source['kind']=='asset':
            from nbt_components import load as load_component
            if flow!='component':raise ValueError('引用资产复用仅用于独立结构工作流')
            data=load_component(workspace,source['asset_id'])
            if data.get('archived') or data['content_sha256']!=source['content_sha256']:raise ValueError('引用资产已变化或已回收，请重新检索')
            if data['name']!=source['label'] or data['size']!=source['size'] or data['anchor']!=source['anchor'] or source['id']!='asset:'+source['asset_id'] or source['locator']!='.nbtcreator/components/'+source['asset_id']+'.json':raise ValueError('引用资产描述已变化，请重新检索')
            references.append({key:data[key] for key in ('name','size','anchor','palette','content_sha256')}|dict(id=source['asset_id']))
        elif source['kind']=='knowledge':
            if source['document_id'].startswith('web:'):
                from nbt_knowledge.web_research import read as read_web
                if source!=read_web(workspace,flow,source['document_id']):
                    raise ValueError('网络证据已变化，请重新选择')
                continue
            if source['document_id'].startswith('library:'):
                external.append(source)
                continue
            if docs is None:
                docs={item['id']:item for item in documents(workspace,flow,audience,issues)}
            doc=docs.get(source['document_id'])
            issue=next((item for item in issues if item['id']==source['document_id']),None)
            if issue:raise ValueError(f"引用资料 {issue['label']}（{issue['id']}）：{issue['error']}")
            if not doc or doc['sha256']!=source['sha256']:raise ValueError('引用资料已变化或已从工作流取消，请重新检索')
            current=next((chunk for chunk in chunks(doc) if chunk['id']==source['id']),None)
            if not current or any(current[key]!=source[key] for key in ('text','label','heading','locator','line_start','line_end','clipped')):raise ValueError('引用片段已变化，请重新检索')
        else:raise ValueError('引用种类无效')
    if external:libraries.verify_citations(workspace,flow,external)
    return references

def provider_result(bundle,references):
    sources=[];knowledge=[]
    for index,item in enumerate(bundle['sources']):
        citation='R'+str(index+1)
        descriptor={key:item[key] for key in ('kind','label')}
        descriptor.update(citation=citation,id=item['id'],sha256=item.get('sha256',item.get('content_sha256')))
        if item['kind']=='knowledge':
            fields=('heading','line_start','line_end','clipped','reference_type','library_name','manifest_sha256','passage_sha256','bibliography')
            descriptor.update({key:item[key] for key in fields if key in item})
            positions={key:item[key] for key in ('line_start','line_end') if key in item}
            knowledge.append(dict(citation=citation,label=item['label'],content=item['text'],sha256=item['sha256'],**positions))
        else:descriptor.update(asset_id=item['asset_id'],size=item['size'])
        sources.append(descriptor)
    return dict(workflow=bundle['workflow'],sources=sources,knowledge=knowledge,references=references,asset_written=False)

def receipt_file(workspace,identifier):
    if not isinstance(identifier,str) or not RECEIPT_ID.fullmatch(identifier):raise ValueError('检索回执编号无效')
    root=libraries.inside(workspace,workspace/'.nbtcreator/retrieval/queries')
    return libraries.inside(root,root/(identifier+'.json'))

def external_receipt(workspace,found):
    sources={f'R{index}':{key:value for key,value in item.items() if key not in ('thumbnail','saved')}
             for index,item in enumerate(found['knowledge']+found['assets'],1)}
    if not sources:return dict(found,receipt=None)
    raw=encode(dict(workflow=found['workflow'],query=found['query'],size=found['size'],sources=sources))
    identifier=digest(raw)[:32];file=receipt_file(workspace,identifier)
    with_existing=False
    if file.is_file():
        with file.open('rb') as stream:with_existing=stream.read(len(raw)+1)==raw
    if not with_existing:libraries.atomic(file,raw)
    refs={item['id']:ref for ref,item in sources.items()}
    def compact(item):
        fields=('label','heading','text','reason','reference_type','library_name','line_start','line_end','clipped','size','rotations','asset_id','content_sha256')
        projection=dict(ref=refs[item['id']],**{key:item[key] for key in fields if key in item})
        bibliography=item.get('bibliography',{})
        if bibliography:
            projection['bibliography']={key:bibliography[key] for key in ('author','edition','publisher','source_url','verification') if key in bibliography}
        return projection
    return dict(found,receipt=identifier,knowledge=[compact(item) for item in found['knowledge']],assets=[compact(item) for item in found['assets']])

def read_receipt(workspace,flow,request,audience):
    if audience!='external_agent':raise ValueError('外部检索回执不可用于内置 AI')
    file=receipt_file(workspace,request.get('receipt'))
    try:
        with file.open('rb') as stream:raw=stream.read(512*1024+1)
    except FileNotFoundError:raise ValueError('检索回执不存在，请在当前工作区重新检索') from None
    if len(raw)>512*1024 or digest(raw)[:32]!=file.stem:raise ValueError('检索回执已变化，请重新检索')
    data=json.loads(raw)
    if data['workflow']!=flow:raise ValueError('检索回执不属于本次工作流')
    return data

def source_window(result,request,*,bounded,default_line=1):
    if 'full' in request and type(request['full']) is not bool:raise ValueError('full 须为布尔值')
    if request.get('full') and 'line' in request:raise ValueError('请在全文和行号窗口之间择一')
    if request.get('full') or (not bounded and 'line' not in request):return result
    lines=result['text'].splitlines();line=request.get('line',default_line)
    if type(line) is not int or not 1<=line<=max(1,len(lines)):raise ValueError('资料原文行号无效')
    start=max(1,line-8);end=min(len(lines),line+28)
    while start<line and len('\n'.join(lines[start-1:line]))>12000:start+=1
    excerpt='\n'.join(lines[start-1:end])
    while end>line and len(excerpt)>12000:
        end-=1;excerpt='\n'.join(lines[start-1:end])
    return dict(result,text=excerpt[:12000],line_start=start,line_end=end,clipped=len(excerpt)>12000,
                next_line=end+1 if end<len(lines) else None)

def read_bundle(workspace,request,*,audience):
    workspace=Path(workspace).resolve()
    identifier=request.get('id');expected=request.get('sha256');flow=workflow(request)
    if not isinstance(identifier,str) or not RECEIPT_ID.fullmatch(identifier) or not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected):raise ValueError('参考集合编号或 SHA256 无效')
    base=libraries.inside(workspace,workspace/'.nbtcreator/retrieval/bundles')
    file=libraries.inside(base,base/(identifier+'.json'))
    try:
        with file.open('rb') as stream:raw=stream.read(256*1024+1)
    except FileNotFoundError:raise ValueError('参考集合不存在，请核对当前工作区与 id') from None
    if len(raw)>256*1024:raise ValueError('参考集合超过存储上限，请重新选择')
    if digest(raw)!=expected:raise ValueError('参考集合 SHA256 不匹配，请核对收到的 id 和 sha256')
    bundle=json.loads(raw);version=bundle.get('schema_version')
    if version not in (1,2,3) or bundle.get('workflow')!=flow:raise ValueError('参考集合不属于本次工作流')
    stored=bundle.get('audience') if version==3 else 'internal_ai'
    if stored not in AUDIENCES or (audience is not None and stored!=audience):raise ValueError('参考集合不属于当前资料范围')
    references=checked_sources(workspace,flow,bundle['sources'],audience=stored)
    return dict(id=identifier,sha256=expected,**provider_result(bundle,references))

def dispatch(workspace,action,request,*,audience='internal_ai'):
    workspace=Path(workspace).resolve()
    if not isinstance(request,dict):raise ValueError('检索请求须为JSON对象')
    if audience not in AUDIENCES:raise ValueError('未知检索范围')
    if action=='library':return libraries.manage(workspace,workflow(request),request)
    if action=='saved-web':
        from nbt_knowledge.saved_references import manage
        return manage(workspace,workflow(request),request)
    if action in ('research','import-web'):
        from nbt_knowledge.web_research import research, import_evidence
        from nbt_knowledge.saved_references import mark_research
        flow=workflow(request)
        result=(research if action=='research' else import_evidence)(workspace,flow,request)
        result['evidence']=mark_research(workspace,flow,result['evidence'])
        return result
    if action=='search':
        found=search(workspace,request,audience=audience)
        return external_receipt(workspace,found) if audience=='external_agent' else found
    if action=='source':
        flow=workflow(request);default_line=1
        if 'receipt' in request:
            snapshot=read_receipt(workspace,flow,request,audience)
            selected=snapshot['sources'].get(request.get('ref'))
            if not selected or selected['kind']!='knowledge':raise ValueError('请选择检索回执中的资料编号')
            checked_sources(workspace,flow,[selected],audience=audience)
            default_line=selected.get('line_start',1)
            request={**request,**{key:selected[key] for key in ('document_id','sha256','manifest_sha256') if key in selected}}
        identifier=request.get('document_id')
        if isinstance(identifier,str) and identifier.startswith('web:'):
            from nbt_knowledge.web_research import read as read_web
            result=read_web(workspace,flow,identifier)
            if result['sha256']!=request.get('sha256'):raise ValueError('网络证据哈希不匹配')
            return result
        if isinstance(identifier,str) and identifier.startswith('library:'):
            item,book,text=libraries.document(workspace,flow,identifier,request.get('manifest_sha256'),request.get('sha256'))
            result=dict(id=identifier,label=book['title'],sha256=book['sha256'],locator='library:'+item['name']+'/'+book['file'],
                        text=text,bibliography=libraries.bibliography(book))
            return source_window(result,request,bounded=audience=='external_agent',default_line=default_line)
        issues=[]
        for doc in documents(workspace,flow,audience,issues):
            if doc['id']==request.get('document_id') and doc['sha256']==request.get('sha256'):
                return source_window(doc,request,bounded=audience=='external_agent',default_line=default_line)
        issue=next((item for item in issues if item['id']==identifier),None)
        if issue:raise ValueError(f"资料 {issue['label']}（{identifier}）：{issue['error']}")
        raise ValueError('资料未选中或已变化')
    base=libraries.inside(workspace,workspace/'.nbtcreator/retrieval/bundles')
    if action=='bundle':
        flow=workflow(request);chosen=request.get('selected',[])
        if not isinstance(chosen,list) or not 1<=len(chosen)<=16 or any(not isinstance(key,str) for key in chosen) or len(set(chosen))!=len(chosen):raise ValueError('请选择1～16项参考')
        web=[key for key in chosen if key.startswith('web:')]
        available={}
        snapshot=None
        if 'receipt' in request:
            snapshot=read_receipt(workspace,flow,request,audience)
            available.update(snapshot['sources'])
        elif len(web)!=len(chosen):
            found=search(workspace,request,audience=audience)
            available.update({item['id']:item for item in found['assets']+found['knowledge']})
        if web:
            from nbt_knowledge.web_research import read as read_web
            available.update({key:read_web(workspace,flow,key) for key in web})
        if any(key not in available for key in chosen):raise ValueError('检索结果已变化，请重新检索并选择')
        sources=[{name:value for name,value in available[key].items() if name!='thumbnail'} for key in chosen]
        origin=snapshot if snapshot is not None else request
        bundle=dict(schema_version=3,audience=audience,workflow=flow,query=origin.get('query',''),size=origin.get('size'),sources=sources)
        references=checked_sources(workspace,flow,sources,audience=audience)
        if sum(len(item.get('text','')) for item in bundle['sources'])>24000:raise ValueError('选中的资料片段超过24000字，请减少参考')
        identifier=uuid.uuid4().hex;raw=encode(bundle);base.mkdir(parents=True,exist_ok=True)
        if len(raw)>256*1024:raise ValueError('参考集合超过存储上限，请减少参考')
        with (base/(identifier+'.json')).open('xb') as stream:stream.write(raw)
        return dict(id=identifier,sha256=digest(raw),**provider_result(bundle,references))
    if action=='read':
        return read_bundle(workspace,request,audience=audience)
    raise ValueError('未知检索操作')

def main():
    if sys.argv[1:2] == ['architecture']:
        from nbt_architecture_knowledge import main as architecture
        return architecture(sys.argv[2:])
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('action',choices=ACTIONS);parser.add_argument('--request',metavar='FILE|-',required=True,help='UTF-8 JSON 文件路径，或 - 表示标准输入');parser.add_argument('--audience',choices=AUDIENCES,default='external_agent');args=parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    try:print(json.dumps(dispatch(args.workspace,args.action,read_request(args.request),audience=args.audience),ensure_ascii=False));return 0
    except libraries.ERRORS as error:print(json.dumps(dict(error=str(error)),ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
