"""Conservative, source-preserving recovery into a newly classified master candidate."""
import argparse
import gzip
import hashlib
import json
import math
import re
import uuid
from pathlib import Path
from nbt_assembly import Volume
from nbt_model import AIR, state
from nbt_refine import read_master, save_master
from nbt_project_batch import source_path, write

CATEGORIES=('single','long','square','l_shape','t_shape','cross','standalone','irregular')

def recover_model(source):
    changes=[]
    if source.stat().st_size>64*1024*1024:raise ValueError('文件超过64MiB，需单独检查')
    with gzip.open(source,'rb') as stream:raw=stream.read(256*1024*1024+1)
    if len(raw)>256*1024*1024:raise ValueError('解压后的模型超过256MiB')
    if source.suffix.lower()=='.nbt':
        from generate_sealed_models import read_nbt
        data=read_nbt(source,raw=raw)
        if data.get('DataVersion')!=3465:raise ValueError('仅恢复Java 1.20.1（DataVersion 3465），不自动转换版本')
        if data.get('entities') or 'palettes' in data:raise ValueError('含实体或多套调色板，需要人工处理，未丢弃任何内容')
        palette=[state(v) for v in data['palette']]
        if not 1<=len(palette)<=4096:raise ValueError('调色板无效')
        blocks=[]
        for block in data['blocks']:
            if set(block)-{'pos','state'}:raise ValueError('含方块实体或未知方块字段，不能无损恢复')
            index=block['state']
            if type(index) is not int or not 0<=index<len(palette):raise ValueError('方块调色板索引无效')
            blocks.append((block['pos'],palette[index]))
        changes.append('将结构NBT读取为完整主模型；未列出的格按结构格式解释为空气，未导出NBT')
        walls=[]
    else:
        data=json.loads(raw)
        if data.get('entities') or data.get('block_entities'):raise ValueError('主模型含实体资料，需要人工处理')
        if data.get('absent_positions',AIR)!=AIR:raise ValueError('未定义格不是空气，不能自动解释')
        blocks=data['blocks'];walls=data.get('wall_positions',[])
    size=data['size']
    if not isinstance(size,list) or len(size)!=3 or any(type(n) is not int or not 1<=n<=294 for n in size) or math.prod(size)>2_000_000:raise ValueError('尺寸无效或体积超过200万格')
    if not isinstance(blocks,list) or len(blocks)>2_000_000:raise ValueError('方块列表无效或过大')
    model=Volume(size);seen={};duplicates=0
    def position(value):
        if not isinstance(value,(list,tuple)) or len(value)!=3 or any(type(n) is not int for n in value):raise ValueError('方块坐标无效')
        p=tuple(value)
        if not model.in_bounds(p):raise ValueError('发现越界方块或墙层，需人工处理')
        return p
    for entry in blocks:
        if not isinstance(entry,(list,tuple)) or len(entry)!=2:raise ValueError('方块记录无效')
        p=position(entry[0]);value=state(entry[1])
        if p in seen:
            if seen[p]!=value:raise ValueError('同一坐标有冲突方块，不能猜测保留哪一个')
            duplicates+=1
        seen[p]=value;model.put(p,value)
    if not model.blocks:raise ValueError('没有可恢复的实体方块')
    mask={position(p) for p in walls}
    if any(p not in model.blocks for p in mask):raise ValueError('墙层指向空气，需人工确认归属')
    if duplicates:changes.append(f'合并{duplicates}条同坐标同材质重复记录')
    if source.suffix.lower()!='.nbt' and data.get('geometry_sha256')!=model.fingerprint():changes.append('依据实际方块重建缺失或过期的几何哈希；未改变几何')
    return model,mask,changes

def repair(workspace,source,category='auto',source_sha256=None):
    workspace=Path(workspace).resolve();source=source_path(workspace,str(source))
    if category not in ('auto',*CATEGORIES):raise ValueError('未知归类')
    if source.stat().st_size>64*1024*1024:raise ValueError('文件超过64MiB，需单独检查')
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    if source_sha256 is not None and source_sha256!=before:raise ValueError('源文件已变化，请重新选择')
    identifier=uuid.uuid4().hex;directory=workspace/'.nbtcreator/repairs'/identifier
    if not directory.resolve().is_relative_to(workspace):raise ValueError('报告路径越界')
    report=dict(id=identifier,status='failed',source=source.relative_to(workspace).as_posix(),source_sha256=before,source_unchanged=True,nbt_exported=False,approval_created=False,design='pending_visual_review')
    try:
        model,walls,changes=recover_model(source)
        selected=category;basis='用户选择'
        if selected=='auto':
            selected=next((part for part in reversed(source.relative_to(workspace/'nbt_models').parts[:-1]) if part in CATEGORIES),'standalone');basis='原目录分类' if selected!='standalone' else '无可靠分类时归入独立结构'
            descriptor=source.parent/'room_description.json'
            if descriptor.is_file():
                try:
                    value=json.loads(descriptor.read_text(encoding='utf-8-sig')).get('shape')
                    if value in CATEGORIES:selected=value;basis='原模型分类资料'
                except (ValueError,OSError):pass
        name=re.sub(r'[^\w\-\u4e00-\u9fff]','_',source.parent.name)[:60] or 'model'
        target=(workspace/'nbt_models'/selected/('recovered_'+name)/('repair_'+identifier)).resolve()
        if not target.is_relative_to((workspace/'nbt_models').resolve()):raise ValueError('归类目标路径越界')
        staging=directory/'candidate';staging.mkdir(parents=True)
        save_master(staging/'recovered.master.json.gz',model,walls)
        disk,mask=read_master(staging/'recovered.master.json.gz')
        if disk.blocks!=model.blocks or mask!=walls:raise ValueError('候选回读不一致')
        write(staging/'room_description.json',dict(name_zh='修复候选_'+name,shape=selected,size=list(model.size),master='recovered.master.json.gz',version_name='修复候选',repair_source=report['source'],repair_report=f'.nbtcreator/repairs/{identifier}/report.json',geometry_sha256=model.fingerprint(),verification='pending_visual_review'))
        if hashlib.sha256(source.read_bytes()).hexdigest()!=before:raise ValueError('恢复期间源文件变化，候选未入库')
        target.parent.mkdir(parents=True,exist_ok=True);staging.rename(target)
        report.update(status='recovered_candidate',candidate=(target/'recovered.master.json.gz').relative_to(workspace).as_posix(),category=selected,category_basis=basis,changes=changes or ['源数据可读取，生成新的归类候选'],geometry_sha256=model.fingerprint(),size=list(model.size),solid_blocks=len(model.blocks),wall_blocks=len(walls))
    except Exception as error:report['error']=str(error) or '格式不受支持，需要人工检查'
    report['source_unchanged']=hashlib.sha256(source.read_bytes()).hexdigest()==before
    report['report']=f'.nbtcreator/repairs/{identifier}/report.json';write(directory/'report.json',report)
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('--source',required=True);parser.add_argument('--category',choices=('auto',*CATEGORIES),default='auto');parser.add_argument('--source-sha256');args=parser.parse_args()
    try:
        result=repair(args.workspace,args.source,args.category,args.source_sha256);print(json.dumps(result,ensure_ascii=False));return 0 if result['status']=='recovered_candidate' else 1
    except Exception as error:print(json.dumps(dict(error=str(error)),ensure_ascii=False));return 1

if __name__=='__main__':raise SystemExit(main())
