"""Exact bounded selection context and local-to-global operation compilation."""
import hashlib
import json
from pathlib import Path
from nbt_refine import read_master
from nbt_assembly import Volume
from nbt_recipes import translate_operation

ROOT=Path(__file__).resolve().parents[1]
CATALOG=json.loads((ROOT/'tool-catalog.json').read_text(encoding='utf8'))

def sha(file):return hashlib.sha256(Path(file).read_bytes()).hexdigest()

def load_selection(request,snapshot):
    source=Path(request['source']).resolve();source_hash=sha(source)
    if source_hash!=request.get('source_sha256'):raise ValueError('源建筑已变化，请重新打开')
    model,walls=read_master(source)
    snapshot_hash=sha(snapshot) if snapshot else None
    if snapshot:
        data=json.loads(Path(snapshot).read_text(encoding='utf-8-sig'))
        if data.get('source_sha256')!=source_hash or data.get('size')!=list(model.size):raise ValueError('选区快照不属于当前源')
        if data.get('preview_only'):
            from nbt_task import checked_preview_snapshot
            checked_preview_snapshot(snapshot)
            candidate=Volume(model.size)
            for p,value in data['master_blocks']:candidate.put(p,value)
            model=candidate;walls={tuple(p) for p in data['wall_positions']}
        if data.get('geometry_sha256')!=model.fingerprint():raise ValueError('选区快照几何不一致')
    if request.get('geometry_sha256') and request['geometry_sha256']!=model.fingerprint():raise ValueError('选区画面已变化，请重新生成')
    lo,hi=request.get('lo'),request.get('hi')
    if any(not isinstance(p,list) or len(p)!=3 or any(type(v) is not int for v in p) for p in (lo,hi)) or any(lo[i]<0 or lo[i]>hi[i] or hi[i]>=model.size[i] for i in range(3)):raise ValueError('选择模型边界内的整数XYZ范围')
    volume=1
    for i in range(3):volume*=hi[i]-lo[i]+1
    if volume>65536:raise ValueError('自然语言编辑每次选择至多65536格，请缩小选区；不会发送不完整数据')
    return source,source_hash,model,walls,lo,hi,snapshot_hash

def dispatch(action,request,snapshot=None):
    source,source_hash,model,walls,lo,hi,snapshot_hash=load_selection(request,snapshot)
    if action=='context':
        from nbt_registry import effective,normalize
        palette=[];ids={};runs=[];count=0
        points=sorted(((p,value) for p,value in model.blocks.items() if all(lo[i]<=p[i]<=hi[i] for i in range(3))),key=lambda pair:(pair[0][1],pair[0][2],pair[0][0]))
        for p,value in points:
            name,props=effective(value)
            if name in ('minecraft:air','minecraft:cave_air','minecraft:void_air'):continue
            value=normalize(dict(Name=name,Properties=props));id=ids.setdefault(value,len(palette))
            if id==len(palette):palette.append(value)
            x,y,z=[p[i]-lo[i] for i in range(3)];wall=1 if p in walls else 0;count+=1
            if runs and runs[-1][1:3]==[y,z] and runs[-1][0]+runs[-1][3]==x and runs[-1][4:]==[id,wall]:runs[-1][3]+=1
            else:runs.append([x,y,z,1,id,wall])
        result=dict(schema_version=1,geometry_sha256=model.fingerprint(),size=[hi[i]-lo[i]+1 for i in range(3)],palette=palette,runs=runs,solid_blocks=count,air_omitted=True)
        if len(runs)>4096 or len(palette)>512 or len(json.dumps(result).encode('utf8'))>128*1024:raise ValueError('选区方块数据过多，请缩小选区；未截断或发送部分数据')
    elif action=='compile':
        operations=request.get('operations');allowed=set(CATALOG['common'])
        if not isinstance(operations,list) or not 1<=len(operations)<=32:raise ValueError('选区编辑须有1～32个工具步骤')
        result=[];overwrite=request.get('allow_overwrite',True)
        if type(overwrite) is not bool:raise ValueError('覆盖开关须为布尔值')
        for index,raw in enumerate(operations):
            if not isinstance(raw,dict) or raw.get('kind') not in CATALOG['tools']:raise ValueError('选区编辑工具种类无效')
            kind=raw['kind'];fields=(allowed|set(CATALOG['tools'][kind][1])|{'kind','include_boxes'})-{'overwrite','write_group','write_bounds','max_writes'}
            if set(raw)-fields:raise ValueError('AI步骤含未开放字段，不能改变覆盖、保护或预算')
            operation=dict(raw);operation.setdefault('label','选区编辑 '+str(index+1));operation.setdefault('classification','inherit')
            if kind not in ('beam','auto_floor'):
                a,b=operation.get('lo'),operation.get('hi')
                if any(not isinstance(p,list) or len(p)!=3 or any(type(n) is not int for n in p) for p in (a,b)) or any(a[i]<0 or a[i]>b[i] or b[i]>hi[i]-lo[i] for i in range(3)):raise ValueError('工具读取/编辑区域超出当前局部选区')
            if kind=='auto_floor':
                a=operation.pop('lo',[0,0,0]);b=operation.pop('hi',[hi[i]-lo[i] for i in range(3)])
                operation.setdefault('include_boxes',[dict(lo=a,hi=b)])
            if 'overwrite' in CATALOG['tools'][kind][1]:operation['overwrite']=overwrite
            if 'max_writes' in CATALOG['tools'][kind][1]:operation['max_writes']=65536
            operation=translate_operation(operation,lo);operation['write_bounds']=dict(lo=lo,hi=hi,allow_overwrite=overwrite)
            result.append(operation)
        from nbt_detail_control import default_settings,compile_plan
        settings=default_settings();settings['operations']=result;compile_plan(settings,list(model.size))
        result=dict(operations=result,source_sha256=source_hash,geometry_sha256=model.fingerprint(),asset_written=False)
    else:raise ValueError('未知选区编辑操作')
    if sha(source)!=source_hash or snapshot and sha(snapshot)!=snapshot_hash:raise ValueError('读取期间源或快照已变化')
    return result

def main():
    import argparse
    from nbt_request_paths import read_request
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['context','compile']);parser.add_argument('--request',type=Path,required=True);parser.add_argument('--snapshot',type=Path);args=parser.parse_args()
    try:print(json.dumps(dispatch(args.action,read_request(args.request),args.snapshot),ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError) as error:print(json.dumps(dict(error=str(error)),ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
