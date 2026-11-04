"""Mixed asset batches and hash-bound JSON lists in a dedicated workspace folder."""
import argparse,base64,gzip,hashlib,json,re,uuid
from pathlib import Path
import nbt_components as components
from nbt_refine import read_master,save_master
from nbt_project_batch import write

KIND='nbtcreator.asset-list'
LIMIT=100
MAX_BYTES=32*1024*1024

def base(workspace):
    workspace=Path(workspace).resolve();folder=workspace/'nbt_models/asset_batches'
    if not folder.resolve().is_relative_to(workspace):raise ValueError('批量资产目录越界')
    return folder

def local(workspace,value):
    if not isinstance(value,str) or not value or Path(value).is_absolute() or '..' in value.replace('\\','/').split('/'):raise ValueError('资产路径须为工作区相对路径')
    file=(Path(workspace).resolve()/value).resolve()
    if not file.is_relative_to(Path(workspace).resolve()) or not file.is_file():raise ValueError('资产文件缺失或超出工作区')
    return file

def sha(file):
    result=hashlib.sha256()
    with file.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):result.update(chunk)
    return result.hexdigest()
def relative(workspace,file):return file.resolve().relative_to(Path(workspace).resolve()).as_posix()
def bounded_json(file):
    if file.stat().st_size>MAX_BYTES:raise ValueError('JSON文件超过32MiB')
    return json.loads(file.read_text(encoding='utf-8-sig'))

def manifest(workspace,data):
    if not isinstance(data,dict) or data.get('schema_version')!=1 or data.get('kind')!=KIND or not isinstance(data.get('entries'),list) or not 1<=len(data['entries'])<=LIMIT:raise ValueError('资产清单须为nbtcreator.asset-list，包含1～100项')
    results=[];total=0;seen=set()
    for entry in data['entries']:
        if not isinstance(entry,dict) or entry.get('type') not in ('component','model') or not isinstance(entry.get('sha256'),str) or not re.fullmatch('[a-f0-9]{64}',entry['sha256']):raise ValueError('清单条目类型或哈希无效')
        file=local(workspace,entry.get('path'));key=str(file).casefold()
        if key in seen:raise ValueError('清单重复引用同一文件')
        seen.add(key);total+=file.stat().st_size
        if total>MAX_BYTES:raise ValueError('批量读取总量超过32MiB')
        if sha(file)!=entry['sha256']:raise ValueError('资产内容已变化：'+entry['path'])
        if entry['type']=='component':
            component=components.validate(bounded_json(file));summary=dict(name=component['name'],size=component['size'],content_sha256=component['content_sha256'],data=component)
        else:
            with gzip.open(file,'rb') as stream:payload=stream.read(256*1024*1024+1)
            if len(payload)>256*1024*1024:raise ValueError('解压后超过256MiB')
            model,walls=read_master(file);summary=dict(name=entry.get('name',file.stem),size=list(model.size),geometry_sha256=model.fingerprint(),data=dict(size=list(model.size),blocks=[[list(p),v] for p,v in sorted(model.blocks.items())],wall_positions=[list(p) for p in sorted(walls)]))
        if sha(file)!=entry['sha256']:raise ValueError('读取期间资产变化')
        results.append(dict(path=entry['path'],type=entry['type'],sha256=entry['sha256'],**summary))
    return results

def new_list(workspace,name,entries,identifier=None,errors=None):
    if not isinstance(name,str) or not name.strip() or len(name)>120:raise ValueError('批次名称须为1～120字')
    identifier=identifier or uuid.uuid4().hex;folder=base(workspace)/identifier
    if not folder.resolve().is_relative_to(base(workspace).resolve()):raise ValueError('批次路径越界')
    data=dict(schema_version=1,kind=KIND,id=identifier,name=name.strip(),path_base='workspace',entries=entries)
    file=folder/'assets.json';write(file,data)
    return dict(id=identifier,name=name.strip(),manifest=relative(workspace,file),entries=entries,errors=errors or [],count=len(entries),nbt_exported=False)

