"""Orthographic half-block silhouette comparison against explicit masks."""
from collections import Counter
import hashlib
import io
import json
import math
import os
from pathlib import Path
import tempfile

import numpy as np
from PIL import Image,ImageDraw

from nbt_collision import collision_cells
from nbt_composition.large_assembly import _workspace_path,assembly_source_matches,is_assembly_source,read_assembly,require_creative_workspace,verify_assembly_binding
from nbt_review.reference_views import MAX_MANIFEST,VIEW_AXES,_hash,_image_bytes,load_reference
from nbt_refine import binary_wall_mask_hash,digest,read_master


def _mask(workspace,record,size):
    if not isinstance(record,dict) or set(record)-{'file','sha256','threshold','ignore_file','ignore_sha256'} or not {'file','sha256','threshold'}<=set(record):
        raise ValueError('参考轮廓掩模字段无效')
    threshold=record['threshold']
    if type(threshold) is not int or not 1<=threshold<=255:raise ValueError('轮廓掩模阈值须为1至255')
    def read(name,sha):
        file=_workspace_path(workspace,name);raw,actual,_=_image_bytes(file)
        if actual!=size or _hash(raw)!=sha:raise ValueError('轮廓掩模哈希或尺寸不一致')
        with Image.open(io.BytesIO(raw)) as image:value=np.asarray(image.convert('L'))>=threshold
        return file,value
    file,foreground=read(record['file'],record['sha256'])
    if ('ignore_file' in record)!=('ignore_sha256' in record):raise ValueError('遮挡掩模需要路径和哈希')
    ignored=np.zeros_like(foreground,dtype=bool);checks=[(file,record['sha256'])]
    if 'ignore_file' in record:
        ignore_file,ignored=read(record['ignore_file'],record['ignore_sha256']);checks.append((ignore_file,record['ignore_sha256']))
    return foreground,ignored,checks


def _span(axis,lower,upper,origin,scale):
    negative=axis.startswith('-');name=axis[1:] if negative else axis;index='xyz'.index(name)
    a=origin+scale*lower[index]*(-1 if negative else 1)
    b=origin+scale*upper[index]*(-1 if negative else 1)
    low,high=sorted((a,b))
    return math.ceil(low-.5-1e-9),math.ceil(high-.5-1e-9)-1


def _project(model,views):
    images={name:Image.new('1',tuple(view['size']),0) for name,view in views.items()}
    drawers={name:ImageDraw.Draw(image) for name,image in images.items()}
    approximate=Counter();full=tuple((x,y,z) for x in (0,1) for y in (0,1) for z in (0,1))
    for position,value in model.blocks.items():
        cells,reason=collision_cells(value)
        if reason or not cells:
            approximate[(value,reason or 'noncolliding_visual_shape')]+=1
            if not cells:cells=full
        boxes=[((0,0,0),(1,1,1))] if len(cells)==8 and set(cells)==set(full) else [
            (tuple(v*.5 for v in cell),tuple((v+1)*.5 for v in cell)) for cell in cells]
        for local_lo,local_hi in boxes:
            lower=[position[i]+local_lo[i] for i in range(3)];upper=[position[i]+local_hi[i] for i in range(3)]
            for name,view in views.items():
                x0,x1=_span(view['u_axis'],lower,upper,view['origin'][0],view['pixels_per_block'])
                y0,y1=_span(view['v_axis'],lower,upper,view['origin'][1],view['pixels_per_block'])
                if x0<=x1 and y0<=y1:drawers[name].rectangle((x0,y0,x1,y1),fill=1)
    return {name:np.asarray(image,dtype=bool) for name,image in images.items()},[
        dict(state=state,reason=reason,count=count) for (state,reason),count in sorted(approximate.items())]


def _edge(mask):
    padded=np.pad(mask,1,constant_values=False)
    inside=padded[1:-1,1:-1]
    return inside & ~(padded[:-2,1:-1]&padded[2:,1:-1]&padded[1:-1,:-2]&padded[1:-1,2:])


def _dilate(mask,radius):
    height,width=mask.shape
    if not mask.any():return np.zeros_like(mask)
    if radius>=max(height,width):return np.ones_like(mask)
    xs=np.arange(width);ys=np.arange(height)
    left=np.maximum(0,xs-radius);right=np.minimum(width,xs+radius+1)
    horizontal=np.concatenate((np.zeros((height,1),dtype=np.int32),np.cumsum(mask,axis=1,dtype=np.int32)),axis=1)
    spread=(horizontal[:,right]-horizontal[:,left])>0
    del horizontal
    top=np.maximum(0,ys-radius);bottom=np.minimum(height,ys+radius+1)
    vertical=np.concatenate((np.zeros((1,width),dtype=np.int32),np.cumsum(spread,axis=0,dtype=np.int32)),axis=0)
    return (vertical[bottom,:]-vertical[top,:])>0


