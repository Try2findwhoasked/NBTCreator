"""Anonymous A/B image packets bound to actual renderer inputs and outputs."""
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import secrets
import tempfile

import numpy as np
from PIL import Image
from nbt_large_assembly import _workspace_path,require_creative_workspace
from nbt_reference_views import MAX_MANIFEST,SHA,_hash
from nbt_task import checked_preview_snapshot,preview_source_matches

MAX_IMAGE=64*1024*1024
MAX_SNAPSHOT=64*1024*1024
MAX_PIXELS=16_777_216
DIFF_GAIN=4


def _read(path,limit=MAX_MANIFEST):
    if not path.is_file() or path.stat().st_size>limit:raise ValueError('审阅输入不存在或过大')
    with path.open('rb') as stream:raw=stream.read(limit+1)
    if len(raw)>limit:raise ValueError('审阅输入过大')
    return raw


def _json(path,sha,limit=MAX_MANIFEST):
    if not isinstance(sha,str) or not SHA.fullmatch(sha):raise ValueError('审阅输入哈希无效')
    raw=_read(path,limit)
    if _hash(raw)!=sha:raise ValueError('审阅输入哈希不一致：'+path.name)
    try:return json.loads(raw)
    except (ValueError,UnicodeDecodeError):raise ValueError('审阅输入 JSON 无效') from None


def _child(workspace,root,name):
    if not isinstance(name,str) or not name or Path(name).name!=name or '/' in name or '\\' in name or ':' in name:
        raise ValueError('渲染文件名无效')
    return _workspace_path(workspace,str(root/name))


def _camera_matches(actual,requested):
    if not isinstance(actual,dict) or not isinstance(requested,dict):return False
    for key in ('eye','target','up'):
        a,b=actual.get(key),requested.get(key)
        if not isinstance(a,list) or not isinstance(b,list) or len(a)!=3 or len(b)!=3:return False
        if any(type(x) not in (int,float) or type(y) not in (int,float) or not math.isfinite(x) or not math.isfinite(y) or not math.isclose(x,y,rel_tol=1e-6,abs_tol=1e-4) for x,y in zip(a,b)):return False
    for key in ('fov','ortho_height'):
        a,b=actual.get(key),requested.get(key)
        if a is None or b is None:
            if a!=b:return False
        elif type(a) not in (int,float) or type(b) not in (int,float) or not math.isfinite(a) or not math.isfinite(b) or not math.isclose(a,b,rel_tol=1e-6,abs_tol=1e-4):return False
    return actual.get('projection','perspective')==requested.get('projection','perspective')


