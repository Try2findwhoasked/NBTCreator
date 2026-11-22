"""Hash-bound orthographic references and deterministic anchor-profile fitting."""
from bisect import bisect_right
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import tempfile

from PIL import Image
from nbt_large_assembly import _workspace_path, require_creative_workspace

MAX_MANIFEST=4*1024*1024
MAX_IMAGE=64*1024*1024
VIEW_AXES={'front':{'x','y'},'side':{'z','y'},'top':{'x','z'}}
IDENTIFIER=re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]{0,63}$')
SHA=re.compile(r'^[a-f0-9]{64}$')


def _hash(data):return hashlib.sha256(data).hexdigest()


def _numbers(value,count,label):
    if not isinstance(value,(list,tuple)) or len(value)!=count or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1_000_000 for v in value):
        raise ValueError(label+'需要有限数值')
    return [float(v) for v in value]


def _image_bytes(path):
    if not path.is_file() or path.stat().st_size>MAX_IMAGE:raise ValueError('参考图不存在或超过64MiB')
    with path.open('rb') as stream:raw=stream.read(MAX_IMAGE+1)
    if len(raw)>MAX_IMAGE:raise ValueError('参考图超过64MiB')
    try:
        with Image.open(io.BytesIO(raw)) as image:
            size=list(image.size);kind=image.format
            if kind not in ('PNG','JPEG','WEBP') or any(not 1<=v<=8192 for v in size) or size[0]*size[1]>32_000_000:
                raise ValueError('参考图格式或尺寸不支持')
            image.verify()
    except (OSError,Image.DecompressionBombError) as error:
        raise ValueError('参考图无法读取') from error
    return raw,size,{'PNG':'.png','JPEG':'.jpg','WEBP':'.webp'}[kind]


def _axis_value(axis,world):
    negative=axis.startswith('-');name=axis[1:] if negative else axis
    return world['xyz'.index(name)]*(-1 if negative else 1)


def _view_geometry(name,view,size):
    if not isinstance(view,dict):raise ValueError('参考视图须为对象')
    origin=_numbers(view.get('origin'),2,'参考图原点')
    scale=view.get('pixels_per_block')
    if type(scale) not in (int,float) or not math.isfinite(scale) or not .01<=scale<=1024:
        raise ValueError('参考图尺度无效')
    axes=[view.get('u_axis'),view.get('v_axis')]
    if any(not isinstance(axis,str) or axis not in ('x','-x','y','-y','z','-z') for axis in axes) or {axis.lstrip('-') for axis in axes}!=VIEW_AXES[name]:
        raise ValueError('参考图屏幕轴与视图方向不一致')
    return dict(size=list(size),origin=origin,pixels_per_block=float(scale),u_axis=axes[0],v_axis=axes[1])


def _view_provenance(view):
    origin_type=view.get('origin_type');basis=view.get('basis')
    if origin_type not in ('original','generated','derived') or not isinstance(basis,str) or not 1<=len(basis.strip())<=2000:
        raise ValueError('参考图来源类别或依据无效')
    return dict(origin_type=origin_type,basis=basis.strip())


def _anchors(values,views):
    if not isinstance(values,list) or not 1<=len(values)<=4096:raise ValueError('锚点数量无效')
    result=[];seen=set()
    for item in values:
        if not isinstance(item,dict) or set(item)!={'id','part','world','basis','confidence','uncertainty','views'}:
            raise ValueError('锚点字段无效')
        identifier=item['id'];part=item['part'];basis=item['basis'];confidence=item['confidence'];uncertainty=item['uncertainty']
        if not isinstance(identifier,str) or not IDENTIFIER.fullmatch(identifier) or identifier in seen or not isinstance(part,str) or not IDENTIFIER.fullmatch(part):
            raise ValueError('锚点或构件编号无效')
        if not isinstance(basis,str) or not 1<=len(basis.strip())<=2000 or confidence not in ('measured','estimated','generated'):
            raise ValueError('锚点依据或置信类别无效')
        if type(uncertainty) not in (int,float) or not math.isfinite(uncertainty) or not 0<=uncertainty<=256:
            raise ValueError('锚点不确定范围无效')
        world=_numbers(item['world'],3,'锚点坐标');observations=item['views']
        if not isinstance(observations,dict) or not observations or set(observations)-set(views):raise ValueError('锚点视图依据无效')
        normalized={}
        for name,position in observations.items():
            position=_numbers(position,2,'锚点像素');view=views[name]
            if any(position[i]<0 or position[i]>=view['size'][i] for i in range(2)):raise ValueError('锚点像素超出参考图')
            predicted=[view['origin'][i]+view['pixels_per_block']*_axis_value(view[key],world) for i,key in enumerate(('u_axis','v_axis'))]
            if math.dist(position,predicted)>view['pixels_per_block']*uncertainty+.51:
                raise ValueError('锚点与参考图配准不一致：'+identifier+'/'+name)
            normalized[name]=position
        result.append(dict(id=identifier,part=part,world=world,basis=basis.strip(),confidence=confidence,
                           uncertainty=float(uncertainty),views=normalized))
        seen.add(identifier)
    return result


