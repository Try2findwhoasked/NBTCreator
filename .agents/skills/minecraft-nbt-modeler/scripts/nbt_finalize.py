"""Explicit final NBT delivery into a version-mirrored _exports directory."""
import argparse,hashlib,json,shutil
from datetime import datetime,timezone,timedelta
from pathlib import Path
from nbt_model import Model,load
from nbt_refine import read_master,validate,layout
from nbt_web_paths import project_paths
from nbt_whole_validation import validation_mode

def sha(file):return hashlib.sha256(Path(file).read_bytes()).hexdigest()
def write(file,value):Path(file).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def release_path(workspace,source):
    workspace=Path(workspace).resolve();version=project_paths(source)['version'];models=workspace/'nbt_models'
    if not version.is_relative_to(models) or version==models or version.is_relative_to(models/'_exports'):raise ValueError('定稿源必须位于当前工作区的建筑版本目录')
    if not (models/'_exports').resolve().is_relative_to(models.resolve()):raise ValueError('交付根目录不能指向工作区以外')
    target=models/'_exports'/version.relative_to(models)
    if not target.resolve().is_relative_to((models/'_exports').resolve()):raise ValueError('交付路径越界')
    return target
def export_binary(model,walls,config,checks,target):
    from nbt_delivery import export_delivery,verify_delivery
    from nbt_snbt import write_binary
    target=Path(target);target.mkdir(parents=True,exist_ok=False)
    model.seal_record=checks['recapped_seal'];model.stage='opened';model.final_fingerprint=model.fingerprint()
    prefix=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')+'_building_'
    cells=layout(model,config)
    if validation_mode(config)=='standalone':
        from nbt_standalone_delivery import export_standalone
        exported=export_standalone(model,walls,target,file_prefix=prefix,allow_empty_wall_mask=config.get('allow_empty_wall_mask',False),active_cells=config.get('cells'));delivery=exported['delivery'];parts=[dict(file=file) for file in exported['runtime_files']]
    else:
        delivery=export_delivery(model,cells,walls,target/'delivery','Explicit inherited global wall ownership',file_prefix=prefix)
        runtime=target/'runtime/parts';runtime.mkdir(parents=True);parts=[];recovered={}
        for cx,cz in sorted(map(tuple,cells)):
            part=Model((48,model.size[1],48))
            for (x,y,z),value in model.blocks.items():
                if (x//48,z//48)==(cx,cz):part.put((x-cx*48,y,z-cz*48),value)
            part.seal_record=model.seal_record;part.stage='opened';part.final_fingerprint=part.fingerprint();file=runtime/(prefix+f'p{cx}{cz}.nbt');part.save(file);readback=load(file)
            for (x,y,z),value in readback.blocks.items():recovered[(x+cx*48,y,z+cz*48)]=value
            parts.append(dict(file=str(file.resolve()),offset=[cx*48,0,cz*48],sha256=sha(file)))
        if recovered!=model.blocks:raise ValueError('切片回读不能重组完整主模型')
        verify_delivery(target/'delivery');write(target/'runtime/parts.json',dict(stride=48,parts=parts,exact_reassembly=True,geometry_sha256=model.fingerprint(),game_verified=False))
    master=write_binary(target/'master/model.nbt',model,walls)
    return dict(runtime_files=[p['file'] for p in parts],runtime_parts=len(parts),delivery_nbt=delivery['actual_nbt_files'],nbt_master=master['path'],binary_roundtrip=True)
def finalize(workspace,source,validated=None,register_history=True):
    workspace=Path(workspace).resolve();source=Path(source)
    if not source.is_absolute():source=workspace/source
    source=source.resolve();target=release_path(workspace,source);source_hash=sha(source)
    receipt=target/'release.json'
    if receipt.is_file():
        result=json.loads(receipt.read_text(encoding='utf8'))
        if result.get('status')!='finalized' or result.get('source_sha256')!=source_hash:raise ValueError('该版本已有不同交付内容，请另存新版本后再定稿')
        for name,item in result.get('files',{}).items():
            file=(target/name).resolve()
            if not file.is_relative_to(target) or not file.is_file() or sha(file)!=item['sha256']:raise ValueError('已定稿交付缺失或被修改，未覆盖')
        return dict(result,output=str(target),runtime_files=[str(target/p) for p in result['runtime_relative']],nbt_master=str(target/result['master_relative']),unchanged=True)
    if validated is None:
        model,walls=read_master(source)
        from nbt_detail_control import inspect_source,normalize_context,default_settings
        info=inspect_source(source,0)
        if not info['editing_ready']:raise ValueError('缺少可接手的坐标与保护配置，不能定稿')
        config=normalize_context(model,info['context'],info.get('cameras',''),default_settings());checks=validate(model,config)
        if 'wall_positions' in config:walls={tuple(p) for p in config['wall_positions']}
    else:model,walls,config,checks=validated
    result=export_binary(model,walls,config,checks,target)
    version=project_paths(source)['version']
    for name in ['coordinates.json','cameras.json','room_description.json']:
        if (version/name).is_file():shutil.copy2(version/name,target/name)
    if (target/'room_description.json').is_file():
        description=json.loads((target/'room_description.json').read_text(encoding='utf8'));description.update(master='master/model.nbt',master_file_sha256=sha(result['nbt_master']),geometry_sha256=model.fingerprint());write(target/'room_description.json',description)
    (target/'validation').mkdir();write(target/'validation/whole_model.json',checks)
    if sha(source)!=source_hash:raise ValueError('定稿期间制作源已变化，未标记为完成')
    files={p.relative_to(target).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size) for p in target.rglob('*') if p.is_file()}
    result.update(schema_version=1,status='finalized',source=source.relative_to(workspace).as_posix(),source_sha256=source_hash,geometry_sha256=model.fingerprint(),files=files,output=str(target),runtime_relative=[Path(p).relative_to(target).as_posix() for p in result['runtime_files']],master_relative=Path(result['nbt_master']).relative_to(target).as_posix(),source_unchanged=True,game_verified=False)
    write(receipt,{k:v for k,v in result.items() if k not in {'output','runtime_files','nbt_master'}})
    if register_history:
        from nbt_history import record_produced_version
        result['history']=record_produced_version(workspace,source,message='定稿并导出 NBT',actor='human')
    return result
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('--source',required=True);args=parser.parse_args()
    try:print(json.dumps(finalize(args.workspace,args.source),ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError,AssertionError) as error:print(json.dumps(dict(error=str(error)),ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