def _render(workspace,entry):
    if not isinstance(entry,dict) or set(entry)!={'manifest','sha256'}:raise ValueError('渲染清单绑定无效')
    manifest=_workspace_path(workspace,entry['manifest']);report=_json(manifest,entry['sha256']);folder=manifest.parent
    if not isinstance(report,dict) or report.get('status')!='complete' or report.get('snapshot_file')!='snapshot.json':
        raise ValueError('审阅需要完成的渲染清单')
    snapshot_file=_child(workspace,folder,report['snapshot_file'])
    snapshot=_json(snapshot_file,report['snapshot_sha256'],MAX_SNAPSHOT)
    source=_workspace_path(workspace,snapshot['source'])
    if (snapshot.get('source_sha256')!=report.get('source_sha256') or snapshot.get('geometry_sha256')!=report.get('geometry_sha256') or
        _workspace_path(workspace,report['source'])!=source or not preview_source_matches(source,snapshot)):
        raise ValueError('渲染制作源或分区已变化')
    if snapshot.get('preview_only'):checked_preview_snapshot(snapshot_file)
    # Only the source binding is needed below. Drop full voxel lists before reading the images.
    snapshot={key:snapshot[key] for key in ('source_sha256','binary_wall_mask_sha256','source_kind','assembly_partitions') if key in snapshot}
    camera=_workspace_path(workspace,report.get('camera_file'))
    if _hash(_read(camera))!=report.get('cameras_sha256'):raise ValueError('渲染相机文件已变化')
    views=report.get('views');images=report.get('images')
    if not isinstance(views,list) or not 1<=len(views)<=16 or not isinstance(images,list) or len(images)!=len(views):
        raise ValueError('审阅需要1至16个完整机位')
    width,height=report.get('width'),report.get('height')
    if type(width) is not int or type(height) is not int or width<1 or height<1 or width*height>MAX_PIXELS:
        raise ValueError('渲染尺寸超出审阅范围')
    camera_binding=report.get('reference_camera_binding')
    if camera_binding is not None:
        from nbt_reference_camera import checked_registered_camera
        if not isinstance(camera_binding,dict) or not camera_binding.get('bundle') or not camera_binding.get('bundle_sha256'):
            raise ValueError('登记相机绑定无效')
        bundle=_workspace_path(workspace,camera_binding['bundle'])
        if checked_registered_camera(workspace,bundle,camera_binding['bundle_sha256'],camera,width,height)!=camera_binding:
            raise ValueError('登记相机绑定已变化')
    loaded=[]
    for view,item in zip(views,images):
        if not isinstance(item,dict):raise ValueError('渲染图片清单无效')
        image=_child(workspace,folder,item.get('image'));metadata=_child(workspace,folder,item.get('metadata'))
        image_raw=_read(image,MAX_IMAGE)
        if _hash(image_raw)!=item.get('sha256'):raise ValueError('渲染图片哈希不一致')
        meta_raw=_read(metadata);meta=json.loads(meta_raw)
        if _hash(meta_raw)!=item.get('metadata_sha256'):raise ValueError('渲染元数据哈希不一致')
        if (not isinstance(meta,dict) or meta.get('id')!=view.get('id') or meta.get('requested_view')!=view or meta.get('image')!=item['image'] or
            meta.get('image_sha256')!=item['sha256'] or meta.get('snapshot_sha256')!=report['snapshot_sha256'] or
            meta.get('source_sha256')!=report['source_sha256'] or meta.get('geometry_sha256')!=report['geometry_sha256']):
            raise ValueError('渲染图片或机位元数据不一致')
        if (not _camera_matches(meta.get('camera'),view) or any(meta.get(key)!=view.get(key) for key in ('cuts','layer','lighting','lighting_options')) or
            any(meta.get(key)!=report.get(key) for key in ('quality','pixel_ratio','width','height'))):
            raise ValueError('渲染实际相机、光照或画幅与请求不一致')
        with Image.open(io.BytesIO(image_raw)) as decoded:
            if decoded.format!='PNG' or decoded.size!=(width,height):raise ValueError('渲染图片尺寸或格式不一致')
            decoded.verify()
        loaded.append(dict(image=image,image_sha256=item['sha256'],metadata=metadata,metadata_sha256=_hash(meta_raw),meta=meta))
    checks=[(manifest,entry['sha256'],MAX_MANIFEST),(snapshot_file,report['snapshot_sha256'],MAX_SNAPSHOT),
            (camera,report['cameras_sha256'],MAX_MANIFEST)]
    for item in loaded:
        checks.extend([(item['image'],item['image_sha256'],MAX_IMAGE),(item['metadata'],item['metadata_sha256'],MAX_MANIFEST)])
    if any(_hash(_read(file,limit))!=sha for file,sha,limit in checks) or not preview_source_matches(source,snapshot):
        raise ValueError('读取期间渲染证据发生变化')
    return dict(manifest=manifest,manifest_sha256=entry['sha256'],report=report,source=source,images=loaded)


def _pair(workspace,entries):
    if not isinstance(entries,list) or len(entries)!=2:raise ValueError('盲评需要两个渲染清单')
    rows=[_render(workspace,item) for item in entries];a,b=(item['report'] for item in rows)
    for key in ('width','height','quality','pixel_ratio','cameras_sha256','views','reference_camera_binding'):
        if a.get(key)!=b.get(key):raise ValueError('盲评机位、光照、画幅或相机绑定不一致：'+key)
    settings=('camera','cuts','layer','lighting','lighting_options','quality','pixel_ratio','width','height')
    for first,second in zip(rows[0]['images'],rows[1]['images']):
        if any(first['meta'].get(key)!=second['meta'].get(key) for key in settings):
            raise ValueError('盲评图片的实际相机或光照不一致')
    return rows


def _crop(value,width,height):
    if value is None:return [0,0,width,height]
    if not isinstance(value,list) or len(value)!=4 or any(type(v) is not int for v in value):raise ValueError('裁切须为四个整数像素边界')
    x0,y0,x1,y1=value
    if not 0<=x0<x1<=width or not 0<=y0<y1<=height:raise ValueError('裁切超出画幅')
    return list(value)


def _difference(first,second):
    delta=np.abs(first.astype(np.int16)-second.astype(np.int16))
    difference=np.empty_like(first)
    difference[:,:,:3]=np.minimum(delta[:,:,:3]*DIFF_GAIN,255).astype(np.uint8)
    alpha_changed=delta[:,:,3]!=0
    difference[alpha_changed,:3]=np.maximum(difference[alpha_changed,:3],np.array([255,0,255],dtype=np.uint8))
    difference[:,:,3]=255
    return difference,int(np.count_nonzero(np.any(delta!=0,axis=2)))


