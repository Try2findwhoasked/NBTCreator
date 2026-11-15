"""Versioned raster-pattern assets; no building edits or executable recipes."""
import base64
import hashlib
import json
import os
from io import BytesIO
from pathlib import Path
import re
import uuid

from PIL import Image,ImageOps
from nbt_ornament_sample import sample_image,read_raster,crop_image


def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def root(workspace):
    base=Path(workspace).resolve();folder=base/'nbt_models/asset_library/patterns'
    if not folder.resolve().is_relative_to(base):raise ValueError('纹样资产库路径越界')
    return folder


def folder_for(workspace,identifier):
    if not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('纹样资产编号无效')
    folder=root(workspace)/identifier
    if not folder.resolve().is_relative_to(root(workspace).resolve()):raise ValueError('纹样资产路径越界')
    return folder


def checked_file(folder,name):
    file=folder/name
    if not file.resolve().is_relative_to(folder.resolve()):raise ValueError('纹样资产文件路径越界')
    return file


def load(workspace,identifier):
    if identifier.startswith('builtin:'):
        from nbt_pattern_panel import library,LIBRARY
        key=identifier[len('builtin:'):];entry=library().get(key)
        if entry is None:raise ValueError('内置纹样不存在')
        file=LIBRARY/entry['file'];raw=file.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise ValueError('内置纹样哈希已变化')
        image=read_raster(raw)
        data=dict(id=identifier,asset_type='ornament_pattern',name=entry.get('label',key),tags=entry['surfaces'],
                  archived=False,builtin=True,resolution=list(image.size),image_sha256=entry['sha256'],
                  recipe=dict(preset=key),fitting_input=dict(preset=key),
                  fitting_defaults=dict(mode='micro' if entry.get('microfit',{}).get('preferred') else 'standard',
                      size_uv=entry['size_uv'],recommended_size_uv=entry.get('microfit',{}).get('recommended_size_uv',{})))
        data['content_sha256']=digest(data)
        return dict(data,thumbnail=str(file),image=str(file),file=None)
    folder=folder_for(workspace,identifier);file=checked_file(folder,'pattern.json')
    if file.stat().st_size>1024*1024:raise ValueError('纹样元数据过大')
    data=json.loads(file.read_text(encoding='utf8'))
    if data.get('schema_version')!=1 or data.get('id')!=identifier or data.get('asset_type')!='ornament_pattern':
        raise ValueError('纹样资产格式无效')
    content=data.pop('content_sha256',None)
    if digest(data)!=content:raise ValueError('纹样资产内容哈希不匹配')
    for name,key in (('pattern.png','image_sha256'),('thumbnail.png','thumbnail_sha256')):
        path=checked_file(folder,name)
        if path.stat().st_size>8*1024*1024 or hashlib.sha256(path.read_bytes()).hexdigest()!=data[key]:
            raise ValueError('纹样图像哈希不匹配')
    if data.get('original_sha256'):
        original=checked_file(folder,'original.image')
        if original.stat().st_size>8*1024*1024 or hashlib.sha256(original.read_bytes()).hexdigest()!=data['original_sha256']:
            raise ValueError('纹样原图哈希不匹配')
    image=checked_file(folder,'pattern.png')
    relative=image.relative_to(Path(workspace).resolve()).as_posix()
    return dict(data,content_sha256=content,builtin=False,file=str(file),image=str(image),
                thumbnail=str(checked_file(folder,'thumbnail.png')),
                fitting_input=dict(sample=dict(path=relative,sha256=data['image_sha256'],noise_strength=0)))


