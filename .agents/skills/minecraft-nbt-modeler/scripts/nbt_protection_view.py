"""Exact read-only display mask derived from the same protection policy as preview/export."""
from pathlib import Path
import hashlib
import json


class ProtectionConflict(ValueError):
    def __init__(self,label,points):
        points=sorted(set(tuple(p) for p in points));self.details=dict(kind='protection_conflict',label=label,positions=[list(p) for p in points[:4096]],total=len(points),truncated=len(points)>4096)
        super().__init__(f'步骤“{label}”触及保护区：{points[:8]}。请移动构件或缩小范围；允许覆盖不会取消保护。')


def mask(request):
    from nbt_refine import read_master,protections
    from nbt_library import canonical_context
    source=Path(request['source']).resolve();digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if request.get('source_sha256')!=digest:raise ValueError('源建筑已改变，请重新打开后查看保护区')
    model,_=read_master(source);context=Path(request['context']).resolve() if request.get('context') else None
    if not context:return dict(schema_version=1,source_sha256=digest,size=list(model.size),runs=[],count=0,bounds=None,available=False,reason='未关联坐标资料，无法显示保护区')
    context_hash=hashlib.sha256(context.read_bytes()).hexdigest();config=canonical_context(context)
    points=sorted((p for p in protections(model,config) if model.in_bounds(p)),key=lambda p:(p[1],p[2],p[0]));runs=[]
    for x,y,z in points:
        if runs and runs[-1][1:3]==[y,z] and runs[-1][0]+runs[-1][3]==x:runs[-1][3]+=1
        else:runs.append([x,y,z,1])
    if len(runs)>200000:raise ValueError('保护区显示数据超过20万段，请缩小坐标资料中的保护范围')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=digest or hashlib.sha256(context.read_bytes()).hexdigest()!=context_hash:raise ValueError('读取期间建筑或坐标资料已改变，请刷新保护区')
    bounds=dict(lo=[min(p[i] for p in points) for i in range(3)],hi=[max(p[i] for p in points) for i in range(3)]) if points else None
    return dict(schema_version=1,source_sha256=digest,context_sha256=context_hash,size=list(model.size),runs=runs,count=len(points),bounds=bounds,available=True,asset_written=False)
