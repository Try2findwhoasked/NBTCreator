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
from nbt_refine import read_master,save_master,validate,layout
from nbt_model import Model,load
from nbt_assembly import Volume
from nbt_delivery import export_delivery,verify_delivery
from nbt_web_paths import project_paths,reserve_version

def resolve_request(file):
    file=Path(file).resolve()
    if file.is_dir():
        file=next((candidate for candidate in (file/'request.json',file/'settings.json',file.parent/'request.json') if candidate.is_file()),file)
    if not file.is_file():raise ValueError('请选择网页保存的设置JSON，或包含request.json的任务目录')
    data=read_json(file)
    if isinstance(data,dict) and isinstance(data.get('settings'),dict) and data.get('source'):return file,data,None
    request_file=next((candidate for candidate in (file.parent/'settings.json',file.parent/'request.json',file.parent.parent/'request.json') if candidate.is_file()),None)
    if request_file is None:raise ValueError('此JSON不含设置。预览after.json需保留同任务的request.json，不能只复制单张预览JSON')
    request=read_json(request_file)
    if not isinstance(request.get('settings'),dict) or not request.get('source'):raise ValueError('配套request.json格式无效')
    snapshot=data if file.name=='after.json' and 'blocks' in data else None
    if not snapshot and file.name not in {'plan.json','bundle.json','job.json'}:raise ValueError('不支持此JSON，请使用保存的设置或after.json')
    return request_file,request,snapshot

def convert_web_json(input_file,workdir=None):
    request_file,request,expected=resolve_request(input_file)
    source=Path(request['source']).resolve();source_hash=digest(source)
    if request.get('source_sha256') and request['source_sha256']!=source_hash:raise ValueError('原建筑已变化，请重新打开原版本并保存设置')
    baseline,base_walls=read_master(source)
    settings=request['settings'];config=normalize_context(baseline,request['context'],request.get('cameras',''),settings)
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
        if any(not any((p[0]//48,p[2]//48)==tuple(cell) for p in walls) for cell in cells):raise ValueError('每个有效分片都需要原稿中明确记录的墙体归属，不能按方块材质猜测')
        changed=sum(baseline.get(p)!=model.get(p) for p in set(baseline.blocks)|set(model.blocks))
        if changed>settings.get('max_changed_blocks',4096):raise ValueError(f'改动{changed}个方块超过当前数量上限，请核对设置后再导出')
        checks=validate(model,config)
        if digest(source)!=source_hash:raise ValueError('转换期间原建筑变化，请重新导出')
        work,target=reserve_version(source,workdir)
        input_hash=digest(input_file) if Path(input_file).is_file() else digest(request_file)
        receipt=dict(schema_version=1,status='writing',source=str(source),source_sha256=source_hash,
            input=str(Path(input_file).resolve()),input_sha256=input_hash,settings_sha256=canonical(settings),
            source_version=str(project_paths(source)['version']),output=str(target),changed_blocks=changed,
            intent='Explicit saved-effect conversion; not an approval receipt or game deployment',runtime_verified=False)
        write_json(target/'conversion.json',receipt)
        try:
            master=target/'master';master.mkdir()
            save_master(master/'master_geometry.json.gz',model,walls)
            write_json(master/'wall_mask.json',dict(geometry_sha256=model.fingerprint(),wall_positions=[list(p) for p in sorted(walls)]))
            disk,disk_walls=read_master(master/'master_geometry.json.gz')
            if disk.blocks!=model.blocks or disk_walls!=walls:raise ValueError('完整主模型回读不一致')
            archive=work/'修改意见'/'设置'/source_hash;archive.mkdir(parents=True,exist_ok=True)
            archive_file=archive/(canonical(request)+'.json')
            try:
                with archive_file.open('x',encoding='utf8') as stream:json.dump(request,stream,ensure_ascii=False,indent=2)
            except FileExistsError:
                if canonical(read_json(archive_file))!=canonical(request):raise ValueError('已归档设置内容不符')
            receipt['settings_archive']=str(archive_file)
            write_json(target/'settings.json',request);write_json(target/'input.json',read_json(input_file) if Path(input_file).is_file() else read_json(request_file))
            write_json(target/'coordinates.json',original_config)
            cameras=read_json(request['cameras']) if request.get('cameras') else config['cameras'];write_json(target/'cameras.json',cameras)
            validation=target/'validation';validation.mkdir();write_json(validation/'baseline.json',baseline_checks);write_json(validation/'whole_model.json',checks)
            model.seal_record=checks['recapped_seal'];model.stage='opened';model.final_fingerprint=model.fingerprint()
            date=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
            room=next((part.lower() for part in source.parts if re.fullmatch(r'[rRsSlL]\d{2,3}',part.split('_')[0])), 'building').split('_')[0]
            prefix=date+'_'+room+'_'
            delivery=export_delivery(model,cells,walls,target/'delivery','Explicit inherited global wall ownership',file_prefix=prefix)
            runtime=target/'runtime/parts';runtime.mkdir(parents=True)
            parts=[];recovered={}
            for cx,cz in sorted(map(tuple,cells)):
                part=Model((48,model.size[1],48))
                for (x,y,z),value in model.blocks.items():
                    if (x//48,z//48)==(cx,cz):part.put((x-cx*48,y,z-cz*48),value)
                part.seal_record=model.seal_record;part.stage='opened';part.final_fingerprint=part.fingerprint()
                file=runtime/(prefix+f'p{cx}{cz}.nbt');part.save(file);readback=load(file)
                for (x,y,z),value in readback.blocks.items():recovered[(x+cx*48,y,z+cz*48)]=value
                parts.append(dict(file=str(file.resolve()),offset=[cx*48,0,cz*48],sha256=digest(file)))
            if recovered!=model.blocks:raise ValueError('48连续切片回读不能完整重组主模型')
            verify_delivery(target/'delivery')
            write_json(target/'runtime/parts.json',dict(stride=48,parts=parts,exact_reassembly=True,geometry_sha256=model.fingerprint(),game_verified=False,saodg49_verified=False))
            write_json(target/'changes.json',dict(changes=[dict(pos=list(p),before=baseline.get(p),after=model.get(p)) for p in sorted(set(baseline.blocks)|set(model.blocks)) if baseline.get(p)!=model.get(p)]))
            (target/'previews').mkdir();write_json(target/'previews/README.json',dict(status='not_rendered',reason='Generate new previews from this master; original-version images are not copied'))
            if digest(source)!=source_hash:raise ValueError('导出期间原稿变化，当前版本不能标为完成')
            from nbt_library import register_building
            description=next((p/'room_description.json' for p in [source.parent,*list(source.parents)[:4]] if (p/'room_description.json').is_file()),None)
            if description:
                register_building(master/'master_geometry.json.gz',read_json(description)['name_zh'],cells)
            receipt.update(status='complete',master=str(master/'master_geometry.json.gz'),runtime_parts=len(parts),runtime_files=[entry['file'] for entry in parts],delivery_nbt=delivery['actual_nbt_files'],geometry_sha256=model.fingerprint(),source_unchanged=True)
            write_json(target/'conversion.json',receipt)
            return receipt
        except Exception as error:
            receipt.update(status='failed',error=str(error));write_json(target/'conversion.json',receipt);raise

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--workdir',type=Path)
    args=parser.parse_args()
    try:print(json.dumps(dict(ok=True,result=convert_web_json(args.input,args.workdir)),ensure_ascii=False));return 0
    except Exception as error:print(json.dumps(dict(ok=False,error=str(error)),ensure_ascii=False));return 1

if __name__=='__main__':raise SystemExit(main())
