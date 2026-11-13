"""Version-bound comment tasks. Original feedback and evidence remain untouched."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import unicodedata
import uuid
from datetime import datetime, timezone
from nbt_prompts import encode, digest, inside, relative, index_lock
from nbt_web_paths import project_paths
import nbt_agent_protocol as protocol

STATUSES=('todo','working','blocked','done')

def stamp():return datetime.now(timezone.utc).isoformat()

def workspace_file(workspace,value):
    target=(Path(workspace).resolve()/Path(value)).resolve()
    if not target.is_relative_to(Path(workspace).resolve()):raise ValueError('意见任务的证据须位于当前工作区')
    return target

def inventory(workspace,source):
    from nbt_feedback import collect
    report=collect(source,workspace);comments=[]
    for record in report['records']:
        binding=record['binding'];file=workspace_file(workspace,record['feedback_file'])
        assets=[{key:item[key] for key in ('role','sha256','status') if key in item}|({'path':relative(workspace,workspace_file(workspace,item['path']))} if item.get('path') else {}) for item in record['assets']]
        metadata={key:binding[key] for key in ('kind','source_sha256','geometry_sha256','image_sha256','snapshot_sha256','size') if key in binding}
        for note in record['notes']:
            key=digest(encode([relative(workspace,file),note['id'],metadata]))
            relevant=[item for item in assets if item['role'] in ('source','snapshot','image') or item['role'].startswith('reference:'+note['id']+':')]
            stable=dict(note=note,binding=metadata,assets=relevant,feedback_file=relative(workspace,file))
            evidence=dict(stable,feedback_sha256=record['feedback_sha256'])
            comments.append(dict(key=key,note_id=note['id'],number=note.get('number'),text=note.get('text',''),status=note.get('status','open'),
                                 kind=binding.get('kind','image'),view_name=Path(binding.get('image','')).name if binding.get('kind')!='3d' else '3D画面',geometry_sha256=binding['geometry_sha256'],image_sha256=binding.get('image_sha256'),
                                 anchors=note.get('anchors',[]) or ([dict(kind='image',**note['point'])] if note.get('point') else []),
                                 references=note.get('references',[]),verified=all(item['status']=='verified' for item in relevant) and not any(':' not in error or error.endswith(':'+note['id']) for error in record['errors']),geometry_matches_source=record['geometry_matches_source'],
                                 content_sha256=digest(encode(stable)),evidence_sha256=digest(encode(evidence)),evidence=evidence))
    if len(comments)>5000:raise ValueError('当前源意见超过5000条，请先按结构版本拆分整理')
    return report,comments

def locations(comment):
    prefix=comment['geometry_sha256']
    return sorted(set('3d:'+prefix+':'+json.dumps(anchor['position']) if anchor.get('kind')=='voxel' else
                      'image:'+prefix+':'+str(comment.get('image_sha256'))+':'+json.dumps([anchor.get('x'),anchor.get('y')])
                      for anchor in comment['anchors']))

def suggestions(comments):
    duplicates={};spatial={}
    for comment in comments:
        if comment['status']=='resolved' or not comment['verified']:continue
        text=' '.join(unicodedata.normalize('NFKC',comment['text']).split())
        scope=locations(comment) or [comment['kind']+':'+comment['geometry_sha256']+':'+str(comment.get('image_sha256'))+':whole']
        refs=sorted((item.get('sha256','') for item in comment['references']))
        faces=sorted(json.dumps([anchor.get('position'),anchor.get('normal')]) for anchor in comment['anchors'] if anchor.get('kind')=='voxel')
        identity=encode([text,scope,faces,refs]);duplicates.setdefault(identity,[]).append(comment['key'])
        for location in locations(comment):spatial.setdefault(location,[]).append(comment)
    overlaps={};truncated=False
    for notes in spatial.values():
        for i,a in enumerate(notes):
            for b in notes[i+1:]:
                if a['text']==b['text']:continue
                key=tuple(sorted((a['key'],b['key'])))
                if len(overlaps)>=2000 and key not in overlaps:truncated=True;continue
                overlaps[key]=dict(members=list(key),reason='相同标注位置有不同意见，需人工核对；不代表已经确认互相冲突。')
    return dict(duplicates=[members for members in duplicates.values() if len(members)>1],overlaps=list(overlaps.values()),overlaps_truncated=truncated)

def load_document(file,source,source_hash,workspace):
    if not file.exists():return dict(schema_version=1,source=relative(workspace,source),source_sha256=source_hash,revision=0,tasks=[],history=[])
    if file.stat().st_size>16*1024*1024:raise ValueError('意见任务索引超过16MiB，请归档后整理')
    data=json.loads(file.read_text(encoding='utf-8-sig'))
    if data.get('schema_version')!=1 or not isinstance(data.get('tasks'),list) or not isinstance(data.get('history'),list):raise ValueError('意见任务索引无效，未覆盖')
    if workspace_file(workspace,data.get('source',''))!=source or type(data.get('revision')) is not int:raise ValueError('意见任务索引不属于当前建筑')
    for task in data['tasks']:
        if not isinstance(task,dict) or not isinstance(task.get('id'),str) or not isinstance(task.get('title'),str) or not isinstance(task.get('category'),str) or task.get('status') not in STATUSES or not isinstance(task.get('members'),list) or not isinstance(task.get('conflicts'),list):raise ValueError('意见任务记录无效，未覆盖')
    return data

def evidence_file(directory,workspace,comment):
    target=inside(workspace,directory/'任务证据'/(comment['evidence_sha256']+'.json'));target.parent.mkdir(exist_ok=True)
    raw=encode(comment['evidence'])
    try:
        with target.open('xb') as stream:stream.write(raw)
    except FileExistsError:
        if digest(target.read_bytes())!=comment['evidence_sha256']:raise ValueError('已归档的原评论证据被改动')
    return dict(key=comment['key'],content_sha256=comment['content_sha256'],evidence_sha256=comment['evidence_sha256'],evidence_file=relative(workspace,target))

def view(workspace,source,data,comments,report):
    by_key={item['key']:item for item in comments};tasks=copy.deepcopy(data['tasks'])
    for task in tasks:
        task['evidence_updates']=[member['key'] for member in task['members'] if member['key'] not in by_key or by_key[member['key']].get('content_sha256',by_key[member['key']]['evidence_sha256'])!=member.get('content_sha256',member['evidence_sha256'])]
    overview=[]
    for item in comments:
        brief={key:value for key,value in item.items() if key!='evidence'}
        brief['anchors']=[{key:value for key,value in anchor.items() if key in ('kind','number','position','normal','x','y')} for anchor in item['anchors']]
        overview.append(brief)
    return dict(schema_version=1,source=relative(workspace,source),source_sha256=report['source_sha256'],stale=data['source_sha256']!=report['source_sha256'],revision=data['revision'],tasks=tasks,
                comments=overview,suggestions=suggestions(comments),history=data['history'],
                boundary='Task organization only; original feedback, evidence, model and approval remain separate.')

def dispatch(workspace,action,request):
    workspace=Path(workspace).resolve();source=inside(workspace,request['source']);source_hash=request.get('source_sha256')
    directory=inside(workspace,project_paths(source)['version']/'修改意见');file=directory/'意见任务.json'
    if action in ('list','evidence'):
        if digest(source.read_bytes())!=source_hash:protocol.error('SOURCE_CHANGED','源建筑已变化，请重新读取')
        report,comments=inventory(workspace,source)
    if action=='list':return view(workspace,source,load_document(file,source,source_hash,workspace),comments,report)
    if action=='evidence':
        data=load_document(file,source,source_hash,workspace);task=next((item for item in data['tasks'] if item['id']==request.get('id')),None)
        if not task:raise ValueError('意见任务不存在')
        offset=request.get('offset',0);limit=request.get('limit',50)
        if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=100:raise ValueError('原评论证据分页参数无效')
        records=[];checked={}
        for member in task['members'][offset:offset+limit]:
            target=inside(workspace,member['evidence_file']);raw=target.read_bytes()
            if not target.is_relative_to(directory/'任务证据') or digest(raw)!=member['evidence_sha256']:raise ValueError('原评论证据已缺失或被改动')
            record=json.loads(raw)
            from nbt_feedback import sha
            for asset in record['assets']:
                if not asset.get('path'):continue
                asset_path=workspace_file(workspace,asset['path']);key=(str(asset_path),asset.get('sha256'))
                if key not in checked:checked[key]=asset_path.is_file() and sha(asset_path)==asset.get('sha256')
                asset['status']='verified' if checked[key] else 'missing_or_changed'
            records.append(record)
        return dict(task=task,records=records,total=len(task['members']),offset=offset,next_offset=offset+limit if offset+limit<len(task['members']) else None,source_matches=data['source_sha256']==source_hash)
    if action not in ('create','update','merge'):raise ValueError('未知意见整理操作')
    directory.mkdir(parents=True,exist_ok=True)
    with index_lock(workspace,directory):
        data=load_document(file,source,source_hash,workspace)
        replayed=protocol.replay(workspace,data,'annotation-tasks.'+action,request)
        if replayed is not None:return replayed
        if digest(source.read_bytes())!=source_hash:protocol.error('SOURCE_CHANGED','源建筑已变化，请重新读取')
        report,comments=inventory(workspace,source);by_key={item['key']:item for item in comments}
        if data['source_sha256']!=source_hash:raise ValueError('已有任务属于旧源版本，保留旧记录；请在新版本重新整理')
        if request.get('revision')!=data['revision']:protocol.error('REVISION_CONFLICT','意见任务已被其他页面更新，请刷新后再操作',retryable=True,details={'current_revision':data['revision']})
        before=copy.deepcopy(data['tasks']);now=stamp()
        if action=='create':
            title=request.get('title','');category=request.get('category','其他')
            if not isinstance(title,str) or not isinstance(category,str):raise ValueError('任务标题与分类须为文字')
            title=title.strip();category=category.strip()
            if not title or len(title)>160 or not category or len(category)>40:raise ValueError('填写1～160字任务标题与1～40字分类')
            members=request.get('members')
            if not isinstance(members,list) or not 1<=len(members)<=200 or any(not isinstance(item,dict) or not isinstance(item.get('key'),str) for item in members) or len({item['key'] for item in members})!=len(members):raise ValueError('请选择1～200条不同的原评论')
            refs=[]
            for member in members:
                item=by_key.get(member.get('key'))
                if not item or member.get('evidence_sha256')!=item['evidence_sha256'] or not item['verified']:raise ValueError('所选原评论或证据已变化/缺失，请刷新后核对')
                live=workspace_file(workspace,item['evidence']['feedback_file'])
                if digest(live.read_bytes())!=item['evidence']['feedback_sha256']:raise ValueError('原评论正在更新，请刷新后再整理')
                refs.append(evidence_file(directory,workspace,item))
            data['tasks'].append(dict(id=uuid.uuid4().hex,title=title,category=category,status='todo',members=refs,conflicts=[],reason='',created_at=now,updated_at=now))
        elif action=='update':
            task=next((item for item in data['tasks'] if item['id']==request.get('id') and not item.get('merged_into')),None)
            if not task:raise ValueError('任务不存在或已合并')
            patch=request.get('patch',{})
            if not isinstance(patch,dict) or set(patch)-{'title','category','status','reason','conflicts'}:raise ValueError('任务更新字段无效')
            for key,value in patch.items():
                if key=='status' and value not in STATUSES:raise ValueError('任务状态无效')
                if key in ('title','category','reason') and (not isinstance(value,str) or len(value)>{'title':160,'category':40,'reason':2000}[key] or key!='reason' and not value.strip()):raise ValueError('任务文字字段无效')
                if key=='conflicts' and (not isinstance(value,list) or len(value)>100 or any(id==task['id'] or not any(other['id']==id and not other.get('merged_into') for other in data['tasks']) for id in value)):raise ValueError('关联冲突任务无效')
                task[key]=value
            task['updated_at']=now
        else:
            ids=request.get('ids',[])
            if not isinstance(ids,list) or not 2<=len(ids)<=100 or any(not isinstance(id,str) for id in ids) or len(set(ids))!=len(ids):raise ValueError('选择2～100个不同任务，首个为保留任务')
            tasks=[next((item for item in data['tasks'] if item['id']==id and not item.get('merged_into')),None) for id in ids]
            if any(item is None for item in tasks):raise ValueError('合并任务已变化，请刷新')
            target=tasks[0];known={(member['key'],member['evidence_sha256']) for member in target['members']}
            for task in tasks[1:]:
                for member in task['members']:
                    key=(member['key'],member['evidence_sha256'])
                    if key not in known:target['members'].append(member);known.add(key)
                task['merged_into']=target['id'];task['updated_at']=now
            target['status']='todo';target['updated_at']=now
        if digest(source.read_bytes())!=source_hash:raise ValueError('整理期间源建筑已变化，未更新任务')
        changed=[item for item in data['tasks'] if item not in before];old=[item for item in before if any(updated['id']==item['id'] for updated in changed)]
        event=dict(action=action,time=now,before=old,after=changed);raw=encode(event);history=directory/'任务历史';history.mkdir(exist_ok=True);event_file=inside(workspace,history/(digest(raw)+'.json'))
        try:
            with event_file.open('xb') as stream:stream.write(raw)
        except FileExistsError:
            if event_file.read_bytes()!=raw:raise ValueError('任务历史被改动')
        data['history'].append(dict(action=action,time=now,file=relative(workspace,event_file),sha256=digest(raw)));data['revision']+=1
        result=view(workspace,source,data,comments,report);protocol.receipt(workspace,data,'annotation-tasks.'+action,request,result)
        temporary=file.with_name(file.name+'.'+uuid.uuid4().hex+'.tmp');temporary.write_bytes(encode(data));temporary.replace(file)
        return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('action',choices=['list','create','update','merge','evidence']);parser.add_argument('--request',type=Path,required=True);args=parser.parse_args()
    try:print(json.dumps(dispatch(args.workspace,args.action,json.loads(args.request.read_text(encoding='utf-8-sig'))),ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError) as error:print(json.dumps(dict(error=str(error)),ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
