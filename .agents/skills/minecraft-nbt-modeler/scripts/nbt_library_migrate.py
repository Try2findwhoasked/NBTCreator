"""Inventory, verify, relocate model artifacts and rebase their local references.

Copy+SHA256 verification precedes removal. Only planned files beneath build are
removed, never whole directories or unrelated compiler/release outputs.
"""
import argparse,json,os,re,hashlib,time,shutil
from pathlib import Path
from collections import defaultdict,Counter
from nbt_library import *
from nbt_web_paths import project_paths
SKILL=Path(__file__).resolve().parents[1]
SCOPE={'nbt_models','选择','结构审查_20261101','room_models','dungeon_review_20261030','skill_validation','skill_package_validation','detail_fix_control_web'}
def scoped_files(workspace):
 root=Path(workspace).resolve()/'build';files=[]
 for child in root.iterdir():
  if not child.is_dir() or not(child.name in SCOPE or child.name.startswith('console_')):continue
  for directory,dirs,names in os.walk(child):
   dirs[:]=[name for name in dirs if name not in {'node_modules','.git','__pycache__'} and not (Path(directory)/name).is_symlink()]
   files.extend(Path(directory)/name for name in names if not (Path(directory)/name).is_symlink())
 return files

def synthetic(path,build):
 return any(part.startswith(('console_','synthetic','test_')) or (part.lower().endswith('_test') or '_test_' in part.lower() or any(t in part.lower() for t in ('validation','fixture','regression'))) for part in path.relative_to(build).parts)

def audit(workspace,report,resume=False,limit=0):
 workspace=Path(workspace).resolve();build=workspace/'build';files=scoped_files(workspace);groups=defaultdict(list);testing=[]
 for p in files:
  if p.name.endswith('.json.gz') and 'master' in p.name.lower():
   if synthetic(p,build):testing.append(str(p));continue
   unit=version_root(p)
   if unit==build or build not in unit.parents:continue
   groups[unit].append(p)
 previous={record['unit']:record for record in read_json(report).get('records',[])} if resume and Path(report).is_file() else {}
 cache={};delivery_cache={};records=[];new_count=0;total=len(groups)
 for index,(unit,masters) in enumerate(sorted(groups.items())):
  if str(unit) in previous:
   record=previous[str(unit)];records.append(record);continue
  if limit and new_count>=limit:break
  new_count+=1
  try:record=audit_unit(unit,masters,cache,delivery_cache)
  except Exception as error:record=dict(unit=str(unit),masters=[str(p) for p in masters],valid=False,reasons=['审计异常：'+type(error).__name__+': '+str(error)])
  record['valid']=bool(record.get('valid'))
  records.append(record)
  if index%10==0:
   write_json(report,dict(status='auditing',processed=index+1,total=len(groups),records=records));print(json.dumps(dict(processed=index+1,total=len(groups),valid=sum(r['valid'] for r in records))),flush=True)
 data=dict(status='audited' if len(records)==total else 'auditing',total=total,workspace=str(workspace),files=[dict(source=str(p),size=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns) for p in files],records=records,synthetic_masters=testing)
 write_json(report,data);print(json.dumps(dict(status='audited',units=len(records),valid=sum(r['valid'] for r in records),files=len(files))),flush=True)
 return data

