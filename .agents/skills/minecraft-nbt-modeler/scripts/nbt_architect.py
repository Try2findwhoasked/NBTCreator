"""Project design standards, delivery checks and version-bound human review tools."""
import argparse,copy,json,os
from pathlib import Path
from nbt_prompts import inside,relative,index_lock,encode,digest
from nbt_history import file_hash,now
from nbt_project_batch import write
from nbt_web_paths import project_paths

FIELDS={'name':'规范名称','materials':'材质与配色','dimensions':'尺度、层高与门窗','circulation':'道路与通行','style':'风格与构造','references':'参考资料说明','notes':'其他统一要求'}

def validate_standard(snapshot):
    if not isinstance(snapshot,dict) or snapshot.get('schema_version')!=1 or type(snapshot.get('revision')) is not int or snapshot['revision']<1:raise ValueError('项目规范快照无效')
    fields=snapshot.get('fields')
    if not isinstance(fields,dict) or set(fields)!=set(FIELDS) or any(not isinstance(value,str) or len(value)>4000 for value in fields.values()) or digest(encode(fields))!=snapshot.get('sha256'):raise ValueError('项目规范快照内容与哈希不符')

def read(file,default):
    if not file.exists():return copy.deepcopy(default)
    if file.stat().st_size>8*1024*1024:raise ValueError('工具记录超过8MiB')
    return json.loads(file.read_text(encoding='utf-8-sig'))

def standards(workspace,action,request):
    directory=inside(workspace,'nbt_models/_workspaces/project_design');file=directory/'standards.json'
    empty=dict(schema_version=1,revision=0,fields={key:'' for key in FIELDS})
    if action=='standards-get':return read(file,empty)
    directory.mkdir(parents=True,exist_ok=True)
    with index_lock(workspace,directory):
        previous=read(file,empty)
        if type(request.get('revision')) is not int or request['revision']!=previous['revision']:raise ValueError('项目规范已更新，请刷新后再保存')
        fields=request.get('fields')
        if not isinstance(fields,dict) or set(fields)!=set(FIELDS) or any(not isinstance(value,str) or len(value)>4000 for value in fields.values()):raise ValueError('规范字段无效，每项最多4000字')
        fields={key:value.strip() for key,value in fields.items()}
        if not fields['name']:raise ValueError('请填写规范名称')
        if fields==previous['fields']:return previous
        result=dict(schema_version=1,revision=previous['revision']+1,fields=fields,updated_at=now(),sha256=digest(encode(fields)))
        archive=directory/'revisions';archive.mkdir(exist_ok=True)
        archived=archive/(str(result['revision'])+'-'+result['sha256']+'.json')
        try:
            with archived.open('xb') as stream:stream.write(encode(result))
        except FileExistsError:
            recovered=read(archived,{})
            validate_standard(recovered)
            if recovered['revision']!=result['revision'] or recovered['fields']!=fields:raise ValueError('规范修订归档已变化，未覆盖')
            result=recovered
        write(file,result);return result

def delivery(workspace,value):
    source=inside(workspace,value)
    if source.is_relative_to(workspace/'nbt_models/_exports'):raise ValueError('请选择制作源，交付副本不可再次定稿')
    from nbt_finalize import release_path
    target=release_path(workspace,source);manifest=target/'release.json'
    result=dict(source=relative(workspace,source),absolute_source=str(source),name=project_paths(source)['workdir'].name,version=project_paths(source)['version'].name,output=relative(workspace,target),status='not_finalized',issues=[],file_count=0,game_verified=False)
    if not source.is_file():return dict(result,status='source_missing',issues=['制作源缺失'])
    result['source_sha256']=file_hash(source)
    if not manifest.is_file():return result
    record=read(manifest,{})
    if record.get('status')!='finalized' or not isinstance(record.get('files'),dict) or not record['files'] or record.get('master_relative') not in record['files']:raise ValueError('定稿清单无效或缺少完整 NBT 主模型')
    if record.get('source')!=result['source'] or record.get('source_sha256')!=result['source_sha256']:result['issues'].append('制作源与定稿时不同，请另存制作版后重新定稿')
    if len(record['files'])>10000:raise ValueError('单次交付超过10000个文件')
    for name,item in record['files'].items():
        file=inside(workspace,target/name)
        if not file.is_relative_to(target):raise ValueError('交付清单包含越界路径')
        if not file.is_file():result['issues'].append('缺失：'+name)
        elif not isinstance(item,dict) or file_hash(file)!=item.get('sha256'):result['issues'].append('内容变化：'+name)
    result['file_count']=len(record['files']);result['status']='changed' if result['issues'] else 'finalized'
    result['master']=relative(workspace,inside(workspace,target/record['master_relative']))
    return result

