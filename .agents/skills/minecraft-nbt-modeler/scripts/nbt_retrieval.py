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

def digest(raw):return hashlib.sha256(raw).hexdigest()
def encode(data):return (json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8')
def read(file,limit=512*1024):
    raw=file.read_bytes()
    if len(raw)>limit:raise ValueError('参考文件过大')
    return json.loads(raw.decode('utf-8-sig'))

def workflow(request):
    key=request.get('workflow')
    if key not in FLOWS:raise ValueError('请选择有效的AI工作流')
    return key

def documents(workspace,flow):
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

def search(workspace,request):
    flow=workflow(request);query=request.get('query','')
    if not isinstance(query,str) or not query.strip() or len(query)>12000:raise ValueError('请输入1～12000字的本地检索要求')
    size=request.get('size')
    if size is not None and (not isinstance(size,list) or len(size)!=3 or any(type(n) is not int or not 1<=n<=65536 for n in size)):raise ValueError('目标尺寸须为正整数XYZ')
    limit=request.get('limit',12)
    if type(limit) is not int or not 1<=limit<=32:raise ValueError('检索数量须为1～32')
    assets=[];catalog=dict(items=[],errors=[])
    if flow=='component':
        from nbt_components import listing
        catalog=listing(workspace)
    for item in catalog['items']:
        if item.get('archived'):continue
        value=score(query,item['name']+' '+ ' '.join(item.get('tags',[])))
        if value<=0:continue
        rotations=[turn for turn in (0,1) if size is None or all(n<=size[i] for i,n in enumerate(item['size'] if turn==0 else [item['size'][2],item['size'][1],item['size'][0]]))]
        # Rotation swaps X/Z only; no implicit resizing or clipping.
        if not rotations:continue
        assets.append(dict(id='asset:'+item['id'],kind='asset',asset_id=item['id'],label=item['name'],tags=item['tags'],size=item['size'],anchor=item['anchor'],content_sha256=item['content_sha256'],score=value,rotations=rotations,reason='名称或标签匹配；尺寸可容纳'+('（需绕Y旋转90°）' if rotations==[1] else ''),locator='.nbtcreator/components/'+item['id']+'.json',thumbnail=item.get('thumbnail')))
    groups,library_errors=libraries.search(workspace,flow,query,limit,request)
    knowledge=[];saved=[];saved_errors=[]
    if not request.get('filters') and not request.get('library_id'):
        from nbt_knowledge.saved_references import search as search_saved
        saved,saved_errors=search_saved(workspace,flow,query,limit)
        for document in documents(workspace,flow):
            for chunk in chunks(document):
                value=score(query,chunk['heading']+' '+chunk['text'])
                if value:knowledge.append(dict(chunk,score=value,reason='本工作流已选资料中的任务词匹配'))
    assets.sort(key=lambda item:(-item['score'],item['id']));knowledge.sort(key=lambda item:(-item['score'],item['id']))
    if 'limit' not in request and (groups or library_errors or saved):
        knowledge_limit=6
    else:
        knowledge_limit=limit
    selected=select_passages([knowledge,saved,*groups],knowledge_limit)
    return dict(workflow=flow,query=query,size=size,assets=assets[:limit],knowledge=selected,errors=catalog['errors'],library_errors=library_errors,saved_web_errors=saved_errors,policy='Only current workspace assets and sources enabled for this workflow; local search never calls a provider.')


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

def checked_sources(workspace,flow,sources):
    if not isinstance(sources,list) or not 1<=len(sources)<=16 or len({item['id'] for item in sources})!=len(sources):raise ValueError('参考来源列表无效')
    docs=None;references=[];external=[]
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
                docs={item['id']:item for item in documents(workspace,flow)}
            doc=docs.get(source['document_id'])
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

def dispatch(workspace,action,request):
    workspace=Path(workspace).resolve()
    if not isinstance(request,dict):raise ValueError('检索请求须为JSON对象')
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
    if action=='search':return search(workspace,request)
    if action=='source':
        flow=workflow(request)
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
            if 'line' in request:
                lines=text.splitlines();line=request['line']
                if type(line) is not int or not 1<=line<=len(lines):raise ValueError('书库原文行号无效')
                start=max(1,line-8);end=min(len(lines),line+28)
                excerpt='\n'.join(lines[start-1:end]);result.update(text=excerpt[:12000],line_start=start,line_end=end,clipped=len(excerpt)>12000)
            return result
        for doc in documents(workspace,flow):
            if doc['id']==request.get('document_id') and doc['sha256']==request.get('sha256'):return doc
        raise ValueError('资料未选中或已变化')
    base=(workspace/'.nbtcreator/retrieval/bundles').resolve()
    if action=='bundle':
        flow=workflow(request);chosen=request.get('selected',[])
        if not isinstance(chosen,list) or not 1<=len(chosen)<=16 or any(not isinstance(key,str) for key in chosen) or len(set(chosen))!=len(chosen):raise ValueError('请选择1～16项参考')
        web=[key for key in chosen if key.startswith('web:')]
        available={}
        if len(web)!=len(chosen):
            found=search(workspace,request)
            available.update({item['id']:item for item in found['assets']+found['knowledge']})
        if web:
            from nbt_knowledge.web_research import read as read_web
            available.update({key:read_web(workspace,flow,key) for key in web})
        if any(key not in available for key in chosen):raise ValueError('检索结果已变化，请重新检索并选择')
        sources=[{name:value for name,value in available[key].items() if name!='thumbnail'} for key in chosen]
        version=2 if any(item.get('reference_type') for item in sources) else 1
        bundle=dict(schema_version=version,workflow=flow,query=request.get('query',''),size=request.get('size'),sources=sources);references=checked_sources(workspace,flow,sources)
        if sum(len(item.get('text','')) for item in bundle['sources'])>24000:raise ValueError('选中的资料片段超过24000字，请减少参考')
        identifier=uuid.uuid4().hex;raw=encode(bundle);base.mkdir(parents=True,exist_ok=True)
        if len(raw)>256*1024:raise ValueError('参考集合超过存储上限，请减少参考')
        with (base/(identifier+'.json')).open('xb') as stream:stream.write(raw)
        return dict(id=identifier,sha256=digest(raw),**provider_result(bundle,references))
    if action=='read':
        identifier=request.get('id');expected=request.get('sha256');flow=workflow(request)
        if not re.fullmatch('[a-f0-9]{32}',str(identifier)) or not re.fullmatch('[a-f0-9]{64}',str(expected)):raise ValueError('参考集合编号无效')
        file=(base/(identifier+'.json')).resolve()
        if not file.is_relative_to(base):raise ValueError('参考集合路径越界')
        raw=file.read_bytes()
        if len(raw)>256*1024 or digest(raw)!=expected:raise ValueError('参考集合已变化，请重新选择')
        bundle=json.loads(raw)
        if bundle.get('schema_version') not in (1,2) or bundle.get('workflow')!=flow:raise ValueError('参考集合不属于本次工作流')
        references=checked_sources(workspace,flow,bundle['sources']);return provider_result(bundle,references)
    raise ValueError('未知检索操作')

def main():
    if sys.argv[1:2] == ['architecture']:
        from nbt_architecture_knowledge import main as architecture
        return architecture(sys.argv[2:])
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('action',choices=ACTIONS);parser.add_argument('--request',type=Path,required=True);args=parser.parse_args()
    try:print(json.dumps(dispatch(args.workspace,args.action,read(args.request)),ensure_ascii=False));return 0
    except libraries.ERRORS as error:print(json.dumps(dict(error=str(error)),ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