def translate_name(record):
 if record.get('name_zh'):return record['name_zh'],'existing_metadata'
 unit=Path(record['unit']);parts=list(unit.parts)
 names=[part for part in parts if re.search(r'^(?:[rRsSlL]\d+|\d{2})_',part)]
 raw=names[-1] if names else unit.name
 if re.search('[\u4e00-\u9fff]',raw):return re.sub(r'^[a-zA-Z]?\d+_','',raw),'source_folder'
 words={'ossuary':'遗骨库','prison':'监牢','forge':'锻造坊','foundry':'铸造坊','chapel':'礼拜堂','sluice':'水闸','procession':'巡礼廊','aqueduct':'引水渠','scriptorium':'抄经院','gateworks':'闸门工坊','archive':'档案馆','oath':'誓约','sword':'剑','tomb':'墓室','star':'星象','clock':'钟楼','keep':'要塞','herb':'药草','terraces':'阶地','seed':'种子','nursery':'育苗坊','root':'根系','moon':'月辉','sunken':'沉降','memorial':'纪念堂','knight':'骑士','workshop':'工坊','repair':'修缮','mill':'磨坊','grain':'粮仓','crystal':'水晶','baths':'浴场','dragon':'龙骨','courier':'信使','interchange':'中转站','expedition':'远征','cartography':'制图室','observatory':'观测台','theater':'剧场','armory':'军械库','armoury':'军械库','lockworks':'船闸工坊','drydock':'干船坞','vault':'穹窿','sanctuary':'圣所','cathedral':'大教堂','meridian':'子午','basalt':'玄武岩','fissure':'裂隙','gallery':'回廊','ropewalk':'绳索工坊','rope':'绳索','cascade':'叠瀑','cold':'冷铸','casting':'铸造','ink':'墨契','contract':'契约','garrison':'驻军','relief':'换防','counterweight':'配重','monastery':'修道院','ruined':'废墟','church':'教堂','shrine':'神祠','torii':'鸟居','armour':'甲胄','gatehouse':'门楼','rising':'错层','bent':'折转','cross':'交叉','forked':'分岔','arena':'竞技场','fan':'扇形','school':'学馆','excavation':'挖掘场','loft':'高廊','garden':'庭园','potion':'药剂','forgeworks':'锻造工场','blade':'刀剑','longstring':'长弦','oathhall':'誓约厅','survey':'勘测','silver':'银色','moss':'苔痕','crown':'冠层','patrol':'巡卫','tide':'潮汐','step':'阶梯','verdant':'翠绿','azure':'苍蓝','seedhouse':'种子工坊'}
 tokens=re.sub(r'^[a-zA-Z]?\d+_','',raw).lower().split('_');translated=''.join(words[token] for token in tokens if token in words)
 return (translated or '建筑')+'（'+(re.match(r'^[a-zA-Z]?\d+',raw).group(0) if re.match(r'^[a-zA-Z]?\d+',raw) else hashlib.sha256(raw.encode()).hexdigest()[:6])+'）','source_name_translation' if translated else 'needs_editorial_name'

def plan(data,destination,report):
 destination=Path(destination).resolve();build=Path(data['workspace'])/'build';roots={Path(r['unit']):r for r in data['records']}
 # Deterministic room/version IDs preserve independent batches and authored variants.
 for record in data['records']:
  rel=Path(record['unit']).relative_to(build);identity=hashlib.sha256(str(rel).encode()).hexdigest()[:12]
  name,name_source=translate_name(record);name=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',name).strip(' .')[:80] or '未命名建筑';shape=record.get('shape','unknown') if record.get('size') else 'unknown';shape_zh=LABELS.get(shape,'未识别')
  target=(destination/shape/name/('版本_'+identity)) if record['valid'] else destination/'bugged'/'models'/rel
  record.update(target=str(target),name_zh=name,name_source=record.get('name_source') or name_source,display_name=name+'-'+shape_zh,shape=shape,shape_zh=shape_zh)
 project_roots={}
 for record in sorted(data['records'],key=lambda r:Path(r.get('master',r['unit'])).stat().st_mtime_ns if Path(r.get('master',r['unit'])).exists() else 0):
  if record['valid'] and record.get('master'):project_roots[str(project_paths(record['master'])['workdir'])]=str(Path(record['target']).parent)
 data['project_roots']=project_roots
 mapping=[]
 for item in data['files']:
  source=Path(item['source']);record=next((roots[parent] for parent in [source.parent,*source.parents] if parent in roots),None)
  if record:target=Path(record['target'])/source.relative_to(Path(record['unit']));category='valid' if record['valid'] else 'noncompliant'
  elif any(Path(root) in source.parents and source.relative_to(Path(root)).parts[0] in {'修改意见','modification_feedback'} for root in project_roots):
   root=next(root for root in project_roots if Path(root) in source.parents and source.relative_to(Path(root)).parts[0] in {'修改意见','modification_feedback'});target=Path(project_roots[root])/source.relative_to(Path(root));category='project_feedback'
  elif synthetic(source,build):target=destination/'bugged'/'test_fixtures'/source.relative_to(build);category='test_fixture'
  else:target=destination/'bugged'/'unbound_support'/source.relative_to(build);category='unbound_support'
  mapping.append(dict(item,target=str(target),category=category))
 data.update(status='planned',destination=str(destination),mapping=mapping)
 write_json(report,data);return data

