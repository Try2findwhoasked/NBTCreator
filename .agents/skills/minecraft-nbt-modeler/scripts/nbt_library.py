"""Canonical model-library metadata, shape inference and non-destructive audit."""
import gzip,hashlib,json,os,re
from pathlib import Path
from collections import defaultdict
from functools import lru_cache
from nbt_assembly import Volume
from nbt_registry import normalize
from nbt_model import AIR_NAMES,load
from nbt_delivery import verify_delivery
from generate_sealed_models import read_nbt
INFRA={'master','masters','runtime','parts','layers','delivery'}
LABELS={'single':'单格','long':'长条','square':'方形','l_shape':'L形','t_shape':'T形','cross':'十字形','irregular':'不规则','standalone':'独立建筑'}
def read_json(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write_json(p,d):
 import uuid
 target=Path(p);target.parent.mkdir(parents=True,exist_ok=True);temporary=target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
 temporary.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temporary,target)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as stream:
  for part in iter(lambda:stream.read(1048576),b''):h.update(part)
 return h.hexdigest()
def shape_of(size,cells):
 if size[0]%48 or size[2]%48:return 'standalone'
 c={tuple(p) for p in cells};n=len(c)
 if n==1:return 'single'
 if len({x for x,z in c})==1 or len({z for x,z in c})==1:return 'long'
 if n==3:return 'l_shape'
 degrees=[sum((x+dx,z+dz) in c for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]) for x,z in c]
 if n==5 and max(degrees)==4:return 'cross'
 if n==4 and max(degrees)==3:return 't_shape'
 xs={x for x,z in c};zs={z for x,z in c}
 if n==len(xs)*len(zs) and len(xs)==len(zs):return 'square'
 return 'irregular'
def version_root(master):
 p=Path(master).parent
 while p.name in INFRA:p=p.parent
 # The closest authored coordinate file defines a version, not a broad batch root.
 for parent in [p,*list(p.parents)[:3]]:
  if any((parent/name).is_file() for name in ('coordinates.json','config.json','context.json')):return parent
 return p
