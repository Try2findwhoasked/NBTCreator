"""Non-destructive legacy workspace migration with verified originals and rebased active metadata."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def relative(path,base):
    try:return os.path.relpath(path,base).replace('\\','/')
    except ValueError:return Path(path).as_posix()

def migrate(source,workspace):
    source,workspace=Path(source).resolve(),Path(workspace).resolve()
    assets=source/'nbt_models';destination=workspace/'nbt_models'
    if source==workspace or source in workspace.parents:raise ValueError('迁移目标不能位于旧工作区内部')
    if not assets.is_dir():return dict(status='absent',files=0)
    identifier=hashlib.sha256(str(source).encode()).hexdigest()[:10]
    reportdir=destination/'_migration'/('legacy_'+identifier)
    reportfile=reportdir/'migration.json'
    if reportfile.is_file():
        report=json.loads(reportfile.read_text(encoding='utf8'))
        if report.get('status')=='complete':return report
    files=[]
    for root,dirs,names in os.walk(assets,followlinks=False):
        for name in dirs:
            if (Path(root)/name).is_symlink():raise ValueError('不迁移目录符号链接')
        for name in names:
            p=Path(root)/name
            if p.is_symlink():raise ValueError('不迁移文件符号链接')
            if p.name=='NBTCreator-workspace-redirect.json':continue
            rel=p.relative_to(assets)
            target=reportdir/'preserved-runtime'/Path(*rel.parts[1:]) if rel.parts[0]=='_workspaces' else destination/rel
            if target.exists() and sha(target)!=sha(p):raise ValueError('目标已有不同文件，迁移整体拒绝：'+str(rel))
            files.append((p,target,sha(p)))
    # Refuse conflicts before copying any authoring file. Preserve all source bytes.
    reportdir.mkdir(parents=True,exist_ok=True)
    records=[]
    mappings={str(p):str(q) for p,q,_ in files}
    def rebase(v,parent):
        if isinstance(v,dict):return {k:rebase(x,parent) for k,x in v.items()}
        if isinstance(v,list):return [rebase(x,parent) for x in v]
        if isinstance(v,str) and v in mappings:return relative(mappings[v],parent)
        return v
    for old,new,digest in files:
        new.parent.mkdir(parents=True,exist_ok=True)
        if not new.exists():shutil.copy2(old,new)
        if sha(new)!=digest:raise ValueError('复制校验失败')
        # Only ordinary author metadata is rewritten. Approval/hash-bound runtime
        # records remain preserved bytes, never forged into new valid receipts.
        rewritten=False
        if new.name=='room_description.json' and '_migration' not in new.relative_to(destination).parts:
            value=json.loads(new.read_text(encoding='utf8'));updated=rebase(value,new.parent)
            if value!=updated:new.write_text(json.dumps(updated,ensure_ascii=False,indent=2)+'\n',encoding='utf8');rewritten=True
        records.append(dict(source=relative(old,workspace),target=relative(new,workspace),source_sha256=digest,target_sha256=sha(new),metadata_rebased=rewritten))
    if any(sha(old)!=digest for old,_,digest in files):raise ValueError('旧源在迁移中变化')
    report=dict(schema_version=1,status='complete',files=len(records),records=records,originals_preserved=True,approval_reused=False)
    reportfile.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    redirect=source/'NBTCreator-workspace-redirect.json'
    redirect.write_text(json.dumps(dict(workspace=relative(workspace,source),migration=relative(reportfile,source)),indent=2),encoding='utf8')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,required=True);parser.add_argument('--workspace',type=Path,default=Path.cwd());args=parser.parse_args()
    print(json.dumps(migrate(args.source,args.workspace),ensure_ascii=False))