def execute(data,report,phase='all',batch=0):
 build=Path(data['workspace']).resolve()/'build';dest=Path(data['destination']).resolve()
 if phase=='remove':return remove_sources(data,report,batch)
 if dest==build or build in dest.parents:raise ValueError('目标不能放在待清理的build目录内')
 # A changed/new source requires a new plan. No recursive source deletion is used.
 for item in data['mapping']:
  source=Path(item['source']).resolve();target=Path(item['target']).resolve()
  if build not in source.parents or dest not in target.parents:raise ValueError('迁移范围越界')
  stat=source.stat()
  if stat.st_size!=item['size'] or stat.st_mtime_ns!=item['mtime_ns']:raise ValueError('源文件在审计后变化，请重新规划：'+str(source))
  if target.exists() and not item.get('copied'):raise FileExistsError('拒绝覆盖已有目标：'+str(target))
 count=0
 for index,item in enumerate(data['mapping']):
  if item.get('copied'):continue
  if batch and count>=batch:
   data['status']='copying';write_json(report,data);return
  count+=1
  source=Path(item['source']);target=Path(item['target']);target.parent.mkdir(parents=True,exist_ok=True)
  original=sha(source);shutil.copy2(source,target)
  if sha(target)!=original:raise ValueError('复制哈希不一致：'+str(source))
  item['sha256']=original;item['copied']=True
  if index%300==0:write_json(report,data);print(json.dumps(dict(copied=index,total=len(data['mapping']))),flush=True)
 if phase=='copy':
  data['status']='copied';write_json(report,data);return
 # All original byte copies remain in destination. Operational JSON is rebased;
 # originals are saved beside it, preserving old hash-bound review evidence.
 exact={item['source']:item['target'] for item in data['mapping']};prefixes={**data.get('project_roots',{}),**{record['unit']:record['target'] for record in data['records']}}
 exact_normalized={key.replace('\\','/').casefold():value for key,value in exact.items()}
 prefix_normalized={key.replace('\\','/').casefold():value for key,value in prefixes.items()}
 order=sorted(prefix_normalized,key=len,reverse=True)
 def rewrite(value):
  if isinstance(value,str):
   if not (re.match(r'^[a-zA-Z]:[\\/]',value) or value.startswith('/')):return value
   normalized=value.replace('\\','/').casefold()
   if normalized in exact_normalized:return exact_normalized[normalized]
   for prefix in order:
    if normalized.startswith(prefix+'/'):return str(Path(prefix_normalized[prefix])/Path(value.replace('\\','/')[len(prefix)+1:]))
   return value
  if isinstance(value,list):return [rewrite(child) for child in value]
  if isinstance(value,dict):return {key:rewrite(child) for key,child in value.items()}
  return value
 changed=0
 for index,item in enumerate(data['mapping']):
  if index%1000==0:print(json.dumps(dict(rebasing=index,total=len(data['mapping']))),flush=True)
  target=Path(item['target'])
  if target.suffix.lower()!='.json' or target.stat().st_size>40000000:continue
  try:
   if sha(target)!=item['sha256']:
    backup=dest/'_migration'/'original_json'/Path(item['source']).relative_to(build);backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():shutil.copy2(item['source'],backup)
    if sha(backup)!=item['sha256']:raise ValueError('原始JSON备份与源哈希不符')
    item['original_json']=str(backup);item['target_sha256']=sha(target)
   value=read_json(target);rebased=rewrite(value)
   if rebased==value:continue
   backup=dest/'_migration'/'original_json'/Path(item['source']).relative_to(build);backup.parent.mkdir(parents=True,exist_ok=True)
   if not backup.exists():shutil.copy2(item['source'],backup)
   if sha(backup)!=item['sha256']:raise ValueError('原始JSON凭据备份失败')
   write_json(target,rebased);item['original_json']=str(backup);item['target_sha256']=sha(target);changed+=1
  except (UnicodeError,json.JSONDecodeError):pass
 for record in data['records']:
  target=Path(record['target']);target.mkdir(parents=True,exist_ok=True)
  master=exact.get(record.get('master',''))
  metadata=dict(schema_version=1,name_zh=record['name_zh'],shape=record['shape'],shape_zh=record['shape_zh'],display_name=record['display_name'],description_zh=record['display_name'],
                version_name='/'.join(Path(record['unit']).parts[-2:]),source_name=record['unit'],name_source=record['name_source'],master=master,context_file=str(Path(exact[record['context']]).relative_to(target)) if record.get('context') in exact and target in Path(exact[record['context']]).parents else None,master_file_sha256=record.get('master_sha256'),geometry_sha256=record.get('geometry_sha256'),size=record.get('size'),cells=record.get('cells'),
                audit=dict(compliant=record['valid'],reasons=record['reasons'],scope='Static artifact format, explicit walls, existing seal/route records and exact sliced reconstruction. Not new visual/game/49/multiplayer acceptance.'),
                source_files_preserved=True,historical_authorization='Original receipts preserved under _migration/original_json; never reissued as new approval')
  for filename in ('coordinates.json','config.json','final_manifest.json','final_selection.json','description.json','room_description.json'):
   existing=target/filename
   original_item=next((item for item in data['mapping'] if item['target']==str(existing)),None)
   if not existing.is_file() or original_item is None:continue
   try:
    contents=read_json(existing)
    if not isinstance(contents,dict):continue
    if 'original_json' not in original_item:
     backup=dest/'_migration'/'original_json'/Path(original_item['source']).relative_to(build);backup.parent.mkdir(parents=True,exist_ok=True)
     if not backup.exists():shutil.copy2(original_item['source'],backup)
     if sha(backup)!=original_item['sha256']:raise ValueError('原始JSON备份错误')
     original_item['original_json']=str(backup)
    if filename in ('coordinates.json','config.json'):
     adapted=canonical_context(Path(original_item['source']));contents.update({key:adapted[key] for key in ('interior_probes','start','cameras') if key in adapted and key not in contents})
    contents.update(name_zh=record['name_zh'],shape=record['shape'],shape_zh=record['shape_zh'],display_name=record['display_name'],description_zh=record['display_name'])
    write_json(existing,contents);original_item['target_sha256']=sha(existing)
   except (UnicodeError,json.JSONDecodeError):pass
  existing_item=next((item for item in data['mapping'] if item['target']==str(target/'room_description.json')),None)
  write_json(target/'room_description.json',metadata)
  if existing_item:existing_item['target_sha256']=sha(target/'room_description.json')
 data['rebased_json']=changed;data['status']='copied_verified';write_json(report,data)
 if phase=='rebase':return
 return remove_sources(data,report,batch)

