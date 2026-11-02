"""Finalize relocation metadata without issuing approval receipts."""
from pathlib import Path
import argparse,json,csv,collections,shutil
from nbt_library import read_json,write_json,sha

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args();data=read_json(args.report)
 if data['status']!='copied_verified':raise ValueError('先完成目标复制和路径重定向')
 dest=Path(data['destination']);build=Path(data['workspace'])/'build';mapping={str(Path(item['target']).resolve()):item for item in data['mapping']}
 candidates=[item for item in data['mapping'] if Path(item['target']).name in {'artifact_ledger.json','artifacts_manifest.json','final_manifest.json','manifest.json','delivery.json','whole_cut_manifest.json','parts.json','conversion.json'}]
 count=0
 for _ in range(3):
  changed=0
  for item in candidates:
   path=Path(item['target'])
   if not path.is_file() or path.stat().st_size>10000000:continue
   try:value=read_json(path)
   except (ValueError,UnicodeError):continue
   edited=False
   def visit(obj):
    nonlocal edited
    if isinstance(obj,dict):
     file=obj.get('file') or obj.get('path')
     if isinstance(file,str) and isinstance(obj.get('sha256'),str):
      linked=Path(file) if Path(file).is_absolute() else path.parent/file
      reference=mapping.get(str(linked.resolve()))
      if reference and linked.resolve()!=path.resolve() and linked.is_file() and obj['sha256']==reference['sha256']:
       actual=sha(linked)
       if actual!=obj['sha256']:obj['sha256_before_relocation']=obj['sha256'];obj['sha256']=actual;edited=True
     for child in list(obj.values()):visit(child)
    elif isinstance(obj,list):
     for child in obj:visit(child)
   visit(value)
   if not edited:continue
   if not item.get('original_json'):
    backup=dest/'_migration/original_json'/Path(item['source']).relative_to(build);backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():shutil.copy2(item['source'],backup)
    if sha(backup)!=item['sha256']:raise ValueError('原始清单备份不符')
    item['original_json']=str(backup)
   write_json(path,value);item['target_sha256']=sha(path);changed+=1;count+=1
  if not changed:break
 summary=dict(status='copied_verified',versions=len(data['records']),compliant_versions=sum(r['valid'] for r in data['records']),room_names=len({(r['name_zh'],r['shape']) for r in data['records'] if r['valid']}),files=len(data['mapping']),categories=dict(collections.Counter(i['category'] for i in data['mapping'])),shapes=dict(collections.Counter(r['shape_zh'] for r in data['records'] if r['valid'])),hash_manifests_updated=count,scope='文件、现有静态检查记录及切片一致性归档；没有重做全部视觉或游戏验收')
 write_json(dest/'_migration/summary.json',summary)
 bad=[dict(source=r['unit'],target=r['target'],name_zh=r['name_zh'],reasons=r['reasons'],master_errors=r.get('master_errors',[])) for r in data['records'] if not r['valid']]
 write_json(dest/'bugged/index.json',dict(models=bad,note='保守隔离：包括几何错误、缺失交付/证据、测试夹具和不成套支持文件。保留原始数据，缺证不等于建筑损坏。'))
 (dest/'bugged/README.md').write_text('# 隔离归档\n\nmodels/ 保留未通过本次归档检查的模型版本；test_fixtures/ 为测试夹具；unbound_support/ 为无法绑定完整建筑的资料和支持文件。\n\n具体原因见 index.json；缺少证据不等于几何一定损坏。源文件映射和原始JSON见 ../_migration/。\n',encoding='utf8')
 with (dest/'_migration/files.csv').open('w',encoding='utf-8-sig',newline='') as stream:
  writer=csv.writer(stream);writer.writerow(['旧文件','新文件','分类','原文件SHA256','当前目标SHA256','原始JSON备份'])
  for item in data['mapping']:writer.writerow([item['source'],item['target'],item['category'],item['sha256'],item.get('target_sha256',item['sha256']),item.get('original_json','')])
 data['metadata_finalized']=True;write_json(args.report,data);print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