def cross(workspace,action,request):
    from nbt_feedback_tasks import inventory
    source=inside(workspace,request['source']);reference=inside(workspace,request['reference_source'])
    paths=project_paths(source);old=project_paths(reference)
    if paths['workdir']!=old['workdir'] or paths['version']==old['version']:raise ValueError('请在同一建筑的不同版本之间核对批注')
    source_sha=file_hash(source);reference_sha=file_hash(reference)
    if source_sha!=request.get('source_sha256'):raise ValueError('当前建筑已变化，请重新打开后核对')
    _,comments=inventory(workspace,reference)
    # Reviews are separate from formal annotations. Original anchors never become new-version anchors.
    directory=inside(workspace,paths['version']/'修改意见');file=directory/'跨版本核对.json'
    empty=dict(schema_version=1,revision=0,reviews={})
    def key(comment):return digest(encode([relative(workspace,source),source_sha,relative(workspace,reference),reference_sha,comment['key'],comment['content_sha256']]))
    def view(data):
        items=[]
        for comment in comments:
            review=data['reviews'].get(key(comment));item={k:copy.deepcopy(comment[k]) for k in ('key','content_sha256','text','anchors','kind','verified','geometry_matches_source')}
            valid=comment['verified'] and comment['geometry_matches_source'];item['review']=review if valid and review else dict(state='pending',note='');item['evidence_valid']=valid;items.append(item)
        return dict(source=relative(workspace,source),source_sha256=source_sha,reference_source=relative(workspace,reference),reference_sha256=reference_sha,revision=data['revision'],items=items,location='original_version_only',approval='not_granted_by_cross_review')
    if action=='cross-list':return view(read(file,empty))
    directory.mkdir(parents=True,exist_ok=True)
    with index_lock(workspace,directory):
        data=read(file,empty)
        if request.get('revision')!=data['revision']:raise ValueError('跨版本核对已更新，请刷新后再保存')
        if request.get('reference_sha256')!=reference_sha:raise ValueError('原版本已变化，请重新读取批注')
        comment=next((item for item in comments if item['key']==request.get('key')),None)
        if not comment or comment['content_sha256']!=request.get('content_sha256') or not comment['verified'] or not comment['geometry_matches_source']:raise ValueError('原批注或证据已变化，请重新核对')
        state=request.get('state');note=request.get('note','')
        if state not in ('pending','accepted','rejected','obsolete') or not isinstance(note,str) or len(note)>4000:raise ValueError('核对状态或备注无效')
        if file_hash(source)!=source_sha or file_hash(reference)!=reference_sha:raise ValueError('核对期间建筑已变化，未保存')
        data['reviews'][key(comment)]=dict(state=state,note=note,updated_at=now(),source=relative(workspace,source),source_sha256=source_sha,reference_source=relative(workspace,reference),reference_sha256=reference_sha,key=comment['key'],content_sha256=comment['content_sha256'])
        data['revision']+=1;write(file,data);return view(data)

def versions(workspace,request):
    source=inside(workspace,request['source']);paths=project_paths(source)
    if file_hash(source)!=request.get('source_sha256'):raise ValueError('当前建筑已变化，请重新打开')
    items=[]
    for directory,dirs,names in os.walk(paths['workdir'],followlinks=False):
        dirs[:]=[name for name in dirs if name not in {'Agent交接','修改意见','提示词方案','previews','validation','delivery','runtime','parts','_exports','_workspaces','.git'} and not (Path(directory)/name).is_symlink()]
        for name in names:
            if not (name.lower().endswith(('.snbt','.master.json.gz')) or name in {'master_geometry.json.gz','refined.master.json.gz'}):continue
            file=inside(workspace,Path(directory)/name);other=project_paths(file)
            if file.is_symlink() or other['workdir']!=paths['workdir'] or other['version']==paths['version']:continue
            items.append(dict(source=relative(workspace,file),absolute_source=str(file),version=other['version'].name,name=file.name))
            if len(items)>=200:return dict(versions=items,truncated=True)
    return dict(versions=sorted(items,key=lambda item:item['source'],reverse=True),truncated=False)

def dispatch(workspace,action,request):
    workspace=Path(workspace).resolve()
    if not isinstance(request,dict):raise ValueError('工具参数须为对象')
    if action in ('standards-get','standards-save'):return standards(workspace,action,request)
    if action=='deliveries':
        sources=request.get('sources',[])
        if not isinstance(sources,list) or len(sources)>300 or any(not isinstance(item,str) for item in sources):raise ValueError('每次最多核对300个建筑制作版本')
        items=[]
        for source in dict.fromkeys(sources):
            try:items.append(delivery(workspace,source))
            except (ValueError,OSError,KeyError,TypeError) as error:items.append(dict(source=source,status='unavailable',issues=[str(error)]))
        return dict(items=items,checked_at=now(),read_only=True)
    if action=='continue':
        item=delivery(workspace,request['source'])
        if item['status']!='finalized' or request.get('source_sha256')!=item['source_sha256']:raise ValueError('请先核对未变化的定稿版本，再继续制作')
        from nbt_history import dispatch as history
        recorded=history(workspace,'record',dict(source=item['source'],message='从定稿版继续制作',actor='human'))
        result=history(workspace,'derive',dict(id=recorded['version']['id'],message=request.get('message') or '从定稿版继续修改'))
        if file_hash(inside(workspace,item['source']))!=item['source_sha256']:raise ValueError('原稿在派生期间发生变化，请核对新版本')
        return dict(result,previous_release=item['output'],approval='not_granted_by_derivation')
    if action=='cross-list' and not request.get('reference_source'):return versions(workspace,request)
    if action in ('cross-list','cross-save'):return cross(workspace,action,request)
    raise ValueError('未知建筑师工具')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('action',choices=['standards-get','standards-save','deliveries','continue','cross-list','cross-save']);parser.add_argument('--request',type=Path);args=parser.parse_args()
    try:print(json.dumps(dispatch(args.workspace,args.action,read(args.request,{}) if args.request else {}),ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError) as error:print(json.dumps(dict(error=str(error)),ensure_ascii=False));return 1

if __name__=='__main__':raise SystemExit(main())