def remove_sources(data,report,batch=0):
 build=Path(data['workspace']).resolve()/'build';dest=Path(data['destination']).resolve()
 if data['status'] not in ('copied_verified','removing'):raise ValueError('须先完成复制和重定向')
 # Only now remove each exact source after checking its unchanged bytes and retained copy.
 count=0
 for index,item in enumerate(data['mapping']):
  if item.get('source_removed'):continue
  if batch and count>=batch:data['status']='removing';write_json(report,data);return
  count+=1
  source=Path(item['source']).resolve();target=Path(item['target']).resolve()
  retained=Path(item.get('original_json',target))
  if not source.exists() and sha(retained)==item['sha256'] and sha(target)==item.get('target_sha256',item['sha256']):item['source_removed']=True;continue
  if build not in source.parents or dest not in retained.parents or sha(retained)!=item['sha256'] or sha(target)!=item.get('target_sha256',item['sha256']):raise ValueError('删除前保留副本校验失败：'+str(source))
  if sha(source)!=item['sha256']:
   import uuid
   quarantine=dest/'bugged/concurrent_updates'/uuid.uuid4().hex/source.relative_to(build);quarantine.parent.mkdir(parents=True,exist_ok=True)
   if dest not in quarantine.resolve().parents:raise ValueError('并发更新归档越界')
   source.rename(quarantine)
   item['concurrent_path']=str(quarantine);item['concurrent_sha256']=sha(quarantine);item['source_removed']=True
   write_json(report,data);print(json.dumps(dict(concurrent_update=str(source)),ensure_ascii=False),flush=True);continue
  source.unlink();item['source_removed']=True
  if index%300==0:write_json(report,data);print(json.dumps(dict(removed=index,total=len(data['mapping']))),flush=True)
 parents=sorted({parent for item in data['mapping'] for parent in Path(item['source']).parents if build in parent.parents},key=lambda p:len(p.parts),reverse=True)
 for parent in parents:
  if build not in parent.resolve().parents:raise ValueError('空目录清理越界')
  try:parent.rmdir()
  except OSError:pass
 data['status']='complete';data['summary']=dict(units=len(data['records']),compliant=sum(r['valid'] for r in data['records']),files=len(data['mapping']),categories=dict(Counter(i['category'] for i in data['mapping'])))
 write_json(report,data);print(json.dumps(data['summary'],ensure_ascii=False),flush=True)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--report',type=Path,required=True);parser.add_argument('--execute',action='store_true');parser.add_argument('--reuse-audit',action='store_true');parser.add_argument('--phase',choices=['all','copy','rebase','remove'],default='all');parser.add_argument('--batch',type=int,default=0);parser.add_argument('--resume',action='store_true');parser.add_argument('--limit',type=int,default=0);args=parser.parse_args()
 data=read_json(args.report) if args.reuse_audit else audit(args.workspace,args.report,args.resume,args.limit)
 if data['status']=='auditing':return
 if data['status']=='complete':
  print(json.dumps(data.get('summary',{}),ensure_ascii=False));return
 if args.phase=='all' and 'mapping' not in data:data=plan(data,Path(args.workspace).resolve()/'nbt_models',args.report)
 if args.phase=='all' and any(item.get('source_removed') for item in data.get('mapping',[])):args.phase='remove'
 if args.execute:execute(data,args.report,args.phase,args.batch)
if __name__=='__main__':main()