@lru_cache(maxsize=1024)
def _state(value):return normalize(value)
def read_geometry(file):
 if Path(file).suffix.lower()=='.snbt':
  from nbt_snbt import read_snbt
  model,walls=read_snbt(file);return model,walls,sorted({(x//48,z//48) for x,y,z in model.blocks})
 with gzip.open(file,'rt',encoding='utf8') as stream:data=json.load(stream)
 size=data['size'];assert len(size)==3 and all(type(n) is int and n>0 for n in size),'主模型size无效'
 model=Volume(size);blocks={}
 for p,value in data['blocks']:
  p=tuple(p);assert len(p)==3 and all(type(n) is int for n in p) and model.in_bounds(p) and p not in blocks,'主模型坐标重复或越界'
  value=_state(value)
  if value not in AIR_NAMES:blocks[p]=value
 model.blocks=blocks
 assert data.get('geometry_sha256')==model.fingerprint(),'完整几何哈希不符'
 walls={tuple(p) for p in data.get('wall_positions',[])}
 assert all(p in blocks for p in walls),'墙归属越界或指向空气'
 cells=sorted({(x//48,z//48) for x,y,z in blocks})
 assert all(0<=p[0]<size[0] and 0<=p[2]<size[2] for p in blocks)
 return model,walls,cells
def chinese_name(unit):
 for name in ('room_description.json','final_manifest.json','design_review.json','description.json','coordinates.json','final_selection.json','manifest.json','room.json'):
  p=Path(unit)/name
  if not p.is_file():continue
  try:d=read_json(p)
  except (ValueError,OSError):continue
  if not isinstance(d,dict):continue
  for key in ('name_zh','chinese_name','中文名','title','name','room_name','label'):
   value=d.get(key)
   if isinstance(value,str) and re.search('[\u4e00-\u9fff]',value) and len(value)<70:return value.split(' - ')[0],str(p)
 # Version descriptors are often one or two levels above the final runtime export.
 for parent in list(Path(unit).parents)[:2]:
  p=parent/'final_selection.json'
  if p.is_file():
   try:
    d=read_json(p)
    for key in ('name_zh','title','name'):
     value=d.get(key)
     if isinstance(value,str) and re.search('[\u4e00-\u9fff]',value):return value,str(p)
   except (ValueError,OSError):pass
 return None,None

def adapt_coordinates(data):
 if not isinstance(data,dict):raise ValueError('坐标配置JSON需要对象，不能是列表或文字')
 data=dict(data,**data.get('floor_context',{}))
 if 'start' not in data and isinstance(data.get('arrival'),list):data['start']=data['arrival']
 if 'interior_probes' not in data and isinstance(data.get('probes'),list):data['interior_probes']=data['probes']
 if not data.get('cameras') and isinstance(data.get('views'),dict):
  cameras=[]
  for key,view in data['views'].items():
   if not isinstance(view,dict) or 'eye' not in view or 'target' not in view:continue
   camera=dict(view,id='entry' if key in ('entry','entrance') else key,role='entry' if key in ('entry','entrance') else key)
   camera['cuts']=[dict(axis=cut[0],position=cut[1],removed_side=cut[2]) if isinstance(cut,list) else cut for cut in camera.get('cuts',[])]
   cameras.append(camera)
  if cameras:data['cameras']=cameras
 return data

def canonical_context(file):
 data=adapt_coordinates(read_json(file))
 if 'interior_probes' not in data:
  for candidate in (Path(file).parent/'validation.json',Path(file).parent/'validation/summary.json',Path(file).parent/'validation/before_opening.json'):
   if not candidate.is_file():continue
   try:record=read_json(candidate)
   except (OSError,ValueError):continue
   for key in ('before_opening','seal_before_open','sealed_before_opening','sealed_before_opening','recapped_seal',''):
    proof=record.get(key,{}) if key else record
    if isinstance(proof,dict) and proof.get('passed') is True and isinstance(proof.get('probes'),list):
     data['interior_probes']=proof['probes'];break
   if 'interior_probes' in data:break
 return data

def report_evidence(unit):
 proof={'seal':False,'routes':False,'design':False};files=[]
 candidates=[]
 for p in Path(unit).glob('*.json'):
  if any(token in p.name for token in ('valid','manifest','review','audit','refin','report','route')):candidates.append(p)
 for folder in ['validation','validation_reports']:
  if (Path(unit)/folder).is_dir():candidates.extend((Path(unit)/folder).glob('*.json'))
 def walk(value,key=''):
  if isinstance(value,dict):
   passed=value.get('passed') is True
   k=key.lower()
   if passed and any(t in k for t in ('sealed','seal_before','recapped_seal','before_open','closed')):proof['seal']=True
   if passed and any(t in k for t in ('route','collision','reachab')):proof['routes']=True
   if any(value.get(t) is True for t in ('static_routes','routes_passed','route_passed','walk_48_passed','routes_48_passed')):proof['routes']=True
   for name,child in value.items():walk(child,name)
  elif isinstance(value,list):
   for child in value:walk(child,key)
 for p in candidates:
  if p.stat().st_size>8000000:continue
  try:
   d=read_json(p);walk(d,p.stem);files.append(str(p))
   if p.name=='design_review.json' and isinstance(d,dict):proof['design']=True
  except (ValueError,OSError):pass
 return proof,files

def audit_unit(unit,masters,geometry_cache,delivery_cache):
 result={'unit':str(unit),'masters':[str(p) for p in masters],'reasons':[],'valid':False}
 name,name_source=chinese_name(unit);result.update(name_zh=name,name_source=name_source)
 def rank(p):
  n=p.name
  return (p.suffix.lower()=='.snbt',n=='master_geometry.json.gz' or n.endswith('_master_geometry.json.gz'),not n.startswith(('pre_','sealed_','source.')),p.stat().st_mtime_ns)
 candidates=sorted(masters,key=rank,reverse=True)
 selected=None
 for p in candidates:
  try:
   digest=sha(p)
   if digest in geometry_cache:
    record=geometry_cache[digest]
    if not record['valid']:raise ValueError(record['error'])
   else:
    model,walls,cells=read_geometry(p);record=dict(valid=True,size=list(model.size),cells=[list(c) for c in cells],geometry_sha256=model.fingerprint(),walls=len(walls));geometry_cache[digest]=record
   selected=p;result.update(record,master=str(p),master_sha256=digest);break
  except Exception as error:
   geometry_cache[digest]=dict(valid=False,error=str(error))
 if selected is None:result['reasons'].append('没有可读取且哈希一致的完整主模型');return result
 result['valid']=False
 standalone_config=None
 for candidate in [unit/'coordinates.json',unit/'config.json',unit/'context.json']:
  if not candidate.is_file():continue
  try:
   value=canonical_context(candidate)
   if value.get('mode')=='standalone':standalone_config=value;break
  except (ValueError,OSError):pass
 standalone=standalone_config is not None
 footprint={tuple(c) for c in result['cells']};reached=set();pending=[next(iter(footprint))] if footprint else []
 while pending:
  cell=pending.pop()
  if cell in reached:continue
  reached.add(cell);x,z=cell
  pending.extend((x+dx,z+dz) for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)] if (x+dx,z+dz) in footprint and (x+dx,z+dz) not in reached)
 if not standalone and reached!=footprint:result['reasons'].append('有效cells不连通')
 if not result['walls'] and not (standalone and standalone_config.get('allow_empty_wall_mask') is True):result['reasons'].append('缺少显式全局墙mask')
 if not standalone and not 8<=result['size'][1]<=48:result['reasons'].append('当前切片高度不在8至48')
 result['shape']=shape_of(result['size'],result['cells']);result['shape_zh']=LABELS[result['shape']]
 if standalone:
  descriptor=unit/'room_description.json'
  if descriptor.is_file() and read_json(descriptor).get('shape')=='standalone':result.update(shape='standalone',shape_zh=LABELS['standalone'])
  result['mode']='standalone'
 configs=[p for p in [unit/'coordinates.json',unit/'config.json',unit/'context.json'] if p.is_file()]
 if not configs:result['reasons'].append('缺少坐标/保护配置')
 else:
  try:
   choice=None
   for candidate in configs:
    config=canonical_context(candidate)
    if all(k in config for k in ('start','targets','interior_probes')):choice=(candidate,config);break
   if choice is None:result['reasons'].append('坐标配置缺少路线或密闭探针')
   else:
    selected_config,config=choice
    if not standalone and config.get('cells') and {tuple(c) for c in config['cells']}!={tuple(c) for c in result['cells']}:result['reasons'].append('声明cells与实际占地不一致')
    result['context']=str(selected_config)
  except Exception as error:result['reasons'].append('坐标JSON无法读取：'+str(error))
 proof,proof_files=report_evidence(unit);result.update(evidence=proof,evidence_files=proof_files)
 if not proof['seal']:result['reasons'].append('缺少密闭检查通过记录')
 if not proof['routes']:result['reasons'].append('缺少静态通路检查通过记录')
 manifests=list(unit.rglob('delivery.json'))
 # Ignore nested versions; their own units will be processed separately.
 manifests=[p for p in manifests if not any(part=='versions' or re.match(r'^(?:v|detail_v|refined_v)\d+$',part) for part in p.relative_to(unit).parts[:-2])]
 # Final deliveries can live in the approved mirrored _exports tree.
 # Bind that packet to these exact source bytes before accepting its evidence.
 try:
  from nbt_history import source_workspace
  from nbt_finalize import release_path
  released=release_path(source_workspace(selected),selected)
  receipt=read_json(released/'release.json')
  if receipt.get('status')=='finalized' and receipt.get('source_sha256')==sha(selected) and receipt.get('geometry_sha256')==result['geometry_sha256']:
   mirror=released/'delivery/delivery.json'
   if mirror.is_file():manifests.append(mirror)
 except (OSError,ValueError,KeyError):pass
 matched=None
 for manifest in manifests:
  try:
   d=read_json(manifest)
   if d.get('source_geometry_sha256')!=result['geometry_sha256']:continue
   if standalone and d.get('kind')=='standalone_xyz_tiles':
    from nbt_standalone_delivery import verify_standalone
    verified=verify_standalone(manifest.parent.parent)
    matched=manifest;result['delivery']=str(manifest.parent);result['delivery_nbt']=verified['actual_nbt_files'];break
   key=sha(manifest)
   # file paths in the digest differ across copies; verify each packet's actual bytes.
   expected_files=[entry[layer] for entry in d['parts'] for layer in ('body','walls')]
   actual=[]
   for entry in d['parts']:
    for layer in ('body','walls'):
     file=manifest.parent/(d.get('file_prefix','')+f'p{entry["cell"][0]}{entry["cell"][1]}_{layer}.nbt')
     value=sha(file);assert value==entry[layer]['sha256'],'分层NBT文件哈希不符';actual.append(value)
   cache_key=('delivery',key,tuple(actual))
   if cache_key not in delivery_cache:delivery_cache[cache_key]=verify_delivery(manifest.parent)
   verified=delivery_cache[cache_key]
   matched=manifest;result['delivery']=str(manifest.parent);result['delivery_nbt']=verified['actual_nbt_files'];break
  except Exception as error:result.setdefault('delivery_errors',[]).append(str(error))
 if not matched:result['reasons'].append('缺少与当前主模型一致并可回读重组的主体/墙体交付')
 # Runtime comparison: inspect actual full-volume parts and match geometry by cell.
 if matched:
  try:
   if standalone and read_json(matched).get('kind')=='standalone_xyz_tiles':
    part_manifest=read_json(matched.parent.parent/'runtime/parts.json')
    result['runtime']=[str(matched.parent.parent/'runtime'/entry['file']) for entry in part_manifest['parts']]
    result['valid']=not result['reasons']
    return result
   model,_,_=read_geometry(selected)
   candidates=[p for folder in (unit/'runtime',unit/'parts',selected.parent,matched.parent.parent/'runtime') if folder.is_dir() for p in folder.rglob('*.nbt') if 'delivery' not in p.parts and 'layers' not in p.parts]
   candidates=list(dict.fromkeys(candidates));expected=defaultdict(dict)
   for (x,y,z),value in model.blocks.items():expected[(x//48,z//48)][(x%48,y,z%48)]=value
   signatures=defaultdict(list)
   for cell,blocks in expected.items():signatures[hashlib.sha256(json.dumps(sorted(blocks.items()),separators=(',',':')).encode()).hexdigest()].append(cell)
   found={};runtime=[]
   for p in candidates:
    file_sha=sha(p)
    if file_sha not in delivery_cache:
     full=load(p);delivery_cache[file_sha]=dict(size=list(full.size),geometry=hashlib.sha256(json.dumps(sorted(full.blocks.items()),separators=(',',':')).encode()).hexdigest())
    meta=delivery_cache[file_sha];matches=signatures.get(meta['geometry'],[])
    index=re.search(r'(?:^|_)p(\d)(\d)(?:[_.]|$)',p.name)
    cell=(int(index[1]),int(index[2])) if index else matches[0] if len(matches)==1 else None
    if cell not in matches:cell=None
    if cell is not None and meta['size']==[48,result['size'][1],48]:found[cell]=True;runtime.append(str(p))
   if set(found)!=set(expected):result['reasons'].append('完整含空气运行切片缺失或与主模型不一致')
   result['runtime']=runtime
  except Exception as error:result['reasons'].append('运行NBT回读失败：'+str(error))
 result['valid']=not result['reasons']
 return result


def new_project(workspace,name_zh,shape):
 from datetime import datetime,timezone,timedelta
 if not re.search('[\u4e00-\u9fff]',name_zh) or any(c in name_zh for c in '<>:"/\\|?*'):raise ValueError('建筑名须含中文且不能包含路径符号')
 if shape not in LABELS:raise ValueError('未知形状，使用single/long/square/l_shape/t_shape/cross/irregular/standalone')
 root=Path(workspace).resolve()/'nbt_models'/shape/name_zh
 stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d_%H%M%S')
 number=1
 while True:
  target=root/('v_'+stamp+('' if number==1 else '_'+str(number)))
  try:target.mkdir(parents=True);break
  except FileExistsError:number+=1
 write_json(target/'room_description.json',dict(schema_version=1,name_zh=name_zh,shape=shape,shape_zh=LABELS[shape],display_name=name_zh+'-'+LABELS[shape],description_zh=name_zh+'-'+LABELS[shape],master=None,status='authoring',audit=dict(compliant=None)))
 return target

def register_building(master,name_zh,cells=None,mode=None):
 if not isinstance(name_zh,str) or not re.search('[\u4e00-\u9fff]',name_zh):raise ValueError('房间描述必须提供中文名')
 model,walls,inferred=read_geometry(master);shape=shape_of(model.size,cells or inferred)
 if mode not in (None,'standalone','saodg'):raise ValueError('未知建筑模式')
 if mode=='standalone':
  from nbt_whole_validation import standalone_cells
  cells=standalone_cells(model,dict(cells=cells)) or []
  shape=shape_of(model.size,cells or inferred)
 parts=Path(master).resolve().parts
 if 'nbt_models' in parts:
  index=parts.index('nbt_models')
  if mode=='standalone' and index+1<len(parts) and parts[index+1]=='standalone':shape='standalone'
  if index+1<len(parts) and parts[index+1] in LABELS and parts[index+1]!=shape:raise ValueError('保存目录形状与实际完整模型不一致，请使用正确形状目录')
 unit=version_root(master);existing=unit/'room_description.json';data=read_json(existing) if existing.is_file() else {}
 data.update(schema_version=1,name_zh=name_zh,shape=shape,shape_zh=LABELS[shape],display_name=name_zh+'-'+LABELS[shape],description_zh=name_zh+'-'+LABELS[shape],master=os.path.relpath(Path(master).resolve(),unit).replace('\\','/'),master_file_sha256=sha(master),geometry_sha256=model.fingerprint(),size=list(model.size),cells=cells or inferred)
 if mode=='standalone':data.update(mode='standalone',cells=cells or [],parts_layout='xyz_tiles_max48')
 write_json(existing,data);return data

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
 new=sub.add_parser('new');new.add_argument('--workspace',type=Path,default=Path.cwd());new.add_argument('--name-zh',required=True);new.add_argument('--shape',required=True,choices=LABELS)
 reg=sub.add_parser('register');reg.add_argument('--master',type=Path,required=True);reg.add_argument('--name-zh',required=True)
 args=parser.parse_args()
 if args.command=='new':result=dict(output=str(new_project(args.workspace,args.name_zh,args.shape)))
 else:
  from nbt_refine import read_master
  from nbt_snbt import save_snbt
  source=args.master.resolve()
  if source.suffix.lower()!='.snbt':
   model,walls=read_master(source);authored=source.parent/'model.snbt'
   if authored.exists() and read_master(authored)[0].fingerprint()!=model.fingerprint():raise ValueError('制作源已存在不同内容，请另建版本后再登记')
   if not authored.exists():save_snbt(authored,model,walls)
   source=authored
  result=register_building(source,args.name_zh)
  from nbt_history import record_produced_version,source_workspace
  result['history']=record_produced_version(source_workspace(source),source,message='登记 SNBT 制作源',actor='import')
 print(json.dumps(result,ensure_ascii=False))
