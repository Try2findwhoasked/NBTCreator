"""Native tool-effect assets shared by UI and agents; previews never export NBT."""
import argparse,hashlib,json,uuid
from copy import deepcopy
from pathlib import Path
from nbt_project_batch import write
from nbt_recipes import json_data

def root(workspace):
    workspace=Path(workspace).resolve();folder=workspace/'nbt_models/asset_library/tool_effects'
    if not folder.resolve().is_relative_to(workspace):raise ValueError('效果库路径越界')
    return folder

def file_for(workspace,identifier):
    import re
    if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('效果资产编号无效')
    file=root(workspace)/identifier/'effect.json'
    if not file.resolve().is_relative_to(root(workspace).resolve()):raise ValueError('效果路径越界')
    return file

def fingerprint(data):return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def merged_settings(base,patch):
    result=deepcopy(base)
    for key,value in patch.items():result[key]={**result[key],**deepcopy(value)} if isinstance(value,dict) and isinstance(result.get(key),dict) else deepcopy(value)
    return result

def validate(data):
    from nbt_detail_control import default_settings,compile_plan
    from nbt_operation_parameters import validate_operation
    from nbt_capabilities import capabilities
    if not isinstance(data,dict) or set(data)-{'name','settings','tags','schema_version','asset_type','content_sha256','archived','id','source_recipe_id'}:raise ValueError('工具效果只接收名称、标签和配置数据')
    if data.get('schema_version',1)!=1 or data.get('asset_type','tool_effect')!='tool_effect':raise ValueError('效果资产版本或类型无效')
    name=data.get('name');settings=data.get('settings');tags=data.get('tags',[])
    if not isinstance(name,str) or not 1<=len(name.strip())<=80 or not isinstance(settings,dict):raise ValueError('请填写效果名称和配置')
    if not isinstance(tags,list) or len(tags)>16 or any(not isinstance(t,str) or not 1<=len(t)<=32 for t in tags):raise ValueError('效果标签无效')
    allowed=set(default_settings())-{'lo','hi','whole_region','max_changed_blocks'}
    if set(settings)-allowed:raise ValueError('效果不能保存源文件、选区、保护、导出阶段或预算权限')
    json_data(settings);defaults=default_settings();settings=deepcopy(settings)
    for key,value in settings.items():
        sample=defaults[key]
        if isinstance(sample,dict):
            if not isinstance(value,dict) or set(value)-set(sample):raise ValueError('未知效果面板参数：'+key)
        elif key=='operations':
            if not isinstance(value,list) or len(value)>128:raise ValueError('效果最多128步')
        elif type(value) is not type(sample):raise ValueError('效果参数类型无效：'+key)
    catalog=capabilities()
    for op in settings.get('operations',[]):
        if not isinstance(op,dict) or op.get('kind') not in catalog['tools']:raise ValueError('未知建模工具')
        fields={'kind',*catalog['common'],*catalog['operation_parameters'][op['kind']]['properties'],'include_boxes','mask_positions'}
        if set(op)-fields or set(op)&{'write_group','write_bounds','max_writes','overwrite'}:raise ValueError('效果步骤不能携带源绑定或覆盖权限')
        if op.get('enabled',True):validate_operation(op)
    defaults=merged_settings(defaults,settings);defaults.update(whole_region=False,lo=[4,3,4],hi=[28,11,28]);compile_plan(defaults,(294,294,294))
    archived=data.get('archived',False)
    if type(archived) is not bool:raise ValueError('回收状态无效')
    result=dict(schema_version=1,asset_type='tool_effect',name=name.strip(),tags=[t for t in dict.fromkeys(tags) if not t.isdecimal()],settings=settings,archived=archived)
    if data.get('source_recipe_id'):
        import re
        if not isinstance(data['source_recipe_id'],str) or not re.fullmatch('[a-f0-9]{32}',data['source_recipe_id']):raise ValueError('原配方编号无效')
        result['source_recipe_id']=data['source_recipe_id']
    result['content_sha256']=fingerprint(result)
    if data.get('content_sha256') and data['content_sha256']!=result['content_sha256']:raise ValueError('效果内容哈希不匹配')
    return result

