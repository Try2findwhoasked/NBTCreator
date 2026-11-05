"""Canonical Java 1.20.1 SNBT authoring sources with explicit wall ownership."""
import argparse,gzip,hashlib,io,json,os,sys,uuid
from functools import lru_cache
from pathlib import Path
WHEEL_SHA='38d571fbf2f7ebd640639461b47fc79919a8ea8e74633ffcc8aa6b2acfc9c889'
try:import nbtlib as N
except ModuleNotFoundError as error:
    if error.name!='nbtlib':raise
    wheel=Path(__file__).resolve().parents[1]/'assets/python/nbtlib-2.0.4-py3-none-any.whl'
    if not wheel.is_file() or hashlib.sha256(wheel.read_bytes()).hexdigest()!=WHEEL_SHA:raise RuntimeError('锁定的 SNBT 解析库缺失或已变化') from error
    sys.path.insert(0,str(wheel));import nbtlib as N
from nbt_assembly import Volume
from nbt_registry import normalize
from nbt_model import compound,AIR_NAMES

def state(tag):
    if not isinstance(tag,N.Compound) or not isinstance(tag.get('Name'),N.String):raise ValueError('SNBT 材质缺少 Name 字符串')
    props=tag.get('Properties',{})
    if any(not isinstance(value,N.String) for value in props.values()):raise ValueError('SNBT 方块状态属性须为字符串')
    return normalize(str(tag['Name'])+('['+','.join(str(k)+'='+str(v) for k,v in sorted(props.items()))+']' if props else ''))
def root(file):
    file=Path(file)
    if not file.is_file() or file.stat().st_size>256*1024*1024:raise ValueError('SNBT 文件缺失或超过256MiB')
    try:value=N.parse_nbt(file.read_text(encoding='utf-8-sig'))
    except (ValueError,TypeError,RecursionError) as error:raise ValueError('SNBT 语法无效：'+str(error)) from error
    if not isinstance(value,N.Compound):raise ValueError('SNBT 根节点须为 Compound')
    return value
def decode(data):
    if type(data.get('DataVersion')) is not N.Int or int(data['DataVersion'])!=3465:raise ValueError('SNBT 必须使用 Minecraft Java 1.20.1 DataVersion 3465')
    if data.get('entities') or 'palettes' in data:raise ValueError('当前几何引擎不支持实体或多材质方案，未丢弃这些数据；请使用支持的结构源')
    size=data.get('size',[])
    if len(size)!=3 or any(type(v) is not N.Int or not 1<=int(v)<=294 for v in size):raise ValueError('SNBT size 须为三个有效整数')
    model=Volume([int(v) for v in size]);palette=[state(tag) for tag in data.get('palette',[])]
    if not 1<=len(palette)<=4096:raise ValueError('SNBT palette 数量无效')
    seen=set()
    for block in data.get('blocks',[]):
        if 'nbt' in block:raise ValueError('当前几何引擎不支持方块实体数据，未转换或丢弃原文件')
        pos=block.get('pos',[]);index=block.get('state')
        if len(pos)!=3 or any(type(v) is not N.Int for v in pos) or type(index) is not N.Int or not 0<=int(index)<len(palette):raise ValueError('SNBT 方块坐标或材质编号无效')
        p=tuple(map(int,pos))
        if not model.in_bounds(p) or p in seen:raise ValueError('SNBT 方块重复或越界')
        seen.add(p);model.put(p,palette[int(index)])
    metadata=data.get('nbtcreator',{});walls={tuple(map(int,p)) for p in metadata.get('wall_positions',[])}
    if any(len(p)!=3 or not model.in_bounds(p) or p not in model.blocks for p in walls):raise ValueError('SNBT 墙层归属越界或指向空气')
    model._snbt_metadata_stale=bool(metadata.get('geometry_sha256') and str(metadata['geometry_sha256'])!=model.fingerprint())
    model._snbt_palette=palette;model._snbt_extras={k:v for k,v in data.items() if k not in {'DataVersion','size','palette','blocks','entities','nbtcreator'}}
    return model,walls
@lru_cache(maxsize=8)
def _parsed_source(file,size,mtime,ctime):return decode(root(file))
def read_snbt(file):
    file=Path(file).resolve();stamp=file.stat();base,mask=_parsed_source(str(file),stamp.st_size,stamp.st_mtime_ns,stamp.st_ctime_ns)
    model=Volume(base.size);model.blocks=dict(base.blocks);model._snbt_palette=list(base._snbt_palette);model._snbt_extras=dict(base._snbt_extras);model._snbt_metadata_stale=base._snbt_metadata_stale
    return model,set(mask)
def read_binary(file):
    file=Path(file);model,walls=decode(N.load(file))
    sidecar=file.parent/'wall_mask.json'
    if sidecar.is_file():
        meta=json.loads(sidecar.read_text(encoding='utf8'));walls={tuple(p) for p in meta.get('wall_positions',[])}
        if meta.get('geometry_sha256')!=model.fingerprint() or any(len(p)!=3 or not model.in_bounds(p) or p not in model.blocks for p in walls):raise ValueError('NBT 墙层附属数据与主模型不一致')
    return model,walls
