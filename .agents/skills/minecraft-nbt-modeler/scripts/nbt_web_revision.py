"""Convert saved website settings / preview JSON into a new authoring version.

Run only for a human-selected saved effect. This script never fabricates approval
receipts, changes the source version or installs files into a world/room pool.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
from datetime import datetime,timezone,timedelta
from nbt_detail_control import read_json,write_json,digest,canonical,preview_effect,normalize_context
from nbt_refine import read_master,save_master,validate,layout,protections,point
from nbt_model import Model,load
from nbt_assembly import Volume
from nbt_delivery import export_delivery,verify_delivery
from nbt_web_paths import project_paths,reserve_version
from nbt_request_paths import read_request,portable_request
from nbt_whole_validation import validation_mode

def resolve_request(file):
    file=Path(file).resolve()
    if file.is_dir():
        file=next((candidate for candidate in (file/'request.json',file/'settings.json',file.parent/'request.json') if candidate.is_file()),file)
    if not file.is_file():raise ValueError('请选择网页保存的设置JSON，或包含request.json的任务目录')
    data=read_json(file)
    if isinstance(data,dict) and isinstance(data.get('settings'),dict) and data.get('source'):return file,read_request(file),None
    request_file=next((candidate for candidate in (file.parent/'settings.json',file.parent/'request.json',file.parent.parent/'request.json') if candidate.is_file()),None)
    if request_file is None:raise ValueError('此JSON不含设置。预览after.json需保留同任务的request.json，不能只复制单张预览JSON')
    request=read_request(request_file)
    if not isinstance(request.get('settings'),dict) or not request.get('source'):raise ValueError('配套request.json格式无效')
    snapshot=data if file.name=='after.json' and 'blocks' in data else None
    if not snapshot and file.name not in {'plan.json','bundle.json','job.json'}:raise ValueError('不支持此JSON，请使用保存的设置或after.json')
    return request_file,request,snapshot

def convert_web_json(input_file,workdir=None):
    request_file,request,expected=resolve_request(input_file)
    source=Path(request['source']).resolve();source_hash=digest(source)
    draft_only=request.get('draft_only',False)
    if type(draft_only) is not bool:raise ValueError('制作版保存选项无效')
    if request.get('source_sha256') and request['source_sha256']!=source_hash:raise ValueError('原建筑已变化，请重新打开原版本并保存设置')
    baseline,base_walls=read_master(source)
    settings=request['settings'];config=normalize_context(baseline,request['context'],request.get('cameras',''),settings)
    if 'wall_positions' in config:
        base_walls={point(p) for p in config['wall_positions']}
        if any(not baseline.in_bounds(p) for p in base_walls):raise ValueError('显式墙mask超出原模型边界')
    base_walls={p for p in base_walls if p in baseline.blocks}
    standalone=validation_mode(config)=='standalone'
    original_config=read_json(request['context']);baseline_checks=validate(baseline,config)
    root=Path(workdir).resolve() if workdir else project_paths(source)['workdir']
    skill=Path(__file__).resolve().parents[1]
    if root==skill or skill in root.parents or root==Path(root.anchor):raise ValueError('不能把skill安装目录或磁盘根目录当建筑工作目录')
    if not root.is_dir():raise ValueError('原建筑工作文件夹不存在，请检查源路径')
    with tempfile.TemporaryDirectory(prefix='.web_conversion_',dir=root) as scratch:
        result=preview_effect(dict(request,source_sha256=source_hash),Path(scratch)/'preview')
        after=read_json(result['snapshot'])
        if expected is not None:
            # Match the exact displayed state array as well as source/geometry identity.
            if any(expected.get(key)!=after.get(key) for key in ('source_sha256','geometry_sha256','size','blocks','wall_positions')):raise ValueError('预览JSON与原稿/设置不一致，拒绝导出不同于所看效果的建筑')
        model=Volume(after['size'])
        for p,value in after['master_blocks']:
            p=tuple(p)
            if p in model.blocks:raise ValueError('预览中有重复坐标')
            model.put(p,value)
        if model.fingerprint()!=after['geometry_sha256']:raise ValueError('修改后几何哈希不符')
        walls={tuple(p) for p in after['wall_positions'] if model.get(tuple(p)) not in {'minecraft:air','minecraft:cave_air','minecraft:void_air'}};cells=layout(model,config)
        if standalone:
            if not walls and config.get('allow_empty_wall_mask') is not True:raise ValueError('独立素材的空墙mask须显式设置allow_empty_wall_mask=true')
        elif any(not any((p[0]//48,p[2]//48)==tuple(cell) for p in walls) for cell in cells):raise ValueError('每个有效分片都需要原稿中明确记录的墙体归属，不能按方块材质猜测')
        from nbt_change_policy import enforce_changes,change_sets
        difference=enforce_changes(baseline.blocks,model.blocks,base_walls,walls,
            protected=protections(baseline,config),maximum=settings.get('max_changed_blocks',4096))
        geometry_changed,layers_changed=change_sets(baseline.blocks,model.blocks,base_walls,walls)
        checks=validate(model,config)
        if digest(source)!=source_hash:raise ValueError('转换期间原建筑变化，请重新导出')
        work,target=reserve_version(source,workdir)
        input_hash=digest(input_file) if Path(input_file).is_file() else digest(request_file)
        receipt=dict(schema_version=1,status='writing',source=str(source),source_sha256=source_hash,
            input=str(Path(input_file).resolve()),input_sha256=input_hash,settings_sha256=canonical(settings),
            source_version=str(project_paths(source)['version']),output=str(target),**difference,
            intent='Explicit saved-effect conversion; not an approval receipt or game deployment',runtime_verified=False)
        write_json(target/'conversion.json',receipt)
        try:
            master=target/'master';master.mkdir()
            from nbt_snbt import save_snbt
            authored=master/'model.snbt';save_snbt(authored,model,walls,palette=getattr(baseline,'_snbt_palette',None),extras=getattr(baseline,'_snbt_extras',None))
            write_json(master/'wall_mask.json',dict(geometry_sha256=model.fingerprint(),wall_positions=[list(p) for p in sorted(walls)]))
            disk,disk_walls=read_master(authored)
            if disk.blocks!=model.blocks or disk_walls!=walls:raise ValueError('完整主模型回读不一致')
            archive=work/'修改意见'/'设置'/source_hash;archive.mkdir(parents=True,exist_ok=True)
            archive_file=archive/(canonical(request)+'.json')
            try:
                with archive_file.open('x',encoding='utf8') as stream:json.dump(request,stream,ensure_ascii=False,indent=2)
            except FileExistsError:
                if canonical(read_json(archive_file))!=canonical(request):raise ValueError('已归档设置内容不符')
            receipt['settings_archive']=str(archive_file)
            write_json(target/'settings.json',portable_request(request));write_json(target/'input.json',read_json(input_file) if Path(input_file).is_file() else read_json(request_file))
            write_json(target/'coordinates.json',original_config)
            cameras=read_json(request['cameras']) if request.get('cameras') else config['cameras'];write_json(target/'cameras.json',cameras)
            validation=target/'validation';validation.mkdir();write_json(validation/'baseline.json',baseline_checks);write_json(validation/'whole_model.json',checks)
            write_json(target/'changes.json',dict(changes=[dict(pos=list(p),before=baseline.get(p),after=model.get(p)) for p in sorted(geometry_changed)],
                wall_membership_changed=[list(p) for p in sorted(layers_changed)],
                wall_changes=[dict(pos=list(p),before_wall=p in base_walls,after_wall=p in walls) for p in sorted(layers_changed)],**difference))
            (target/'previews').mkdir();write_json(target/'previews/README.json',dict(status='not_rendered',reason='Generate new previews from this master; original-version images are not copied'))
            if digest(source)!=source_hash:raise ValueError('导出期间原稿变化，当前版本不能标为完成')
            from nbt_library import register_building
            description=next((p/'room_description.json' for p in [source.parent,*list(source.parents)[:4]] if (p/'room_description.json').is_file()),None)
            if description:
                register_building(authored,read_json(description)['name_zh'],cells,mode='standalone' if standalone else None)
            receipt.update(status='complete',master=str(authored),runtime_parts=0,runtime_files=[],delivery_nbt=0,geometry_sha256=model.fingerprint(),source_unchanged=True,source_format='snbt',draft_only=draft_only)
            write_json(target/'conversion.json',receipt)
            from nbt_history import source_workspace,record_produced_version
            workspace=source_workspace(authored)
            if not draft_only:
                from nbt_finalize import finalize
                released=finalize(workspace,authored,validated=(model,walls,config,checks),register_history=False)
                receipt.update(runtime_parts=released['runtime_parts'],runtime_files=released['runtime_files'],delivery_nbt=released['delivery_nbt'],nbt_master=released['nbt_master'],release_dir=released['output'],finalized=True)
                write_json(target/'conversion.json',receipt)
            receipt['history']=record_produced_version(workspace,authored,parent=source,message='保存 SNBT 制作版' if draft_only else '定稿并导出 NBT',actor='human',set_current=True)
            return receipt
        except Exception as error:
            receipt.update(status='failed',error=str(error));write_json(target/'conversion.json',receipt);raise

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--workdir',type=Path)
    args=parser.parse_args()
    try:print(json.dumps(dict(ok=True,result=convert_web_json(args.input,args.workdir)),ensure_ascii=False));return 0
    except Exception as error:print(json.dumps(dict(ok=False,error=str(error)),ensure_ascii=False));return 1

if __name__=='__main__':raise SystemExit(main())