def load(workspace,identifier):
    file=file_for(workspace,identifier)
    if file.stat().st_size>8*1024*1024:raise ValueError('效果资产超过8MiB')
    value=validate(json.loads(file.read_text(encoding='utf-8-sig')));recipe=file.parent/'source-recipe.json'
    if recipe.is_file() and recipe.stat().st_size<=8*1024*1024:value['source_recipe_id']=json.loads(recipe.read_text(encoding='utf8')).get('id')
    return dict(value,id=identifier)

def save(workspace,data):
    value=validate(data)
    source_recipe=None
    if value.get('source_recipe_id'):
        from nbt_recipes import load as recipe
        try:source_recipe=recipe(workspace,value['source_recipe_id'])
        except OSError:raise ValueError('原配方不在当前工作区，请先导入原配方或迁移整个工作区') from None
    identifier=uuid.uuid4().hex;file=file_for(workspace,identifier);write(file,value)
    if source_recipe:write(file.parent/'source-recipe.json',source_recipe)
    from nbt_asset_batches import new_list,relative,sha
    batch=new_list(workspace,value['name'],[dict(type='effect',name=value['name'],path=relative(workspace,file),sha256=sha(file),effect_id=identifier)])
    return dict(value,id=identifier,file=str(file),manifest=batch['manifest'],nbt_exported=False)

def preview(workspace,data):
    from nbt_assembly import Volume
    from nbt_refine import save_master
    from nbt_detail_control import default_settings,compile_plan,simulate_plan
    from nbt_task import write_snapshot
    from nbt_components import thumbnail
    directory=Path(workspace).resolve()/'nbt_models/_workspaces/effect_previews'/data['id']/uuid.uuid4().hex
    if not directory.resolve().is_relative_to(Path(workspace).resolve()):raise ValueError('样例目录越界')
    directory.mkdir(parents=True)
    model=Volume((48,16,48));model.box([0,0,0],[47,15,47],'stone_bricks');model.box([1,3,1],[46,14,46],'air');model.box([8,3,36],[39,10,37],'stone_bricks');model.box([30,3,30],[32,8,32],'stone_bricks')
    for lo,hi,material in [([12,2,12],[21,2,23],'stone'),([22,2,12],[31,2,23],'oak_planks'),([32,2,12],[41,2,23],'deepslate_tiles')]:model.box(lo,hi,material)
    model.box([34,3,30],[36,8,32],'oak_log[axis=y]')
    settings=merged_settings(default_settings(),data['settings']);
    if data.get('source_recipe_id'):
        from nbt_recipes import translate_operation
        bounds=[op.get('hi',[0,0,0]) for op in settings.get('operations',[])];maximum=[max([v[i] for v in bounds if isinstance(v,list) and len(v)==3 and all(type(n) in (int,float) for n in v)]+[0]) for i in range(3)];offset=[max(0,min([4,3,4][i],model.size[i]-1-maximum[i])) for i in range(3)]
        settings['operations']=[translate_operation(op,offset) for op in settings.get('operations',[])]
    for op in settings.get('operations',[]):
        if op.get('kind') in ('pattern','replace','weathering') and op.get('from_states'):
            from nbt_collision import collision_cells
            material=op['from_states'][0];cells,reason=collision_cells(material)
            if not reason and len(cells)==8:
                lo=op.get('lo',[4,3,4]);hi=op.get('hi',[20,10,5]);low=[max(1,lo[0]),max(3,lo[1]),max(1,lo[2])];high=[min(46,hi[0]),min(12,hi[1]),min(46,lo[2]+1)]
                if all(a<=b for a,b in zip(low,high)):model.box(low,high,material)
    for op in settings.get('operations',[]):
        if op.get('kind')=='weathering' and isinstance(op.get('floor'),dict):
            lo=op.get('lo',[4,3,4]);hi=op.get('hi',[24,6,24]);material=op.get('from_states',['stone_bricks'])[0]
            for level in op['floor'].get('levels',[]):
                if 1<=level<13:model.box([max(1,lo[0]),max(0,level-2),max(1,lo[2])],[min(46,hi[0]),level,min(46,hi[2])],material)
    settings['max_changed_blocks']=65536
    if settings['structure'].get('enabled'):settings.update(whole_region=False,lo=[4,3,4],hi=[28,11,28])
    candidate,walls,diff=simulate_plan(model,set(),compile_plan(settings,model.size),dict(mode='standalone',openings=[],start=[4.5,3,4.5],targets={'end':[24.5,3,24.5]},interior_probes=[[24,5,24]],max_changed_blocks=65536))
    camera=dict(id='effect',role='工具效果样例',eye=[65,43,-24],target=[24,4,24],up=[0,1,0],fov=55,cuts=[dict(axis='y',position=13,removed_side='above')])
    outputs={}
    for name,current,mask in [('before',model,set()),('after',candidate,walls)]:
        source=directory/(name+'.master.json.gz');save_master(source,current,mask);snapshot=directory/(name+'.json');write_snapshot(source,snapshot,cameras=[camera]);outputs[name+'_snapshot']=str(snapshot)
    palette=sorted(set(candidate.blocks.values()));index={value:i for i,value in enumerate(palette)}
    if palette:thumbnail(dict(size=list(model.size),palette=palette,blocks=[[*p,index[v],p in walls] for p,v in candidate.blocks.items() if p[1]<13]),directory/'thumbnail.jpg')
    return dict(outputs,cameras=[camera],thumbnail=str(directory/'thumbnail.jpg') if palette else None,changed_blocks=diff['changed_blocks'],sample_only=True,asset_written=False,nbt_exported=False,warning='样例预览，不代表在你的建筑上已通过检查；载入后仍需实际候选预览')