def store(workspace,image,name,tags,recipe,*,original=None):
    if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise ValueError('纹样名称须为1～80字')
    if not isinstance(tags,list) or len(tags)>16 or any(not isinstance(t,str) or not 1<=len(t)<=32 for t in tags):
        raise ValueError('纹样标签无效')
    if len(json.dumps(recipe,ensure_ascii=False).encode('utf8'))>512*1024:raise ValueError('纹样配方超过512KiB，请简化图层或小位图')
    encoded=BytesIO();image.save(encoded,format='PNG');png=encoded.getvalue()
    if len(png)>8*1024*1024:raise ValueError('归一化PNG超过8MiB，请先裁取区域或缩小原图')
    if original is not None and len(original)>8*1024*1024:raise ValueError('纹样原图过大')
    thumbnail=ImageOps.pad(image.convert('RGBA'),(320,240),Image.Resampling.LANCZOS,color=(18,23,30,255))
    identifier=uuid.uuid4().hex;folder=folder_for(workspace,identifier)
    folder.mkdir(parents=True)
    (folder/'pattern.png').write_bytes(png)
    thumbnail.save(folder/'thumbnail.png')
    data=dict(schema_version=1,id=identifier,asset_type='ornament_pattern',name=name.strip(),tags=list(dict.fromkeys(tags)),
              archived=False,resolution=list(image.size),recipe=recipe,
              image_sha256=hashlib.sha256((folder/'pattern.png').read_bytes()).hexdigest(),
              thumbnail_sha256=hashlib.sha256((folder/'thumbnail.png').read_bytes()).hexdigest())
    if original is not None:
        (folder/'original.image').write_bytes(original);data['original_sha256']=hashlib.sha256(original).hexdigest()
    data['content_sha256']=digest(data)
    (folder/'pattern.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    return dict(load(workspace,identifier),model_modified=False,nbt_exported=False)


def dispatch(workspace,args):
    action=args['action']
    fields={'list':{'action'},'get':{'action','id'},
            'update':{'action','id','content_sha256','name','tags','archived'},
            'import':{'action','name','tags','sample','image_base64','crop'},
            'copy':{'action','id','image_sha256','name','tags','crop'}}
    if set(args)-fields[action]:raise ValueError('该纹样资产操作含不适用参数')
    required={'list':set(),'get':{'id'},'update':{'id','content_sha256'},'copy':{'id','image_sha256'},'import':set()}
    if required[action]-set(args):raise ValueError('缺少纹样资产参数：'+','.join(sorted(required[action]-set(args))))
    if action=='list':
        from nbt_pattern_panel import library
        items=[load(workspace,'builtin:'+key) for key in library()];errors=[]
        for file in sorted(root(workspace).glob('*/pattern.json')):
            try:items.append({k:v for k,v in load(workspace,file.parent.name).items() if k!='recipe'})
            except (ValueError,OSError,KeyError) as error:errors.append(dict(id=file.parent.name,error=str(error)))
        return dict(items=items,errors=errors,model_modified=False)
    if action=='get':return load(workspace,args['id'])
    if action=='update':
        data=load(workspace,args['id'])
        if data['builtin']:raise ValueError('内置纹样请先保存副本')
        from nbt_prompts import index_lock
        folder=folder_for(workspace,args['id'])
        with index_lock(Path(workspace).resolve(),folder):
            data=load(workspace,args['id'])
            if data['content_sha256']!=args.get('content_sha256'):raise ValueError('纹样已变化，请刷新资产')
            record=json.loads((folder/'pattern.json').read_text(encoding='utf8'))
            if 'name' in args:
                if not args['name'].strip():raise ValueError('纹样名称不能为空')
                record['name']=args['name'].strip()
            for key in ('tags','archived'):
                if key in args:record[key]=args[key]
            record.pop('content_sha256');record['content_sha256']=digest(record)
            temporary=folder/(uuid.uuid4().hex+'.tmp')
            temporary.write_text(json.dumps(record,ensure_ascii=False,separators=(',',':')),encoding='utf8')
            os.replace(temporary,folder/'pattern.json')
        return load(workspace,args['id'])
    if action=='copy':
        data=load(workspace,args['id'])
        if data['image_sha256']!=args.get('image_sha256'):raise ValueError('源纹样图像已变化')
        raw=Path(data['image']).read_bytes();image=crop_image(read_raster(raw),args.get('crop'))
        recipe=dict(kind='asset_crop',source_id=args['id'],source_image_sha256=data['image_sha256'],crop=args.get('crop'))
        return store(workspace,image,args.get('name',data['name']+' 副本'),args.get('tags',data['tags']),recipe,original=raw)
    if ('sample' in args)==('image_base64' in args):raise ValueError('纹样导入须提供sample或image_base64其中一种')
    if 'sample' in args:
        if 'crop' in args:raise ValueError('sample导入请在sample.crop中设置裁取区域')
        sample=args['sample'];sample_image(workspace,sample)
        path=(Path(workspace).resolve()/sample['path']).resolve()
        if not path.is_relative_to(Path(workspace).resolve()):raise ValueError('样本图片须位于工作区内')
        with path.open('rb') as stream:raw=stream.read(8*1024*1024+1)
        if hashlib.sha256(raw).hexdigest()!=sample['sha256']:raise ValueError('导入期间源图已变化')
        image=crop_image(read_raster(raw),sample.get('crop'));recipe=dict(kind='sample_import',sample=sample)
    else:
        try:raw=base64.b64decode(args['image_base64'],validate=True)
        except (ValueError,TypeError):raise ValueError('图片编码无效') from None
        image=crop_image(read_raster(raw),args.get('crop'));recipe=dict(kind='image_import',source_sha256=hashlib.sha256(raw).hexdigest(),crop=args.get('crop'))
    return store(workspace,image,args.get('name','导入纹样'),args.get('tags',[]),recipe,original=raw)