def _metrics(reference,model,ignored,radius,region=None):
    valid=~ignored
    if region is not None:valid=valid & region
    ref=reference & valid;actual=model & valid
    union=np.count_nonzero(ref|actual);intersection=np.count_nonzero(ref&actual)
    ref_edge=_edge(reference)&valid;model_edge=_edge(model)&valid
    ref_count=np.count_nonzero(ref_edge);model_count=np.count_nonzero(model_edge)
    ref_coverage=float(np.count_nonzero(ref_edge&_dilate(model_edge,radius))/ref_count) if ref_count else None
    model_coverage=float(np.count_nonzero(model_edge&_dilate(ref_edge,radius))/model_count) if model_count else None
    return dict(silhouette_iou=float(intersection/union) if union else None,
                reference_contour_coverage=ref_coverage,model_contour_coverage=model_coverage,
                reference_pixels=int(np.count_nonzero(ref)),model_pixels=int(np.count_nonzero(actual)),
                ignored_pixels=int(np.count_nonzero(ignored if region is None else ignored&region)),
                tolerance_pixels=radius,tolerance_metric='square_one_block')


def _regions(values,views):
    if not isinstance(values,list) or len(values)>128:raise ValueError('局部回投影范围无效')
    result=[];seen=set()
    for item in values:
        if not isinstance(item,dict) or set(item)!={'id','view','lo','hi'} or not isinstance(item['id'],str) or not item['id'] or len(item['id'])>80 or item['id'] in seen or item['view'] not in views:
            raise ValueError('局部回投影范围字段无效')
        lo,hi=item['lo'],item['hi'];size=views[item['view']]['size']
        if any(not isinstance(p,list) or len(p)!=2 or any(type(v) is not int for v in p) for p in (lo,hi)) or any(not 0<=lo[i]<=hi[i]<size[i] for i in range(2)):
            raise ValueError('局部回投影范围越界')
        seen.add(item['id']);result.append(item)
    return result


