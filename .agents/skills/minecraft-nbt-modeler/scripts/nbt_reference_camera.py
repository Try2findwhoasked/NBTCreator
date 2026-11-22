"""Generate source-bound orthographic material cameras from registered views."""
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

from nbt_large_assembly import _workspace_path,assembly_source_matches,is_assembly_source,read_assembly,require_creative_workspace,verify_assembly_binding
from nbt_reference_views import MAX_MANIFEST,SHA,VIEW_AXES,_hash,load_reference
from nbt_refine import binary_wall_mask_hash,digest,read_master


def _axis(value):
    sign=-1 if value.startswith('-') else 1;name=value.lstrip('-');result=[0,0,0]
    result['xyz'.index(name)]=sign
    return result


def _cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]


def _lighting(value):
    if value is None:return None
    if not isinstance(value,dict) or set(value)!={'direction','temperature_kelvin','background','exposure'}:raise ValueError('光照参数字段无效')
    direction=value['direction'];background=value['background'];temperature=value['temperature_kelvin'];exposure=value['exposure']
    if not isinstance(direction,list) or len(direction)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1e6 for v in direction) or math.hypot(*direction)<1e-5:raise ValueError('光照方向无效')
    if not isinstance(background,list) or len(background)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in background):raise ValueError('背景 RGB 无效')
    if type(temperature) not in (int,float) or not math.isfinite(temperature) or not 1000<=temperature<=40000:raise ValueError('色温须为1000至40000 K')
    if type(exposure) not in (int,float) or not math.isfinite(exposure) or not .1<=exposure<=4:raise ValueError('曝光须为0.1至4')
    return dict(direction=list(direction),temperature_kelvin=temperature,background=list(background),exposure=exposure)


def _views(model,reference,lighting=None):
    result={}
    for name,view in reference['views'].items():
        right,down=_axis(view['u_axis']),_axis(view['v_axis'])
        up=[-v for v in down];direction=_cross(right,down)
        width,height=view['size'];scale=view['pixels_per_block'];height_world=height/scale
        if not .01<=height_world<=8192:raise ValueError('参考图尺度超出正交相机范围：'+name)
        target=[0.0,0.0,0.0]
        for axis,sign in enumerate(right):
            if sign:target[axis]=sign*(width/2-view['origin'][0])/scale
        for axis,sign in enumerate(down):
            if sign:target[axis]=sign*(height/2-view['origin'][1])/scale
        hidden=next(i for i,value in enumerate(direction) if value)
        if model.blocks:
            low=min(p[hidden] for p in model.blocks);high=max(p[hidden]+1 for p in model.blocks)
        else:low,high=0,model.size[hidden]
        target[hidden]=(low+high)/2
        distance=max(32.0,(high-low)*2+10)
        eye=[target[i]-direction[i]*distance for i in range(3)]
        camera=dict(id=name,role='登记参考'+name,eye=eye,target=target,up=up,
                    projection='orthographic',ortho_height=height_world,lighting='day',layer='all',cuts=[])
        if lighting is not None:camera['lighting_options']=lighting
        result[name]=dict(width=width,height=height,cameras=[camera])
    return result


def _read_source(workspace,source,expected):
    source=_workspace_path(workspace,source)
    if digest(source)!=expected:raise ValueError('制作源哈希不一致')
    assembly=is_assembly_source(source)
    model,_=read_assembly(source) if assembly else read_master(source)
    parts=[dict(file=name,sha256=sha) for name,sha in model._assembly_binding[2]] if assembly else None
    return source,model,assembly,parts,binary_wall_mask_hash(source)


