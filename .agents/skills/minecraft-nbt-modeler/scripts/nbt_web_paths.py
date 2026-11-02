"""Resolve an authoring project's root and allocate a new sibling version."""
from pathlib import Path
import re
from datetime import datetime, timezone, timedelta
VERSION=re.compile(r'^(v|detail_v|refined_v)(\d+)$',re.I)
INFRA={'master','masters','runtime','parts','revision','delivery'}
def project_paths(source):
    source=Path(source).resolve()
    parent=source.parent
    while parent.name in INFRA:parent=parent.parent
    match=VERSION.fullmatch(parent.name)
    if parent.name.startswith(('版本_','v_')) and (parent/'room_description.json').is_file():return dict(workdir=parent.parent,version=parent,prefix=None,width=2)
    if match:return dict(workdir=parent.parent,version=parent,prefix=match[1],width=len(match[2]))
    if parent.parent.name=='versions':return dict(workdir=parent.parent.parent,version=parent,prefix=None,width=2)
    if parent.name=='refined':return dict(workdir=parent.parent,version=parent,prefix='refined_v',width=1)
    return dict(workdir=parent,version=parent,prefix=None,width=2)
def reserve_version(source,workdir=None):
    info=project_paths(source);root=Path(workdir).resolve() if workdir else info['workdir']
    skill=Path(__file__).resolve().parents[1]
    if root==skill or skill in root.parents or root==Path(root.anchor):raise ValueError('请选择实际建筑工作文件夹')
    root.mkdir(parents=True,exist_ok=True)
    if info['prefix']:
        prefix=info['prefix'];numbers=[int(m.group(1)) for p in root.iterdir() if (m:=re.fullmatch(re.escape(prefix)+r'(\d+)',p.name))]
        number=max(numbers,default=0)+1
        while True:
            target=root/(prefix+str(number).zfill(info['width']))
            try:target.mkdir();return root,target
            except FileExistsError:number+=1
    base=root/'versions';base.mkdir(exist_ok=True)
    stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d_%H%M%S_web_edit')
    number=1
    while True:
        target=base/(stamp if number==1 else stamp+'_'+str(number))
        try:target.mkdir();return root,target
        except FileExistsError:number+=1