def register_components(workspace,items,name='生成资产'):
    workspace=Path(workspace).resolve();identifier=uuid.uuid4().hex;folder=base(workspace)/identifier;folder.mkdir(parents=True,exist_ok=False);entries=[]
    for number,item in enumerate(items):
        source=components.component_file(workspace,item['id']);data=components.load(workspace,item['id']);before=sha(source);target=folder/'items'/f'{number:03d}'/'asset.component.json';target.parent.mkdir(parents=True);target.write_bytes(source.read_bytes())
        if sha(target)!=before or sha(source)!=before:raise ValueError('归档期间源构件变化')
        entry=dict(type='component',name=data['name'],component_id=item['id'],path=relative(workspace,target),sha256=before,review_status=data.get('review_status','not_recorded'))
        image=source.with_suffix('.jpg')
        if image.is_file():
            preview=target.with_suffix('.jpg');preview.write_bytes(image.read_bytes());entry['thumbnail']=relative(workspace,preview)
        recipe=components.library_root(workspace)/'recipes'/(item['id']+'.json')
        if recipe.is_file():
            if recipe.stat().st_size>components.MAX_BYTES:raise ValueError('来源配方过大')
            file=target.parent/'recipe.json';file.write_bytes(recipe.read_bytes());entry['recipe']=relative(workspace,file)
        entries.append(entry)
    return new_list(workspace,name,entries,identifier)