def write_binary(file,model,walls):
    values=sorted(set(model.blocks.values())) or ['minecraft:air'];palette=[]
    for value in values:
        item=compound(value);tag=N.Compound({'Name':N.String(item['Name'])})
        if item.get('Properties'):tag['Properties']=N.Compound({k:N.String(v) for k,v in sorted(item['Properties'].items())})
        palette.append(tag)
    ids={value:i for i,value in enumerate(values)}
    data=N.Compound({'DataVersion':N.Int(3465),'size':N.List[N.Int](model.size),'palette':N.List[N.Compound](palette),'blocks':N.List[N.Compound]([N.Compound({'pos':N.List[N.Int](p),'state':N.Int(ids[value])}) for p,value in sorted(model.blocks.items())]),'entities':N.List[N.Compound]([])})
    raw=io.BytesIO();N.File(data).write(raw);file=Path(file);file.parent.mkdir(parents=True,exist_ok=True)
    if file.exists():raise FileExistsError('定稿 NBT 已存在，未覆盖')
    with file.open('xb') as stream:stream.write(gzip.compress(raw.getvalue(),mtime=0))
    (file.parent/'wall_mask.json').write_text(json.dumps(dict(geometry_sha256=model.fingerprint(),wall_positions=sorted(walls)),separators=(',',':'))+'\n',encoding='utf8')
    disk,mask=read_binary(file)
    if disk.blocks!=model.blocks or disk.size!=model.size or mask!=set(walls):raise ValueError('定稿 NBT 回读不一致')
    return dict(path=str(file.resolve()),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),disk_roundtrip=True)
def save_snbt(file,model,walls,palette=None,extras=None):
    file=Path(file);walls={tuple(p) for p in walls}
    if any(len(p)!=3 or not model.in_bounds(p) or p not in model.blocks for p in walls):raise ValueError('显式墙层归属无效')
    previous=list(palette if palette is not None else getattr(model,'_snbt_palette',[]))
    # Keep existing palette indices and append new states, avoiding unrelated diffs.
    values=list(dict.fromkeys(previous));values.extend(v for v in sorted(set(model.blocks.values())-set(values)))
    if not values:values=['minecraft:air']
    if len(values)>4096:raise ValueError('材质数量超过4096')
    by_state={value:i for i,value in enumerate(values)}
    lines=['{','  DataVersion: 3465,','  size: '+json.dumps(list(model.size))+',','  palette: [']
    for i,value in enumerate(values):
        item=compound(value);tag=N.Compound({'Name':N.String(item['Name'])})
        if item.get('Properties'):tag['Properties']=N.Compound({k:N.String(v) for k,v in sorted(item['Properties'].items())})
        lines.append('    '+tag.snbt()+(',' if i+1<len(values) else ''))
    lines+=['  ],','  blocks: [']
    blocks=sorted((p,v) for p,v in model.blocks.items() if v not in AIR_NAMES)
    for i,(p,value) in enumerate(blocks):lines.append('    {pos: '+json.dumps(list(p))+', state: '+str(by_state[value])+'}'+(',' if i+1<len(blocks) else ''))
    meta=N.Compound({'schema_version':N.Int(1),'geometry_sha256':N.String(model.fingerprint()),'wall_positions':N.List[N.List[N.Int]]([N.List[N.Int](p) for p in sorted(walls)])})
    lines+=['  ],','  entities: [],','  nbtcreator: '+meta.snbt()]
    for key,value in (extras if extras is not None else getattr(model,'_snbt_extras',{})).items():lines[-1]+=',';lines.append('  '+N.String(key).snbt()+': '+value.snbt())
    lines+=['}',''];raw='\n'.join(lines).encode('utf8');file.parent.mkdir(parents=True,exist_ok=True)
    temporary=file.with_name(file.name+'.'+uuid.uuid4().hex+'.tmp');temporary.write_bytes(raw)
    # Parsing the same representation must recover geometry and wall ownership.
    check,mask=read_snbt(temporary)
    if check.blocks!=model.blocks or check.size!=model.size or mask!=walls:raise ValueError('SNBT 写入回读不一致')
    os.replace(temporary,file)
    return dict(source=str(file.resolve()),geometry_sha256=model.fingerprint(),source_sha256=hashlib.sha256(raw).hexdigest(),format='snbt',wall_positions=len(walls))
def convert(source,output):
    source,output=Path(source).resolve(),Path(output).resolve()
    if output==source or output.exists():raise ValueError('请选择新的 SNBT 文件，保留原稿')
    from nbt_refine import read_master
    model,walls=read_master(source);return save_snbt(output,model,walls)
def explicit_walls(source):
    return 'wall_positions' in root(source).get('nbtcreator',{})
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    try:print(json.dumps(convert(args.source,args.output),ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError) as error:print(json.dumps(dict(error=str(error)),ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
