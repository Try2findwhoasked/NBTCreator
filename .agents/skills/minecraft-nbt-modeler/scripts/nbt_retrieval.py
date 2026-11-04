"""Local asset/reference search and immutable, workflow-bound AI reference bundles."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import uuid
from nbt_components import listing, load as load_component

ROOT=Path(__file__).resolve().parents[1]
CATALOG=json.loads((ROOT/'tool-catalog.json').read_text(encoding='utf8'))
FLOWS=json.loads((ROOT/'config/ai-style-schema.json').read_text(encoding='utf8'))['workflows']

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
    if not isinstance(selected,list) or len(selected)>105:raise ValueError('资料选择无效')
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

def tokens(query):
    chunks=re.findall(r'[a-z0-9_]+|[\u3400-\u9fff]+',query.lower());values=[]
    for chunk in chunks:
        values.append(chunk)
        if re.search('[\u3400-\u9fff]',chunk):values.extend(chunk[i:i+2] for i in range(len(chunk)-1))
    return list(dict.fromkeys(values))[:128]

def score(query,text):
    lowered=text.lower();terms=tokens(query)
    return sum(min(3,lowered.count(term))*(5 if len(term)>2 else 1) for term in terms)+(20 if query.lower() in lowered else 0)

def chunks(document):
    lines=document['text'].splitlines();start=0;heading=document['label']
    while start<len(lines):
        if lines[start].startswith('#'):heading=lines[start].lstrip('# ').strip()[:250]
        end=start;length=0
        while end<len(lines) and end-start<24:
            if end>start and lines[end].startswith('#'):break
            size=len(lines[end])+1
            if length+size>2600 and end>start:break
            length+=size;end+=1
        text='\n'.join(lines[start:end]);clipped=len(text)>2600;text=text[:2600]
        if text.strip():
            identifier='knowledge:'+document['id']+':'+document['sha256']+':'+str(start+1)+':'+str(end)
            yield dict(id=identifier,kind='knowledge',document_id=document['id'],label=document['label'],heading=heading,sha256=document['sha256'],locator=document['locator'],line_start=start+1,line_end=end,text=text,clipped=clipped)
        start=max(start+1,end)

def search(workspace,request):
    flow=workflow(request);query=request.get('query','')
    if not isinstance(query,str) or not query.strip() or len(query)>12000:raise ValueError('请输入1～12000字的本地检索要求')
    size=request.get('size')
    if size is not None and (not isinstance(size,list) or len(size)!=3 or any(type(n) is not int or not 1<=n<=65536 for n in size)):raise ValueError('目标尺寸须为正整数XYZ')
    limit=request.get('limit',12)
    if type(limit) is not int or not 1<=limit<=32:raise ValueError('检索数量须为1～32')
    assets=[];catalog=listing(workspace) if flow=='component' else dict(items=[],errors=[])
    for item in catalog['items'] if flow=='component' else []:
        if item.get('archived'):continue
        value=score(query,item['name']+' '+ ' '.join(item.get('tags',[])))
        if value<=0:continue
        rotations=[turn for turn in (0,1) if size is None or all(n<=size[i] for i,n in enumerate(item['size'] if turn==0 else [item['size'][2],item['size'][1],item['size'][0]]))]
        # Rotation swaps X/Z only; no implicit resizing or clipping.
        if not rotations:continue
        assets.append(dict(id='asset:'+item['id'],kind='asset',asset_id=item['id'],label=item['name'],tags=item['tags'],size=item['size'],anchor=item['anchor'],content_sha256=item['content_sha256'],score=value,rotations=rotations,reason='名称或标签匹配；尺寸可容纳'+('（需绕Y旋转90°）' if rotations==[1] else ''),locator='.nbtcreator/components/'+item['id']+'.json',thumbnail=item.get('thumbnail')))
    knowledge=[]
    for document in documents(workspace,flow):
        for chunk in chunks(document):
            value=score(query,chunk['heading']+' '+chunk['text'])
            if value:knowledge.append(dict(chunk,score=value,reason='本工作流已选资料中的任务词匹配'))
    assets.sort(key=lambda item:(-item['score'],item['id']));knowledge.sort(key=lambda item:(-item['score'],item['id']))
    per_doc={};selected=[]
    for chunk in knowledge:
        key=chunk['document_id']
        if per_doc.get(key,0)>=2:continue
        selected.append(chunk);per_doc[key]=per_doc.get(key,0)+1
        if len(selected)>=limit:break
    return dict(workflow=flow,query=query,size=size,assets=assets[:limit],knowledge=selected,errors=catalog['errors'],policy='Only current workspace assets and knowledge already selected for this workflow; local search never calls a provider.')

def checked_sources(workspace,flow,sources):
    if not isinstance(sources,list) or not 1<=len(sources)<=16 or len({item['id'] for item in sources})!=len(sources):raise ValueError('参考来源列表无效')
    docs={item['id']:item for item in documents(workspace,flow)};references=[]
    for source in sources:
        if source['kind']=='asset':
            if flow!='component':raise ValueError('引用资产复用仅用于独立结构工作流')
            data=load_component(workspace,source['asset_id'])
            if data.get('archived') or data['content_sha256']!=source['content_sha256']:raise ValueError('引用资产已变化或已回收，请重新检索')
            if data['name']!=source['label'] or data['size']!=source['size'] or data['anchor']!=source['anchor'] or source['id']!='asset:'+source['asset_id'] or source['locator']!='.nbtcreator/components/'+source['asset_id']+'.json':raise ValueError('引用资产描述已变化，请重新检索')
            references.append({key:data[key] for key in ('name','size','anchor','palette','content_sha256')}|dict(id=source['asset_id']))
        elif source['kind']=='knowledge':
            doc=docs.get(source['document_id'])
            if not doc or doc['sha256']!=source['sha256']:raise ValueError('引用资料已变化或已从工作流取消，请重新检索')
            current=next((chunk for chunk in chunks(doc) if chunk['id']==source['id']),None)
            if not current or any(current[key]!=source[key] for key in ('text','label','heading','locator','line_start','line_end','clipped')):raise ValueError('引用片段已变化，请重新检索')
        else:raise ValueError('引用种类无效')
    return references

def provider_result(bundle,references):
    sources=[];knowledge=[]
    for index,item in enumerate(bundle['sources']):
        citation='R'+str(index+1)
        descriptor={key:item[key] for key in ('kind','label')}
        descriptor.update(citation=citation,id=item['id'],sha256=item.get('sha256',item.get('content_sha256')))
        if item['kind']=='knowledge':
            descriptor.update({key:item[key] for key in ('heading','line_start','line_end','clipped')})
            knowledge.append(dict(citation=citation,label=item['label'],content=item['text'],sha256=item['sha256'],line_start=item['line_start'],line_end=item['line_end']))
        else:descriptor.update(asset_id=item['asset_id'],size=item['size'])
        sources.append(descriptor)
    return dict(workflow=bundle['workflow'],sources=sources,knowledge=knowledge,references=references,asset_written=False)

def dispatch(workspace,action,request):
    workspace=Path(workspace).resolve()
    if not isinstance(request,dict):raise ValueError('检索请求须为JSON对象')
    if action=='search':return search(workspace,request)
    if action=='source':
        flow=workflow(request)
        for doc in documents(workspace,flow):
            if doc['id']==request.get('document_id') and doc['sha256']==request.get('sha256'):return doc
        raise ValueError('资料未选中或已变化')
    base=(workspace/'.nbtcreator/retrieval/bundles').resolve()
    if action=='bundle':
        found=search(workspace,request);chosen=request.get('selected',[])
        if not isinstance(chosen,list) or not 1<=len(chosen)<=16 or len(set(chosen))!=len(chosen):raise ValueError('请选择1～16项参考')
        available={item['id']:item for item in found['assets']+found['knowledge']}
        if any(key not in available for key in chosen):raise ValueError('检索结果已变化，请重新检索并选择')
        bundle=dict(schema_version=1,workflow=found['workflow'],query=found['query'],size=found['size'],sources=[{name:value for name,value in available[key].items() if name!='thumbnail'} for key in chosen]);references=checked_sources(workspace,found['workflow'],bundle['sources'])
        if sum(len(item.get('text','')) for item in bundle['sources'])>24000:raise ValueError('选中的资料片段超过24000字，请减少参考')
        identifier=uuid.uuid4().hex;raw=encode(bundle);base.mkdir(parents=True,exist_ok=True)
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
        if bundle.get('schema_version')!=1 or bundle.get('workflow')!=flow:raise ValueError('参考集合不属于本次工作流')
        references=checked_sources(workspace,flow,bundle['sources']);return provider_result(bundle,references)
    raise ValueError('未知检索操作')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('action',choices=['search','source','bundle','read']);parser.add_argument('--request',type=Path,required=True);args=parser.parse_args()
    try:print(json.dumps(dispatch(args.workspace,args.action,read(args.request)),ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError) as error:print(json.dumps(dict(error=str(error)),ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