def register_reference(workspace,request):
    workspace=require_creative_workspace(workspace)
    if not isinstance(request,dict) or set(request)!={'output','views','anchors','assumptions'}:
        raise ValueError('参考登记请求字段无效')
    supplied=request['views']
    if not isinstance(supplied,dict) or set(supplied)!=set(VIEW_AXES):raise ValueError('须分别登记正视、侧视和俯视图')
    destination=_workspace_path(workspace,request['output']);base=workspace/'nbt_models/_workspaces/reference-views'
    if not destination.is_relative_to(base) or destination==base or destination.exists() or destination.is_symlink():
        raise ValueError('参考输出须为 reference-views 下的新目录')
    assumptions=request['assumptions']
    if not isinstance(assumptions,list) or len(assumptions)>256 or any(not isinstance(item,str) or not 1<=len(item.strip())<=2000 for item in assumptions):
        raise ValueError('参考推定记录无效')
    views={};images={};originals=[]
    for name,view in supplied.items():
        if not isinstance(view,dict) or set(view)!={'image','sha256','origin','pixels_per_block','u_axis','v_axis','origin_type','basis'}:
            raise ValueError('参考视图字段无效')
        file=_workspace_path(workspace,view['image']);raw,size,extension=_image_bytes(file)
        if not isinstance(view['sha256'],str) or not SHA.fullmatch(view['sha256']) or _hash(raw)!=view['sha256']:
            raise ValueError('参考图哈希不一致：'+name)
        item=_view_geometry(name,view,size)|_view_provenance(view)
        item.update(file='images/'+name+extension,sha256=view['sha256'],source=file.relative_to(workspace).as_posix())
        views[name]=item;images[name]=raw;originals.append((file,view['sha256']))
    scales=[view['pixels_per_block'] for view in views.values()]
    if not all(math.isclose(scales[0],value,rel_tol=1e-9,abs_tol=1e-9) for value in scales[1:]):
        raise ValueError('三视图须使用同一方块尺度')
    anchors=_anchors(request['anchors'],views)
    record=dict(schema_version=1,kind='nbtcreator-orthographic-reference',views=views,anchors=anchors,
                assumptions=[item.strip() for item in assumptions])
    raw=(json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf8')
    if len(raw)>MAX_MANIFEST:raise ValueError('参考登记资料过大')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.reference-',dir=destination.parent) as temporary:
        stage=Path(temporary);(stage/'images').mkdir()
        for name,view in views.items():(stage/view['file']).write_bytes(images[name])
        manifest=stage/'reference.json';manifest.write_bytes(raw)
        load_reference(manifest,_hash(raw))
        if any(_hash(_image_bytes(file)[0])!=sha for file,sha in originals):raise ValueError('登记期间参考图发生变化')
        try:destination.mkdir()
        except FileExistsError:raise ValueError('参考输出目录已存在') from None
        os.rename(stage/'images',destination/'images')
        if any(_hash(_image_bytes(file)[0])!=sha for file,sha in originals):raise ValueError('发布期间参考图发生变化')
        os.link(manifest,destination/'reference.json')
        load_reference(destination/'reference.json',_hash(raw))
    return dict(manifest=str(destination/'reference.json'),manifest_sha256=_hash(raw),views=3,anchors=len(anchors),approval_created=False)


def load_reference(manifest,expected_sha256):
    manifest=Path(manifest)
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size>MAX_MANIFEST or not isinstance(expected_sha256,str) or not SHA.fullmatch(expected_sha256):
        raise ValueError('参考清单或哈希无效')
    manifest=manifest.resolve()
    with manifest.open('rb') as stream:raw=stream.read(MAX_MANIFEST+1)
    if len(raw)>MAX_MANIFEST or _hash(raw)!=expected_sha256:raise ValueError('参考清单哈希不一致')
    try:data=json.loads(raw)
    except (ValueError,UnicodeDecodeError):raise ValueError('参考清单无效') from None
    if not isinstance(data,dict) or set(data)!={'schema_version','kind','views','anchors','assumptions'} or data['schema_version']!=1 or data['kind']!='nbtcreator-orthographic-reference':
        raise ValueError('参考清单类型无效')
    views=data['views']
    if not isinstance(views,dict) or set(views)!=set(VIEW_AXES):raise ValueError('参考视图缺失')
    checked=[]
    for name,view in views.items():
        if not isinstance(view,dict) or set(view)!={'size','origin','pixels_per_block','u_axis','v_axis','origin_type','basis','file','sha256','source'}:
            raise ValueError('参考视图字段无效')
        if not isinstance(view.get('file'),str) or '\\' in view['file'] or ':' in view['file']:
            raise ValueError('参考图路径无效')
        relative=PurePosixPath(view['file'])
        if len(relative.parts)!=2 or relative.parts[0]!='images' or relative.stem!=name or relative.suffix not in ('.png','.jpg','.webp'):
            raise ValueError('参考图路径无效')
        image=manifest.parent
        for part in relative.parts:
            image=image/part
            if image.is_symlink() or (hasattr(image,'is_junction') and image.is_junction()):raise ValueError('参考图路径不能包含符号链接')
        if not image.resolve().is_relative_to(manifest.parent):raise ValueError('参考图路径越界')
        image_raw,size,_=_image_bytes(image)
        if size!=view['size'] or _hash(image_raw)!=view['sha256']:raise ValueError('参考图哈希或尺寸已变化：'+name)
        _view_geometry(name,view,size)
        _view_provenance(view)
        checked.append((image,view['sha256']))
    scales=[view['pixels_per_block'] for view in views.values()]
    if not all(math.isclose(scales[0],value,rel_tol=1e-9,abs_tol=1e-9) for value in scales[1:]):raise ValueError('三视图尺度不一致')
    _anchors(data['anchors'],views)
    if not isinstance(data['assumptions'],list) or len(data['assumptions'])>256 or any(not isinstance(x,str) or not 1<=len(x)<=2000 for x in data['assumptions']):raise ValueError('参考推定记录无效')
    with manifest.open('rb') as stream:unchanged=stream.read(MAX_MANIFEST+1)==raw
    if not unchanged or any(_hash(_image_bytes(image)[0])!=sha for image,sha in checked):raise ValueError('参考清单或图片读取期间发生变化')
    return data


def _slopes(heights,values):
    delta=[(values[i+1]-values[i])/(heights[i+1]-heights[i]) for i in range(len(heights)-1)]
    slopes=[delta[0]]
    for i in range(1,len(heights)-1):
        left,right=delta[i-1],delta[i]
        if left*right<=0:slopes.append(0.0);continue
        a=heights[i]-heights[i-1];b=heights[i+1]-heights[i]
        slopes.append((3*(a+b))/((2*b+a)/left+(b+2*a)/right))
    return slopes+[delta[-1]]


def fit_profile(request):
    if not isinstance(request,dict) or set(request)!={'reference','reference_sha256','part','rows','sample_step','vertices'}:
        raise ValueError('截面拟合请求字段无效')
    reference=load_reference(request['reference'],request['reference_sha256'])
    part=request['part'];rows=request['rows'];step=request['sample_step'];count=request['vertices']
    if not isinstance(part,str) or not IDENTIFIER.fullmatch(part) or not isinstance(rows,list) or not 2<=len(rows)<=128:
        raise ValueError('截面构件或锚点行无效')
    if type(step) not in (int,float) or not math.isfinite(step) or not 1<=step<=128 or type(count) is not int or not 8<=count<=128 or count%4:
        raise ValueError('截面采样步长或顶点数无效')
    anchors={item['id']:item for item in reference['anchors']};keys=('x_min','x_max','z_min','z_max')
    heights=[];boundaries={key:[] for key in keys}
    for row in rows:
        if not isinstance(row,dict) or set(row)-set(keys)-{'corner'} or not set(keys)<=set(row) or type(row.get('corner',False)) is not bool or any(not isinstance(row[key],str) or row[key] not in anchors for key in keys):
            raise ValueError('截面边界须引用已登记锚点')
        picked={key:anchors[row[key]] for key in keys}
        if any(item['part']!=part for item in picked.values()):raise ValueError('截面锚点不属于指定构件')
        y=picked['x_min']['world'][1]
        if any(abs(item['world'][1]-y)>1e-7 for item in picked.values()) or heights and y<=heights[-1]:
            raise ValueError('截面锚点高度须一致并严格递增')
        heights.append(y)
        for key in keys:boundaries[key].append(picked[key]['world'][0 if key.startswith('x') else 2])
        if boundaries['x_min'][-1]>=boundaries['x_max'][-1] or boundaries['z_min'][-1]>=boundaries['z_max'][-1]:
            raise ValueError('截面边界须具有正宽度和深度')
    if heights[-1]-heights[0]>4096:raise ValueError('截面高度范围过大')
    controls={}
    for key,values in boundaries.items():
        slopes=_slopes(heights,values);segments=[]
        for i in range(len(heights)-1):
            h=heights[i+1]-heights[i];low,high=sorted((values[i],values[i+1]))
            clamp=lambda value:max(low,min(high,value))
            segment_slope=(values[i+1]-values[i])/h
            left=segment_slope if rows[i].get('corner',False) else slopes[i]
            right=segment_slope if rows[i+1].get('corner',False) else slopes[i+1]
            segments.append([values[i],clamp(values[i]+left*h/3),clamp(values[i+1]-right*h/3),values[i+1]])
        controls[key]=segments
    samples=[]
    for i in range(len(heights)-1):
        y=heights[i]
        while y<heights[i+1]-1e-9:
            if not samples or y>samples[-1]+1e-9:samples.append(y)
            y+=step
            if len(samples)>4096:raise ValueError('截面采样数量过大')
    samples.append(heights[-1]);sections=[]
    for y in samples:
        i=min(len(heights)-2,max(0,bisect_right(heights,y)-1));t=(y-heights[i])/(heights[i+1]-heights[i])
        values={}
        for key in keys:
            a,b,c,d=controls[key][i];values[key]=(1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d
        if values['x_min']>=values['x_max'] or values['z_min']>=values['z_max']:
            raise ValueError('拟合截面出现非正宽度，请调整锚点')
        cx=(values['x_min']+values['x_max'])/2;rx=(values['x_max']-values['x_min'])/2
        cz=(values['z_min']+values['z_max'])/2;rz=(values['z_max']-values['z_min'])/2
        vertices=[[round(cx+rx*math.cos(math.tau*j/count),6),round(cz+rz*math.sin(math.tau*j/count),6)] for j in range(count)]
        sections.append(dict(y=float(y),vertices=vertices))
    # Recheck the same inputs after calculating; fitting never grants approval.
    load_reference(request['reference'],request['reference_sha256'])
    return dict(reference_sha256=request['reference_sha256'],part=part,anchor_rows=rows,sample_step=float(step),vertices=count,heights=heights,
                controls=controls,geometry=dict(shape='loft',sections=sections),approval_created=False)


def save_fit(workspace,request,output):
    workspace=require_creative_workspace(workspace)
    if not isinstance(request,dict) or not isinstance(request.get('reference'),str):raise ValueError('参考拟合请求无效')
    reference=_workspace_path(workspace,request['reference'])
    target=_workspace_path(workspace,str(output));base=workspace/'nbt_models/_workspaces/reference-fits'
    if not target.is_relative_to(base) or target==base or target.suffix.lower()!='.json' or target.exists() or target.is_symlink():
        raise ValueError('拟合输出须为 reference-fits 下尚不存在的 JSON 文件')
    result=fit_profile(dict(request,reference=str(reference)))
    result['reference']=reference.relative_to(workspace).as_posix()
    raw=(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf8')
    if len(raw)>MAX_MANIFEST:raise ValueError('拟合结果过大')
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.fit-',dir=target.parent) as temporary:
        staged=Path(temporary)/'result.json';staged.write_bytes(raw)
        load_reference(reference,request['reference_sha256'])
        try:os.link(staged,target)
        except FileExistsError:raise ValueError('拟合输出已存在，未覆盖') from None
    return dict(output=str(target),sha256=_hash(raw),reference_sha256=request['reference_sha256'],
                sections=len(result['geometry']['sections']),approval_created=False)


def verify_fit(workspace,file,expected_sha256):
    workspace=Path(workspace).resolve();file=_workspace_path(workspace,str(file))
    if not file.is_file() or file.stat().st_size>MAX_MANIFEST or not isinstance(expected_sha256,str) or not SHA.fullmatch(expected_sha256):
        raise ValueError('拟合文件或哈希无效')
    with file.open('rb') as stream:raw=stream.read(MAX_MANIFEST+1)
    if len(raw)>MAX_MANIFEST or _hash(raw)!=expected_sha256:raise ValueError('拟合文件哈希不一致')
    try:data=json.loads(raw)
    except (ValueError,UnicodeDecodeError):raise ValueError('拟合文件无效') from None
    expected_keys={'reference','reference_sha256','part','anchor_rows','sample_step','vertices','heights','controls','geometry','approval_created'}
    if not isinstance(data,dict) or set(data)!=expected_keys:raise ValueError('拟合文件字段无效')
    reference=_workspace_path(workspace,data['reference'])
    computed=fit_profile(dict(reference=str(reference),reference_sha256=data['reference_sha256'],part=data['part'],
                              rows=data['anchor_rows'],sample_step=data['sample_step'],vertices=data['vertices']))
    if computed!={key:value for key,value in data.items() if key!='reference'}:
        raise ValueError('拟合结果与登记锚点不一致')
    with file.open('rb') as stream:unchanged=stream.read(MAX_MANIFEST+1)==raw
    if not unchanged:raise ValueError('核对期间拟合文件发生变化')
    return dict(valid=True,output=str(file),sha256=expected_sha256,reference_sha256=data['reference_sha256'],
                sections=len(computed['geometry']['sections']),approval_created=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,default=Path.cwd())
    sub=parser.add_subparsers(dest='action',required=True)
    for name in ('register','fit','compare','cameras','review-prepare','review-record','review-verify'):
        command=sub.add_parser(name);command.add_argument('--request',type=Path,required=True)
        if name=='fit':command.add_argument('--output',type=Path,required=True)
    verify=sub.add_parser('verify');verify.add_argument('--report',type=Path,required=True);verify.add_argument('--sha256',required=True)
    verify_fit_parser=sub.add_parser('verify-fit');verify_fit_parser.add_argument('--fit',type=Path,required=True);verify_fit_parser.add_argument('--sha256',required=True)
    verify_camera_parser=sub.add_parser('verify-cameras');verify_camera_parser.add_argument('--bundle',type=Path,required=True);verify_camera_parser.add_argument('--sha256',required=True)
    args=parser.parse_args()
    try:
        if args.action=='verify':
            from nbt_reference_projection import verify_comparison
            result=verify_comparison(args.workspace,args.report,args.sha256)
        elif args.action=='verify-fit':result=verify_fit(args.workspace,args.fit,args.sha256)
        elif args.action=='verify-cameras':
            from nbt_reference_camera import verify_cameras
            result=verify_cameras(args.workspace,args.bundle,args.sha256)
        else:
            if args.request.stat().st_size>MAX_MANIFEST:raise ValueError('参考请求过大')
            request=json.loads(args.request.read_text(encoding='utf-8-sig'))
            if args.action=='register':result=register_reference(args.workspace,request)
            elif args.action=='fit':result=save_fit(args.workspace,request,args.output)
            elif args.action=='cameras':
                from nbt_reference_camera import prepare_cameras
                result=prepare_cameras(args.workspace,request)
            elif args.action in ('review-prepare','review-record','review-verify'):
                from nbt_blind_review import prepare_review,record_review,verify_review
                if args.action=='review-prepare':result=prepare_review(args.workspace,request)
                elif args.action=='review-record':result=record_review(args.workspace,request)
                else:
                    if not isinstance(request,dict) or set(request)-{'binding','binding_sha256','record','record_sha256'} or not {'binding','binding_sha256'}<=set(request):
                        raise ValueError('盲评核对请求字段无效')
                    result=verify_review(args.workspace,request['binding'],request['binding_sha256'],request.get('record'),request.get('record_sha256'))
            else:
                from nbt_reference_projection import compare_reference
                result=compare_reference(args.workspace,request)
        print(json.dumps(result,ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(json.dumps(dict(error=str(error),code='REFERENCE_INVALID'),ensure_ascii=False));return 1


if __name__=='__main__':raise SystemExit(main())