def _public(workspace,file,expected):
    data=_json(file,expected)
    if (not isinstance(data,dict) or set(data)!={'schema_version','kind','scope','crop','views','approval_created','boundary'} or
        data.get('kind')!='nbtcreator-blind-review' or data.get('schema_version')!=1 or data.get('approval_created') is not False or
        not isinstance(data.get('scope'),str) or not 1<=len(data['scope'])<=2000 or not isinstance(data.get('views'),list) or not 1<=len(data['views'])<=16):
        raise ValueError('匿名审阅包无效')
    for index,view in enumerate(data['views'],1):
        if (not isinstance(view,dict) or set(view)!={'id','settings','images','changed_pixels','difference_gain'} or view.get('id')!=f'view-{index:02d}' or
            not isinstance(view.get('settings'),dict) or not isinstance(view.get('images'),dict) or set(view['images'])!={'A','B','diff'} or
            type(view.get('changed_pixels')) is not int or view['changed_pixels']<0 or view.get('difference_gain')!=DIFF_GAIN):raise ValueError('匿名审阅图无效')
        for label,item in view['images'].items():
            expected_name=f'{label}/view-{index:02d}.png'
            if not isinstance(item,dict) or set(item)!={'file','sha256','size'} or item.get('file')!=expected_name:raise ValueError('匿名审阅图片路径无效')
            image=_workspace_path(workspace,str(file.parent/expected_name));raw=_read(image,MAX_IMAGE)
            if _hash(raw)!=item.get('sha256'):raise ValueError('匿名审阅图片哈希已变化')
            with Image.open(io.BytesIO(raw)) as decoded:
                if decoded.format!='PNG' or list(decoded.size)!=item.get('size'):raise ValueError('匿名审阅图片尺寸无效')
                decoded.verify()
    return data


def _validate_observations(workspace,decision,actor,observations,ids):
    if decision not in ('A','B','tie','inconclusive') or actor not in ('human','agent'):
        raise ValueError('盲评结论或来源无效')
    if not isinstance(observations,list) or not 1<=len(observations)<=128:raise ValueError('盲评须记录实际观察')
    normalized=[]
    for row in observations:
        required={'view','note','remaining'};optional={'part','reference_region','expected','recheck'}
        if (not isinstance(row,dict) or not required<=set(row) or set(row)-required-optional-{'reference'} or row['view'] not in ids or
            not isinstance(row['note'],str) or not 1<=len(row['note'].strip())<=4000 or
            not isinstance(row['remaining'],str) or len(row['remaining'])>4000 or
            any(not isinstance(row[key],str) or not 1<=len(row[key].strip())<=2000 for key in optional if key in row)):
            raise ValueError('盲评观察字段无效')
        entry=dict(row)
        if 'reference' in row:
            from nbt_reference_views import load_reference
            reference=row['reference']
            if not isinstance(reference,dict) or set(reference)!={'manifest','sha256','view','lo','hi'}:
                raise ValueError('盲评参考区域字段无效')
            manifest=_workspace_path(workspace,reference['manifest']);data=load_reference(manifest,reference['sha256'])
            view=reference['view'];lo=reference['lo'];hi=reference['hi']
            if (not isinstance(view,str) or view not in data['views'] or not isinstance(lo,list) or not isinstance(hi,list) or
                len(lo)!=2 or len(hi)!=2 or any(type(value) is not int for value in lo+hi) or
                any(lo[i]<0 or hi[i]<lo[i] or hi[i]>=data['views'][view]['size'][i] for i in range(2))):
                raise ValueError('盲评参考区域超出图像范围')
            entry['reference']=dict(manifest=manifest.relative_to(workspace).as_posix(),sha256=reference['sha256'],view=view,lo=lo,hi=hi)
        normalized.append(entry)
    return normalized