def dispatch(workspace,action,request):
    if action=='organize':
        from nbt_asset_organization import organize
        return organize(workspace)
    if action=='list':
        items=[];errors=[]
        for file in root(workspace).glob('*/effect.json'):
            try:items.append(load(workspace,file.parent.name))
            except Exception as error:errors.append(dict(file=str(file),error=str(error)))
        return dict(items=items,errors=errors)
    if action=='save':return save(workspace,request['asset'])
    data=load(workspace,request['id'])
    if request.get('content_sha256') and data['content_sha256']!=request['content_sha256']:raise ValueError('效果资产变化，请重新读取')
    if action=='get':return data
    if action=='preview':return preview(workspace,data)
    if action=='compile' and data['archived']:raise ValueError('请先恢复回收站中的效果')
    if action=='compile':
        settings=deepcopy(data['settings'])
        if data.get('source_recipe_id'):
            from nbt_recipes import vector,translate_operation
            if 'position' not in request:raise ValueError('配方效果需要提供局部放置原点position')
            settings['operations']=[translate_operation(op,vector(request['position'])) for op in settings.get('operations',[])]
        return dict(settings=settings,name=data['name'],content_sha256=data['content_sha256'],asset_written=False,nbt_exported=False)
    if action=='archive':
        if type(request.get('archived')) is not bool:raise ValueError('回收开关无效')
        data.pop('content_sha256');data['archived']=request['archived'];value=validate(data);write(file_for(workspace,data['id']),value);return dict(value,id=data['id'])
    raise ValueError('未知工具效果操作')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('action',choices=['list','save','get','preview','compile','archive','organize']);parser.add_argument('--request',type=Path);args=parser.parse_args()
    try:
        request=json.loads(args.request.read_text(encoding='utf-8-sig')) if args.request else {};print(json.dumps(dict(ok=True,result=dispatch(args.workspace,args.action,request)),ensure_ascii=False));return 0
    except Exception as error:print(json.dumps(dict(ok=False,error=str(error)),ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