def organize(workspace):
    items=components.listing(workspace);valid=items['items'];signature=hashlib.sha256(json.dumps(sorted((item['id'],item['content_sha256'],item['name'],item['tags'],item['archived']) for item in valid),ensure_ascii=False).encode()).hexdigest();file=base(workspace)/'organization.json'
    if file.is_file():
        previous=bounded_json(file)
        if previous.get('signature')==signature:
            for batch in previous['batches']:manifest(workspace,bounded_json(local(workspace,batch['manifest'])))
            return dict(previous,reused=True)
    batches=[register_components(workspace,valid[start:start+LIMIT],'现有资产归档 '+str(start//LIMIT+1)) for start in range(0,len(valid),LIMIT)]
    result=dict(signature=signature,count=len(valid),batches=batches,errors=items['errors'],original_ids_preserved=True,drafts_promoted=False,nbt_exported=False)
    write(file,result);return result

def dispatch(workspace,action,request):
    workspace=Path(workspace).resolve()
    if action=='organize':return organize(workspace)
    if action=='save':
        assets=request.get('assets')
        if not isinstance(assets,list) or not 1<=len(assets)<=LIMIT:raise ValueError('每批保存1～100项生成资产')
        from nbt_structure_agent import dispatch as agent
        items=[];errors=[]
        for number,arguments in enumerate(assets):
            try:items.append(agent(workspace,'structure_save',arguments))
            except Exception as error:errors.append(dict(index=number,error=str(error)))
        entries=[]
        for item in items:entries.extend(bounded_json(local(workspace,item['batch_manifest']))['entries'])
        batch=new_list(workspace,request.get('name','生成资产批次'),entries) if entries else None
        return dict(count=len(items),items=items,errors=errors,nbt_exported=False,batch_id=batch['id'] if batch else None,manifest=batch['manifest'] if batch else None)
    if action=='list':
        items=[]
        for file in sorted(base(workspace).glob('*/assets.json'),key=lambda p:p.stat().st_mtime_ns,reverse=True)[:100]:
            try:
                value=bounded_json(file);items.append(dict(id=file.parent.name,name=value['name'],count=len(value['entries']),manifest=relative(workspace,file)))
            except (OSError,ValueError,KeyError,TypeError):continue
        return dict(items=items,directory='nbt_models/asset_batches')
    if action=='read':
        data=request.get('manifest')
        if data is None:
            identifier=request.get('id','')
            if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('批次编号无效')
            data=bounded_json(base(workspace)/identifier/'assets.json')
        results=manifest(workspace,data)
        if request.get('include_data') is True and len(json.dumps(results,ensure_ascii=False).encode())>MAX_BYTES:raise ValueError('完整读取结果超过32MiB，请拆分批次')
        return dict(name=data.get('name','资产清单'),manifest=data,count=len(results),items=[item if request.get('include_data') is True else {k:v for k,v in item.items() if k!='data'} for item in results],nbt_exported=False)
    if action=='generate':
        scope=request.get('scope','components')
        if scope not in ('components','models','all'):raise ValueError('未知清单范围')
        entries=[]
        if scope in ('components','all'):
            for item in components.listing(workspace)['items']:
                if not item.get('archived'):entries.append(dict(type='component',name=item['name'],path=relative(workspace,Path(item['file'])),sha256=sha(Path(item['file']))))
        if scope in ('models','all'):
            from nbt_detail_control import catalog
            for item in catalog(workspace,index_only=True)['models']:
                file=Path(item['source']);entries.append(dict(type='model',name=item.get('name_zh') or item['name'],path=relative(workspace,file),sha256=sha(file)))
        if not 1<=len(entries)<=LIMIT:raise ValueError('此范围须包含1～100项；更多资产请拆分导入批次')
        manifest(workspace,dict(schema_version=1,kind=KIND,entries=entries))
        return new_list(workspace,request.get('name','资产清单'),entries)
    if action!='import':raise ValueError('未知资产批量操作')
    files=request.get('files',[]);paths=request.get('paths',[])
    if not isinstance(files,list) or not isinstance(paths,list) or not 1<=len(files)+len(paths)<=LIMIT:raise ValueError('每次选择1～100个资产文件')
    identifier=uuid.uuid4().hex;folder=base(workspace)/identifier;entries=[];errors=[];total=0
    sources=[]
    for value in paths:
        file=Path(value).resolve()
        if not file.is_file() or file.stat().st_size>MAX_BYTES:raise ValueError('导入文件缺失或过大')
        raw=file.read_bytes();total+=len(raw)
        if total>MAX_BYTES:raise ValueError('本次导入总量超过32MiB')
        sources.append((file.name,raw))
    for value in files:
        if not isinstance(value,dict) or not isinstance(value.get('name'),str) or not isinstance(value.get('base64'),str):raise ValueError('上传文件格式无效')
        if len(value['base64'])>MAX_BYTES*1.4:raise ValueError('上传文件过大')
        raw=base64.b64decode(value['base64'],validate=True);total+=len(raw)
        if total>MAX_BYTES:raise ValueError('本次导入总量超过32MiB')
        sources.append((value['name'],raw))
    folder.mkdir(parents=True,exist_ok=False)
    for index,(name,raw) in enumerate(sources):
        item_folder=folder/'items'/f'{index:03d}';item_folder.mkdir(parents=True)
        try:
            if not name or len(name)>250:raise ValueError('文件名无效')
            if name.lower().endswith('.json'):
                data=components.validate(json.loads(raw.decode('utf-8-sig')));stored=components.store(workspace,data);file=item_folder/'asset.component.json';write(file,data)
                entry=dict(type='component',name=data['name'],component_id=stored['id'])
            elif name.lower().endswith(('.nbt','.json.gz')):
                temporary=item_folder/('input.nbt' if name.lower().endswith('.nbt') else 'input.master.json.gz');temporary.write_bytes(raw)
                try:
                    with gzip.open(temporary,'rb') as stream:payload=stream.read(256*1024*1024+1)
                    if len(payload)>256*1024*1024:raise ValueError('解压后超过256MiB')
                    model,walls=read_master(temporary)
                finally:temporary.unlink(missing_ok=True)
                file=item_folder/'asset.master.json.gz';save_master(file,model,walls)
                write(item_folder/'room_description.json',dict(name_zh=name[:100],shape='standalone',size=list(model.size),master=file.name,version_name='批量导入候选',verification='pending_visual_review'))
                entry=dict(type='model',name=name[:100])
            else:raise ValueError('仅支持构件JSON、结构NBT和主模型JSON.GZ')
            entries.append(dict(entry,path=relative(workspace,file),sha256=sha(file)))
        except Exception as error:errors.append(dict(file=name,error=str(error) or '文件格式不支持'))
    result=new_list(workspace,request.get('name','批量导入'),entries,identifier,errors)
    write(folder/'import-report.json',result);return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('action',choices=['list','import','generate','read','save','organize']);parser.add_argument('--request',type=Path);parser.add_argument('--file',type=Path);parser.add_argument('--include-data',action='store_true');args=parser.parse_args()
    try:
        request=bounded_json(args.request) if args.request else {}
        if args.file:request['manifest']=bounded_json(args.file)
        if args.include_data:request['include_data']=True
        print(json.dumps(dict(ok=True,result=dispatch(args.workspace,args.action,request)),ensure_ascii=False));return 0
    except Exception as error:print(json.dumps(dict(ok=False,error=str(error)),ensure_ascii=False));return 1

if __name__=='__main__':raise SystemExit(main())