def prepare_review(workspace,request):
    workspace=require_creative_workspace(workspace)
    if not isinstance(request,dict) or set(request)!={'renders','scope','crop','output'} or not isinstance(request['scope'],str) or not 1<=len(request['scope'].strip())<=2000:
        raise ValueError('盲评请求或范围无效')
    destination=_workspace_path(workspace,request['output']);base=workspace/'nbt_models/_workspaces/reference-reviews'
    if not destination.is_relative_to(base) or destination==base or destination.exists() or destination.is_symlink():raise ValueError('盲评输出须为 reference-reviews 下的新目录')
    rows=_pair(workspace,request['renders']);width,height=rows[0]['report']['width'],rows[0]['report']['height']
    crop=_crop(request['crop'],width,height);assignment=[0,1] if secrets.randbelow(2)==0 else [1,0]
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.blind-',dir=destination.parent) as temporary:
        stage=Path(temporary);public=stage/'public';private=stage/'private'
        for name in ('A','B','diff'):(public/name).mkdir(parents=True,exist_ok=True)
        private.mkdir();views=[]
        for index,(first,second) in enumerate(zip(rows[assignment[0]]['images'],rows[assignment[1]]['images']),1):
            images={};pixels=[]
            for label,item in [('A',first),('B',second)]:
                with Image.open(item['image']) as decoded:
                    cropped=decoded.convert('RGBA').crop(tuple(crop))
                    clean=Image.frombytes('RGBA',cropped.size,cropped.tobytes())
                name=f'{label}/view-{index:02d}.png';clean.save(public/name)
                images[label]=dict(file=name,sha256=_hash((public/name).read_bytes()),size=list(clean.size))
                pixels.append(np.asarray(clean,dtype=np.uint8))
            difference,changed_pixels=_difference(*pixels)
            name=f'diff/view-{index:02d}.png';Image.fromarray(difference,'RGBA').save(public/name)
            images['diff']=dict(file=name,sha256=_hash((public/name).read_bytes()),size=[crop[2]-crop[0],crop[3]-crop[1]])
            meta=first['meta'];settings={key:meta[key] for key in ('camera','cuts','layer','lighting','lighting_options','quality','pixel_ratio') if key in meta}
            views.append(dict(id=f'view-{index:02d}',settings=settings,images=images,difference_gain=DIFF_GAIN,
                              changed_pixels=changed_pixels))
        public_data=dict(schema_version=1,kind='nbtcreator-blind-review',scope=request['scope'].strip(),crop=crop,views=views,
                         approval_created=False,boundary='Visual evidence only; no human confirmation or game validation')
        public_raw=(json.dumps(public_data,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf8')
        if len(public_raw)>MAX_MANIFEST:raise ValueError('匿名审阅清单过大')
        (public/'review.json').write_bytes(public_raw)
        private_data=dict(schema_version=1,kind='nbtcreator-blind-binding',public='public/review.json',public_sha256=_hash(public_raw),
                          renders=[dict(manifest=row['manifest'].relative_to(workspace).as_posix(),sha256=row['manifest_sha256']) for row in rows],
                          assignment=assignment,crop=crop,view_ids=[view['id'] for view in rows[0]['report']['views']])
        private_raw=(json.dumps(private_data,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf8')
        if len(private_raw)>MAX_MANIFEST:raise ValueError('盲评绑定过大')
        (private/'binding.json').write_bytes(private_raw)
        _public(workspace,public/'review.json',_hash(public_raw));_pair(workspace,request['renders'])
        try:destination.mkdir()
        except FileExistsError:raise ValueError('盲评输出目录已存在') from None
        os.rename(public,destination/'public');os.rename(private,destination/'private')
    result=dict(public=str(destination/'public/review.json'),public_sha256=_hash(public_raw),
                binding=str(destination/'private/binding.json'),binding_sha256=_hash(private_raw),
                views=len(views),approval_created=False)
    verify_review(workspace,result['binding'],result['binding_sha256'])
    return result


def record_review(workspace,request):
    workspace=require_creative_workspace(workspace)
    required={'public','public_sha256','decision','actor','observations','output'}
    if not isinstance(request,dict) or set(request)!=required:
        raise ValueError('盲评记录字段无效')
    public=_workspace_path(workspace,request['public']);data=_public(workspace,public,request['public_sha256'])
    observations=request['observations'];ids={item['id'] for item in data['views']}
    observations=_validate_observations(workspace,request['decision'],request['actor'],observations,ids)
    target=_workspace_path(workspace,request['output']);base=workspace/'nbt_models/_workspaces/reference-reviews'
    if not target.is_relative_to(base) or target==base or target.suffix.lower()!='.json' or target.exists() or target.is_symlink():raise ValueError('盲评记录须使用新的 JSON 路径')
    record=dict(schema_version=1,kind='nbtcreator-blind-observation',public=public.relative_to(workspace).as_posix(),public_sha256=request['public_sha256'],
                decision=request['decision'],actor=request['actor'],observations=observations,approval_created=False,
                boundary='Observation only; source freshness requires review-verify and this record is not user approval')
    raw=(json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf8')
    if len(raw)>MAX_MANIFEST:raise ValueError('盲评记录过大')
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.observation-',dir=target.parent) as temporary:
        staged=Path(temporary)/'record.json';staged.write_bytes(raw);_public(workspace,public,request['public_sha256'])
        _validate_observations(workspace,request['decision'],request['actor'],observations,ids)
        try:os.link(staged,target)
        except FileExistsError:raise ValueError('盲评记录已存在，未覆盖') from None
    return dict(record=str(target),record_sha256=_hash(raw),approval_created=False)


def verify_review(workspace,binding,expected_sha256,record=None,record_sha256=None):
    workspace=Path(workspace).resolve();binding=_workspace_path(workspace,str(binding));data=_json(binding,expected_sha256)
    if (not isinstance(data,dict) or set(data)!={'schema_version','kind','public','public_sha256','renders','assignment','crop','view_ids'} or
        data.get('kind')!='nbtcreator-blind-binding' or data.get('schema_version')!=1 or data.get('public')!='public/review.json' or data.get('assignment') not in ([0,1],[1,0])):
        raise ValueError('盲评绑定无效')
    public=_workspace_path(workspace,str(binding.parent.parent/data['public']));review=_public(workspace,public,data['public_sha256'])
    rows=_pair(workspace,data.get('renders'));crop=_crop(data.get('crop'),rows[0]['report']['width'],rows[0]['report']['height'])
    if crop!=review.get('crop') or data.get('view_ids')!=[view['id'] for view in rows[0]['report']['views']] or len(review['views'])!=len(rows[0]['images']):
        raise ValueError('盲评机位或裁切绑定不一致')
    for index,view in enumerate(review['views']):
        meta=rows[data['assignment'][0]]['images'][index]['meta']
        settings={key:meta[key] for key in ('camera','cuts','layer','lighting','lighting_options','quality','pixel_ratio') if key in meta}
        if view.get('settings')!=settings:raise ValueError('匿名审阅相机或机位元数据不一致')
        pixels=[]
        for label,original in [('A',rows[data['assignment'][0]]['images'][index]),('B',rows[data['assignment'][1]]['images'][index])]:
            image=_workspace_path(workspace,str(public.parent/view['images'][label]['file']))
            with Image.open(original['image']) as left,Image.open(image) as right:
                if left.convert('RGBA').crop(tuple(crop)).tobytes()!=right.convert('RGBA').tobytes():raise ValueError('匿名图片与原渲染像素不一致')
                pixels.append(np.asarray(right.convert('RGBA'),dtype=np.uint8))
        difference,changed_pixels=_difference(*pixels)
        diff_file=_workspace_path(workspace,str(public.parent/view['images']['diff']['file']))
        with Image.open(diff_file) as image:
            if image.convert('RGBA').tobytes()!=difference.tobytes():raise ValueError('匿名差异图与原渲染不一致')
        if view.get('changed_pixels')!=changed_pixels:raise ValueError('匿名差异像素统计不一致')
    if (record is None)!=(record_sha256 is None):raise ValueError('盲评记录和哈希须同时提供')
    if record is not None:
        file=_workspace_path(workspace,str(record));observation=_json(file,record_sha256)
        fields={'schema_version','kind','public','public_sha256','decision','actor','observations','approval_created','boundary'}
        if (not isinstance(observation,dict) or set(observation)!=fields or observation.get('schema_version')!=1 or
            observation.get('kind')!='nbtcreator-blind-observation' or observation.get('approval_created') is not False or
            observation.get('public_sha256')!=data['public_sha256'] or _workspace_path(workspace,observation.get('public'))!=public):
            raise ValueError('盲评记录不属于当前审阅包')
        if _validate_observations(workspace,observation['decision'],observation['actor'],observation['observations'],{item['id'] for item in review['views']})!=observation['observations']:
            raise ValueError('盲评参考区域路径未规范化')
    _public(workspace,public,data['public_sha256']);_pair(workspace,data['renders'])
    if _hash(_read(binding))!=expected_sha256:raise ValueError('核对期间盲评绑定发生变化')
    if record is not None:_validate_observations(workspace,observation['decision'],observation['actor'],observation['observations'],{item['id'] for item in review['views']})
    if record is not None and _hash(_read(file))!=record_sha256:raise ValueError('核对期间盲评记录发生变化')
    return dict(valid=True,binding=str(binding),binding_sha256=expected_sha256,record_checked=record is not None,
                approval_created=False,scope='Checks bound sources, camera, images and optional observation; no human approval or game validation')