def prepare_cameras(workspace,request):
    workspace=require_creative_workspace(workspace)
    required={'source','source_sha256','reference','reference_sha256','output'}
    if not isinstance(request,dict) or not required<=set(request) or set(request)-required-{'lighting_options'}:
        raise ValueError('参考相机请求字段无效')
    source,model,assembly,parts,wall_hash=_read_source(workspace,request['source'],request['source_sha256'])
    reference=_workspace_path(workspace,request['reference']);ref=load_reference(reference,request['reference_sha256'])
    destination=_workspace_path(workspace,request['output']);base=workspace/'nbt_models/_workspaces/reference-cameras'
    if not destination.is_relative_to(base) or destination==base or destination.exists() or destination.is_symlink():
        raise ValueError('相机输出须为 reference-cameras 下的新目录')
    lighting=_lighting(request.get('lighting_options'))
    generated=_views(model,ref,lighting);geometry=model.fingerprint()
    def recheck():
        if digest(source)!=request['source_sha256'] or binary_wall_mask_hash(source)!=wall_hash:raise ValueError('准备相机期间制作源发生变化')
        if assembly:verify_assembly_binding(model)
        load_reference(reference,request['reference_sha256'])
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.cameras-',dir=destination.parent) as temporary:
        stage=Path(temporary);(stage/'cameras').mkdir();entries={}
        for name,item in generated.items():
            file='cameras/'+name+'.json';raw=(json.dumps(item['cameras'],ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf8')
            (stage/file).write_bytes(raw);entries[name]=dict(file=file,sha256=_hash(raw),width=item['width'],height=item['height'])
        record=dict(schema_version=1,kind='nbtcreator-reference-cameras',source=source.relative_to(workspace).as_posix(),
                    source_sha256=request['source_sha256'],geometry_sha256=geometry,wall_mask_sha256=wall_hash,
                    source_kind='assembly' if assembly else 'single',assembly_partitions=parts,
                    reference=reference.relative_to(workspace).as_posix(),reference_sha256=request['reference_sha256'],
                    views=entries,approval_created=False)
        if lighting is not None:record['lighting_options']=lighting
        raw=(json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf8')
        if len(raw)>MAX_MANIFEST:raise ValueError('相机清单过大')
        bundle=stage/'cameras.json';bundle.write_bytes(raw);recheck()
        try:destination.mkdir()
        except FileExistsError:raise ValueError('相机输出目录已存在') from None
        os.rename(stage/'cameras',destination/'cameras');recheck();os.link(bundle,destination/'cameras.json')
    result=dict(record,bundle=str(destination/'cameras.json'),bundle_sha256=_hash(raw))
    verify_cameras(workspace,result['bundle'],result['bundle_sha256'])
    return result


def verify_cameras(workspace,bundle,expected_sha256):
    workspace=Path(workspace).resolve();bundle=_workspace_path(workspace,str(bundle))
    if not isinstance(expected_sha256,str) or not SHA.fullmatch(expected_sha256) or bundle.stat().st_size>MAX_MANIFEST:
        raise ValueError('相机清单或哈希无效')
    with bundle.open('rb') as stream:raw=stream.read(MAX_MANIFEST+1)
    if len(raw)>MAX_MANIFEST or _hash(raw)!=expected_sha256:raise ValueError('相机清单哈希不一致')
    data=json.loads(raw)
    if not isinstance(data,dict) or data.get('kind')!='nbtcreator-reference-cameras' or data.get('schema_version')!=1 or data.get('approval_created') is not False:
        raise ValueError('相机清单格式或批准字段无效')
    source,model,assembly,parts,wall_hash=_read_source(workspace,data['source'],data['source_sha256'])
    if (('assembly' if assembly else 'single')!=data.get('source_kind') or parts!=data.get('assembly_partitions') or
        wall_hash!=data.get('wall_mask_sha256') or model.fingerprint()!=data.get('geometry_sha256')):
        raise ValueError('相机绑定的制作源已变化')
    reference=_workspace_path(workspace,data['reference']);ref=load_reference(reference,data['reference_sha256'])
    if not isinstance(data.get('views'),dict) or set(data['views'])!=set(VIEW_AXES):raise ValueError('相机视图缺失')
    expected=_views(model,ref,_lighting(data.get('lighting_options')))
    checked=[]
    for name,entry in data['views'].items():
        if not isinstance(entry,dict) or set(entry)!={'file','sha256','width','height'} or entry['file']!='cameras/'+name+'.json':raise ValueError('相机文件路径无效')
        file=_workspace_path(workspace,str(bundle.parent/entry['file']))
        if file.stat().st_size>MAX_MANIFEST:raise ValueError('相机文件过大')
        with file.open('rb') as stream:content=stream.read(MAX_MANIFEST+1)
        if len(content)>MAX_MANIFEST:raise ValueError('相机文件过大')
        if (_hash(content)!=entry['sha256'] or json.loads(content)!=expected[name]['cameras'] or
            entry['width']!=expected[name]['width'] or entry['height']!=expected[name]['height']):
            raise ValueError('相机文件与登记参考不一致')
        checked.append((file,entry['sha256']))
    if digest(source)!=data['source_sha256'] or binary_wall_mask_hash(source)!=wall_hash:raise ValueError('核对期间制作源发生变化')
    if assembly and not assembly_source_matches(source,data['source_sha256'],parts):raise ValueError('核对期间组装分区发生变化')
    load_reference(reference,data['reference_sha256'])
    if bundle.read_bytes()!=raw or any(digest(file)!=sha for file,sha in checked):raise ValueError('核对期间相机文件或清单发生变化')
    return dict(valid=True,bundle=str(bundle),bundle_sha256=expected_sha256,approval_created=False)


def checked_registered_camera(workspace,bundle,expected_sha256,camera,width,height):
    """Bind one render input to a still-valid registered camera and its canvas."""
    workspace=Path(workspace).resolve()
    bundle=_workspace_path(workspace,str(bundle));camera=_workspace_path(workspace,str(camera))
    verify_cameras(workspace,bundle,expected_sha256)
    raw=bundle.read_bytes()
    if _hash(raw)!=expected_sha256:raise ValueError('登记相机清单发生变化')
    data=json.loads(raw);matches=[]
    for name,entry in data['views'].items():
        file=_workspace_path(workspace,str(bundle.parent/entry['file']))
        if file==camera:matches.append((name,entry))
    if len(matches)!=1:raise ValueError('相机文件不属于指定参考相机清单')
    name,entry=matches[0]
    if (width,height)!=(entry['width'],entry['height']):
        raise ValueError('渲染尺寸与参考图不一致；请使用登记的宽高')
    if digest(camera)!=entry['sha256']:raise ValueError('登记相机文件发生变化')
    return dict(bundle=bundle.relative_to(workspace).as_posix(),bundle_sha256=expected_sha256,view=name,
                camera_sha256=entry['sha256'],reference_sha256=data['reference_sha256'],
                registered_source_sha256=data['source_sha256'])
