"""Build source-bound curve masks from explicitly selected component slices."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from nbt_composition.large_assembly import _workspace_path,require_creative_workspace
from nbt_review.reference_views import MAX_MANIFEST

MAX_MASK=4*1024*1024
SHA=re.compile(r'^[a-f0-9]{64}$')


def _bytes(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf8')


def _hash(raw):return hashlib.sha256(raw).hexdigest()


def _read(file,limit):
    if not file.is_file() or file.stat().st_size>limit:raise ValueError('曲面组合文件不存在或过大')
    with file.open('rb') as stream:raw=stream.read(limit+1)
    if len(raw)>limit:raise ValueError('曲面组合文件过大')
    return raw


def _pair(value,label,lo,hi):
    if not isinstance(value,list) or len(value)!=2 or any(type(x) is not int or not lo<=x<=hi for x in value):
        raise ValueError(label+'须为两个范围内的整数')
    return value


def _component(workspace,source):
    if not isinstance(source,dict) or source.get('kind') not in ('local','library'):raise ValueError('曲面构件来源无效')
    if source['kind']=='local':
        if set(source)!={'kind','id','content_sha256'} or not isinstance(source['content_sha256'],str) or not SHA.fullmatch(source['content_sha256']):
            raise ValueError('本地构件来源或内容哈希无效')
        from nbt_assets.components import load
        data=load(workspace,source['id'])
        if data.get('archived'):raise ValueError('本地构件已归档')
        if data['content_sha256']!=source['content_sha256']:raise ValueError('本地构件内容哈希已变化')
        return data
    if set(source)!={'kind','ref'} or not isinstance(source['ref'],dict):raise ValueError('拓展构件来源无效')
    ref=source['ref'];required={'id','sha256','source_id','version','manifest_sha256','content_sha256'}
    if not required<=set(ref) or set(ref)-required-{'arguments'}:raise ValueError('拓展构件须绑定来源、版本及内容哈希')
    from nbt_assets.libraries import asset_action
    return asset_action(workspace,'resolve',deepcopy(ref))['component']


def _compose_body(workspace,spec):
    if (not isinstance(spec,dict) or set(spec)!={'name','size','layers','overlaps'} or
        not isinstance(spec['name'],str) or not 1<=len(spec['name'].strip())<=120 or
        not isinstance(spec['layers'],list) or not 1<=len(spec['layers'])<=8 or not isinstance(spec['overlaps'],list)):
        raise ValueError('曲面构件组合格式无效')
    width,height=_pair(spec['size'],'画布尺寸',1,64);layers=[];stats=[];sources={}
    for entry in spec['layers']:
        required={'id','source','slice_z','origin','counts','spacing','mapping','palette'}
        if not isinstance(entry,dict) or not required<=set(entry) or set(entry)-required-{'support_expectations','connections'}:
            raise ValueError('曲面构件层字段无效')
        key=_hash(_bytes(entry['source']))
        if key not in sources:sources[key]=_component(workspace,entry['source'])
        component=sources[key];sx,sy,sz=component['size'];z=entry['slice_z']
        if type(z) is not int or not 0<=z<sz:raise ValueError('曲面构件切片超出深度')
        origin=_pair(entry['origin'],'UV 起点',0,63);counts=_pair(entry['counts'],'重复数量',1,16);spacing=_pair(entry['spacing'],'重复间距',1,64)
        if origin[0]+(counts[0]-1)*spacing[0]+sx>width or origin[1]+(counts[1]-1)*spacing[1]+sy>height:
            raise ValueError('曲面构件重复范围越界，不自动裁切')
        selected=[block for block in component['blocks'] if block[2]==z]
        if not selected:raise ValueError('曲面构件切片为空')
        mapping=entry['mapping']
        if not isinstance(mapping,list) or not 1<=len(mapping)<=4096:raise ValueError('曲面构件材质与墙层映射无效')
        actions={}
        for row in mapping:
            if (not isinstance(row,dict) or set(row)!={'index','wall','symbol'} or type(row['index']) is not int or
                not 0<=row['index']<len(component['palette']) or type(row['wall']) is not bool or
                row['symbol'] is not None and (not isinstance(row['symbol'],str) or not re.fullmatch('[A-Z0-9]',row['symbol']))):
                raise ValueError('曲面构件材质与墙层映射无效')
            key=(row['index'],row['wall'])
            if key in actions:raise ValueError('曲面构件材质与墙层映射重复')
            actions[key]=row['symbol']
        used={(block[3],block[4]) for block in selected}
        if set(actions)!=used:raise ValueError('曲面构件须明确映射切片中每种材质编号和墙层，包括忽略项')
        grid=[['.']*width for _ in range(height)];duplicates=0
        for cy in range(counts[1]):
            for cx in range(counts[0]):
                for x,y,_,index,wall in selected:
                    symbol=actions[(index,wall)]
                    if symbol is None:continue
                    u=origin[0]+cx*spacing[0]+x;v=origin[1]+cy*spacing[1]+y;previous=grid[v][u]
                    if previous!='.' and previous!=symbol:raise ValueError('同层构件重复铺排发生不同动作重叠')
                    if previous==symbol:duplicates+=1
                    grid[v][u]=symbol
        rows=[''.join(row) for row in grid]
        layer=dict(id=entry['id'],rows=rows,palette=deepcopy(entry['palette']))
        if 'support_expectations' in entry:layer['support_expectations']=deepcopy(entry['support_expectations'])
        if 'connections' in entry:layer['connections']=deepcopy(entry['connections'])
        layers.append(layer);stats.append(dict(id=entry['id'],source_content_sha256=component['content_sha256'],
                                              selected_blocks=len(selected),merged_cells=duplicates))
    body=dict(schema_version=2,name=spec['name'].strip(),layers=layers,overlaps=deepcopy(spec['overlaps']))
    from nbt_mounting.curved_surface import _layered_mask
    _layered_mask(body)
    return body,stats


def _verify_data(workspace,mask_file,data,mask_sha256):
    if not isinstance(data,dict) or 'composition' not in data:raise ValueError('掩模没有曲面构件来源绑定')
    binding=data['composition']
    if (not isinstance(binding,dict) or set(binding)!={'manifest','sha256'} or binding['manifest']!='composition.json' or
        not isinstance(binding['sha256'],str) or not SHA.fullmatch(binding['sha256'])):
        raise ValueError('曲面组合回执绑定无效')
    manifest=_workspace_path(workspace,str(mask_file.parent/'composition.json'))
    if manifest!=mask_file.parent/'composition.json':raise ValueError('曲面组合回执路径无效')
    raw=_read(manifest,MAX_MANIFEST)
    if _hash(raw)!=binding['sha256']:raise ValueError('曲面组合回执哈希已变化')
    try:receipt=json.loads(raw)
    except (ValueError,UnicodeDecodeError):raise ValueError('曲面组合回执无效') from None
    fields={'schema_version','kind','spec','body_sha256','stats','approval_created','nbt_exported'}
    if (not isinstance(receipt,dict) or set(receipt)!=fields or type(receipt['schema_version']) is not int or receipt['schema_version']!=1 or
        receipt['kind']!='nbtcreator-curve-composition' or receipt['approval_created'] is not False or receipt['nbt_exported'] is not False):
        raise ValueError('曲面组合回执类型无效')
    body={key:value for key,value in data.items() if key!='composition'}
    if _hash(_bytes(body))!=receipt['body_sha256']:raise ValueError('曲面掩模内容与来源回执不一致')
    rebuilt,stats=_compose_body(workspace,receipt['spec'])
    if rebuilt!=body or stats!=receipt['stats']:raise ValueError('曲面掩模与当前构件内容不一致')
    repeated,repeated_stats=_compose_body(workspace,receipt['spec'])
    if repeated!=body or repeated_stats!=stats or _hash(_read(manifest,MAX_MANIFEST))!=binding['sha256'] or _hash(_read(mask_file,MAX_MASK))!=mask_sha256:
        raise ValueError('核对期间曲面构件或组合文件发生变化')
    return body,receipt


def verify_curve_mask(workspace,mask,expected_sha256):
    workspace=Path(workspace).resolve();mask=_workspace_path(workspace,str(mask))
    if not isinstance(expected_sha256,str) or not SHA.fullmatch(expected_sha256):raise ValueError('曲面掩模哈希无效')
    raw=_read(mask,MAX_MASK)
    if _hash(raw)!=expected_sha256:raise ValueError('曲面掩模哈希已变化')
    try:data=json.loads(raw)
    except (ValueError,UnicodeDecodeError):raise ValueError('曲面掩模 JSON 无效') from None
    _,receipt=_verify_data(workspace,mask,data,expected_sha256)
    return dict(valid=True,mask=str(mask),mask_sha256=expected_sha256,layers=len(receipt['stats']),
                approval_created=False,nbt_exported=False,
                scope='Rebuilds the mask from current bound components; no visual approval or game validation')


def compose_curve_mask(workspace,request):
    workspace=require_creative_workspace(workspace)
    if not isinstance(request,dict) or set(request)!={'name','size','layers','overlaps','output'}:
        raise ValueError('曲面构件组合请求字段无效')
    destination=_workspace_path(workspace,request['output']);base=workspace/'nbt_models/_workspaces/curve-masks'
    if not destination.is_relative_to(base) or destination==base or destination.exists() or destination.is_symlink():
        raise ValueError('曲面构件掩模输出须为 curve-masks 下的新目录')
    spec={key:deepcopy(request[key]) for key in ('name','size','layers','overlaps')}
    body,stats=_compose_body(workspace,spec)
    receipt=dict(schema_version=1,kind='nbtcreator-curve-composition',spec=spec,body_sha256=_hash(_bytes(body)),stats=stats,
                 approval_created=False,nbt_exported=False)
    receipt_raw=_bytes(receipt)
    if len(receipt_raw)>MAX_MANIFEST:raise ValueError('曲面组合回执过大')
    data=dict(body,composition=dict(manifest='composition.json',sha256=_hash(receipt_raw)));mask_raw=_bytes(data)
    if len(mask_raw)>MAX_MASK:raise ValueError('曲面组合掩模过大')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.curve-compose-',dir=destination.parent) as temporary:
        temp=Path(temporary);(temp/'mask.json').write_bytes(mask_raw);(temp/'composition.json').write_bytes(receipt_raw)
        repeated,repeated_stats=_compose_body(workspace,spec)
        if repeated!=body or repeated_stats!=stats:raise ValueError('组合期间构件内容发生变化')
        try:destination.mkdir()
        except FileExistsError:raise ValueError('曲面构件掩模输出已存在') from None
        created=[]
        try:
            for name in ('composition.json','mask.json'):
                os.link(temp/name,destination/name);created.append((destination/name,receipt_raw if name=='composition.json' else mask_raw))
            verify_curve_mask(workspace,destination/'mask.json',_hash(mask_raw))
        except Exception:
            for file,expected in reversed(created):
                try:
                    if not file.is_symlink() and _read(file,max(MAX_MASK,MAX_MANIFEST))==expected:file.unlink()
                except (OSError,ValueError):pass
            try:destination.rmdir()
            except OSError:pass
            raise
    return dict(mask=str(destination/'mask.json'),mask_sha256=_hash(mask_raw),manifest=str(destination/'composition.json'),
                manifest_sha256=_hash(receipt_raw),layers=len(stats),approval_created=False,nbt_exported=False)