def compare_reference(workspace,request):
    workspace=require_creative_workspace(workspace)
    required={'source','source_sha256','reference','reference_sha256','masks','regions','output'}
    if not isinstance(request,dict) or set(request)!=required:raise ValueError('参考回投影请求字段无效')
    source=_workspace_path(workspace,request['source']);reference=_workspace_path(workspace,request['reference'])
    if digest(source)!=request['source_sha256']:raise ValueError('制作源哈希不一致')
    ref=load_reference(reference,request['reference_sha256']);views=ref['views']
    if not isinstance(request['masks'],dict) or set(request['masks'])!=set(VIEW_AXES):raise ValueError('须提供三视轮廓掩模')
    regions=_regions(request['regions'],views)
    destination=_workspace_path(workspace,request['output']);base=workspace/'nbt_models/_workspaces/reference-reviews'
    if not destination.is_relative_to(base) or destination==base or destination.exists() or destination.is_symlink():raise ValueError('回投影输出须为 reference-reviews 下的新目录')
    assembly=is_assembly_source(source);model,walls=read_assembly(source) if assembly else read_master(source)
    source_parts=[dict(file=name,sha256=sha) for name,sha in model._assembly_binding[2]] if assembly else None
    wall_hash=binary_wall_mask_hash(source)
    masks={};checks=[];normalized_masks={}
    for name in VIEW_AXES:
        foreground,ignored,items=_mask(workspace,request['masks'][name],views[name]['size'])
        masks[name]=(foreground,ignored);checks.extend(items)
        normalized_masks[name]=dict(request['masks'][name],file=items[0][0].relative_to(workspace).as_posix())
        if len(items)>1:normalized_masks[name]['ignore_file']=items[1][0].relative_to(workspace).as_posix()
    projected,approximate=_project(model,views);geometry=model.fingerprint()
    def recheck():
        if digest(source)!=request['source_sha256'] or binary_wall_mask_hash(source)!=wall_hash:raise ValueError('回投影期间制作源发生变化')
        if assembly:verify_assembly_binding(model)
        load_reference(reference,request['reference_sha256'])
        for file,sha in checks:
            if _hash(_image_bytes(file)[0])!=sha:raise ValueError('回投影期间轮廓掩模发生变化')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.projection-',dir=destination.parent) as temporary:
        stage=Path(temporary);(stage/'overlays').mkdir();results={};local=[]
        for name,view in views.items():
            foreground,ignored=masks[name];actual=projected[name];radius=int(math.ceil(view['pixels_per_block']))
            metrics=_metrics(foreground,actual,ignored,radius)
            with Image.open(reference.parent/view['file']) as image:base_image=np.asarray(image.convert('RGB'),dtype=np.uint8).copy()
            colors=np.zeros_like(base_image);active=(foreground|actual)&~ignored
            colors[foreground&~actual&~ignored]=[50,130,255]
            colors[actual&~foreground&~ignored]=[255,70,55]
            colors[foreground&actual&~ignored]=[55,205,110]
            base_image[active]=((base_image[active].astype(np.uint16)+colors[active].astype(np.uint16))//2).astype(np.uint8)
            base_image[ignored]=((base_image[ignored].astype(np.uint16)+np.array([255,210,40],dtype=np.uint16))//2).astype(np.uint8)
            output='overlays/'+name+'.png';Image.fromarray(base_image).save(stage/output)
            results[name]=dict(metrics=metrics,overlay=output,overlay_sha256=_hash((stage/output).read_bytes()),mask=normalized_masks[name])
            for region in (row for row in regions if row['view']==name):
                area=np.zeros_like(foreground,dtype=bool);lo,hi=region['lo'],region['hi'];area[lo[1]:hi[1]+1,lo[0]:hi[0]+1]=True
                local.append(dict(id=region['id'],view=name,lo=lo,hi=hi,metrics=_metrics(foreground,actual,ignored,radius,area)))
        record=dict(schema_version=1,kind='nbtcreator-reference-comparison',source=source.relative_to(workspace).as_posix(),
                    source_sha256=request['source_sha256'],geometry_sha256=geometry,wall_mask_sha256=wall_hash,
                    canvas_size=list(model.size),occupied_bounds=(dict(lo=[min(p[i] for p in model.blocks) for i in range(3)],
                    hi=[max(p[i] for p in model.blocks) for i in range(3)]) if model.blocks else None),
                    source_kind='assembly' if assembly else 'single',assembly_partitions=source_parts,
                    reference=reference.relative_to(workspace).as_posix(),reference_sha256=request['reference_sha256'],
                    views=results,regions=local,approximate_states=approximate,approval_created=False,
                    scope='Static half-block collision silhouettes; unsupported visual shapes are approximate. Not visual approval or game validation.')
        raw=(json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf8')
        if len(raw)>MAX_MANIFEST:raise ValueError('回投影报告过大')
        report=stage/'comparison.json';report.write_bytes(raw);recheck()
        try:destination.mkdir()
        except FileExistsError:raise ValueError('回投影输出目录已存在') from None
        os.rename(stage/'overlays',destination/'overlays');recheck();os.link(report,destination/'comparison.json')
    result=dict(record,report=str(destination/'comparison.json'),report_sha256=_hash(raw))
    verify_comparison(workspace,result['report'],result['report_sha256'])
    return result


def verify_comparison(workspace,report,expected_sha256):
    workspace=Path(workspace).resolve();report=_workspace_path(workspace,str(report))
    if report.stat().st_size>MAX_MANIFEST:raise ValueError('回投影报告过大')
    raw=report.read_bytes()
    if _hash(raw)!=expected_sha256:raise ValueError('回投影报告哈希不一致')
    data=json.loads(raw)
    if not isinstance(data,dict) or data.get('kind')!='nbtcreator-reference-comparison' or data.get('schema_version')!=1 or data.get('approval_created') is not False:
        raise ValueError('回投影报告格式或批准字段无效')
    source=_workspace_path(workspace,data['source']);reference=_workspace_path(workspace,data['reference'])
    if digest(source)!=data['source_sha256'] or binary_wall_mask_hash(source)!=data.get('wall_mask_sha256'):
        raise ValueError('回投影制作源已变化')
    if data.get('source_kind')=='assembly' and not assembly_source_matches(source,data['source_sha256'],data.get('assembly_partitions')):
        raise ValueError('回投影组装分区已变化')
    if is_assembly_source(source) != (data.get('source_kind')=='assembly'):raise ValueError('回投影源类型不一致')
    reference_data=load_reference(reference,data['reference_sha256'])
    if not isinstance(data.get('views'),dict) or set(data['views'])!=set(VIEW_AXES):raise ValueError('回投影视图无效')
    for name,view in data['views'].items():
        _mask(workspace,view['mask'],reference_data['views'][name]['size'])
        if view['overlay']!='overlays/'+name+'.png':raise ValueError('回投影图片路径无效')
        image=_workspace_path(workspace,str(report.parent/view['overlay']))
        if _hash(image.read_bytes())!=view['overlay_sha256']:raise ValueError('回投影图片哈希已变化')
    if digest(source)!=data['source_sha256'] or binary_wall_mask_hash(source)!=data.get('wall_mask_sha256'):
        raise ValueError('核对期间回投影制作源发生变化')
    if data.get('source_kind')=='assembly' and not assembly_source_matches(source,data['source_sha256'],data.get('assembly_partitions')):
        raise ValueError('核对期间回投影组装分区发生变化')
    load_reference(reference,data['reference_sha256'])
    for name,view in data['views'].items():
        _mask(workspace,view['mask'],reference_data['views'][name]['size'])
        if _hash((report.parent/view['overlay']).read_bytes())!=view['overlay_sha256']:raise ValueError('核对期间回投影图片发生变化')
    if report.read_bytes()!=raw:raise ValueError('回投影报告读取期间发生变化')
    return dict(valid=True,report=str(report),report_sha256=expected_sha256,approval_created=False,
                scope='Checks bound files and image hashes; does not recompute scores or grant visual approval')
