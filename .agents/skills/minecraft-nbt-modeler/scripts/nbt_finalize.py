"""Explicit final NBT delivery into a version-mirrored _exports directory."""
import argparse,hashlib,json,shutil,tempfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
from nbt_model import Model,load
from nbt_library import canonical_context,coordinate_snapshot,saved_coordinates
from nbt_refine import read_master,validate,layout,binary_wall_mask_hash,resolve_wall_mask,source_binding
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
    prefix=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')+'_building_'
    cells=layout(model,config)
    if validation_mode(config)=='standalone':
        from nbt_standalone_delivery import export_standalone
        exported=export_standalone(model,walls,target,file_prefix=prefix,allow_empty_wall_mask=config.get('allow_empty_wall_mask',False),active_cells=config.get('cells'),checks=checks,cell_size=config.get('cell_size',48));delivery=exported['delivery'];parts=[dict(file=file) for file in exported['runtime_files']]
    else:
        model.seal_record=checks['recapped_seal'];model.stage='opened';model.final_fingerprint=model.fingerprint()
        delivery=export_delivery(model,cells,walls,target/'delivery','Explicit inherited global wall ownership',file_prefix=prefix)
        runtime=target/'runtime/parts';runtime.mkdir(parents=True);parts=[];recovered={}
        for cx,cz in sorted(map(tuple,cells)):
            part=Model((48,model.size[1],48))
            for (x,y,z),value in model.blocks.items():
                if (x//48,z//48)==(cx,cz):part.put((x-cx*48,y,z-cz*48),value)
            part.seal_record=model.seal_record;part.stage='opened';part.final_fingerprint=part.fingerprint();file=runtime/(prefix+f'p{cx}{cz}.nbt');part.save(file);readback=load(file)
            for (x,y,z),value in readback.blocks.items():recovered[(x+cx*48,y,z+cz*48)]=value
            parts.append(dict(file='parts/'+file.name,offset=[cx*48,0,cz*48],sha256=sha(file)))
        if recovered!=model.blocks:raise ValueError('切片回读不能重组完整主模型')
        verify_delivery(target/'delivery');write(target/'runtime/parts.json',dict(stride=48,parts=parts,exact_reassembly=True,geometry_sha256=model.fingerprint(),game_verified=False))
    master=write_binary(target/'master/model.nbt',model,walls)
    runtime_files=[str((target/'runtime'/p['file']).resolve()) for p in parts]
    return dict(runtime_files=runtime_files,runtime_parts=len(parts),delivery_nbt=delivery['actual_nbt_files'],nbt_master=master['path'],binary_roundtrip=True)


def release_inputs(source, context):
    from nbt_detail_control import canonical

    context_data,context_fingerprint=coordinate_snapshot(context) if context else (None,None)
    return dict(source_sha256=sha(source),binary_wall_mask_sha256=binary_wall_mask_hash(source),
                context_sha256=canonical(context_data),context_fingerprint=context_fingerprint)


def released_result(target, result):
    return dict(result,output=str(target),runtime_files=[str(target/p) for p in result['runtime_relative']],
                nbt_master=str(target/result['master_relative']))


def load_release(target, inputs):
    result=json.loads((target/'release.json').read_text(encoding='utf8'))
    released_inputs=result.get('source_inputs')
    comparable_inputs=inputs
    if isinstance(released_inputs,dict) and 'context_fingerprint' not in released_inputs:
        comparable_inputs={key:value for key,value in inputs.items() if key!='context_fingerprint'}
    if (result.get('status')!='finalized' or result.get('source_sha256')!=inputs['source_sha256']
            or 'source_inputs' in result and released_inputs!=comparable_inputs):
        raise ValueError('该版本的制作源或坐标配置已变化，请另存新版本后再定稿')
    files=result['files']
    published={result['master_relative'],*result['runtime_relative']}
    if not published.issubset(files):
        raise ValueError('定稿清单缺少模型或分片的文件校验')
    for name,item in files.items():
        file=(target/name).resolve()
        if not file.is_relative_to(target) or not file.is_file() or sha(file)!=item['sha256']:
            raise ValueError('已定稿交付缺失或被修改，未覆盖')
    return dict(released_result(target,result),unchanged=True)


def inspect_inputs(workspace,source):
    from nbt_agent_protocol import canonical

    workspace=Path(workspace).resolve();source=(workspace/Path(source)).resolve()
    release_path(workspace,source)
    inputs=source_binding(source)
    return dict(inputs,inputs_sha256=hashlib.sha256(canonical(inputs)).hexdigest())


def finalize(workspace,source,*,register_history=True,expected_source_sha256=None,expected_inputs_sha256=None):
    workspace=Path(workspace).resolve();source=Path(source)
    if not source.is_absolute():source=workspace/source
    source=source.resolve();target=release_path(workspace,source)
    from nbt_working_model import WorkingModel,managed_manifest
    manifest=managed_manifest(source)
    managed_building=manifest and manifest['kind']=='building'
    if managed_building and manifest['phase']!='opened':
        raise ValueError(f"受管建筑当前制作阶段为 {manifest['phase']}，完成封闭策略与声明开洞流程并保存 opened 版后才能定稿")
    context=saved_coordinates(source)
    inputs=release_inputs(source,context)
    if expected_source_sha256 is not None and inputs['source_sha256']!=expected_source_sha256:
        raise ValueError('已保存制作源发生变化，请重新检查后定稿')
    if expected_inputs_sha256 is not None:
        reviewed=inspect_inputs(workspace,source)
        if reviewed['inputs_sha256']!=expected_inputs_sha256 or reviewed['source_sha256']!=inputs['source_sha256']:
            raise ValueError('审阅绑定的制作源、保护配置或墙层已变化，请重新检查后定稿')
    receipt=target/'release.json'
    if receipt.is_file():
        return load_release(target,inputs)
    if target.exists():
        raise FileExistsError('已有不完整的旧定稿目录，请保留现场并使用新制作版本')
    if managed_building:
        working=WorkingModel.open(workspace,source,source_sha256=inputs['source_sha256'])
        if working.parent_revision!=manifest['revision']:
            raise ValueError('定稿期间受管制作清单已变化')
        model,walls,config=working.model,working.walls,working.context
        export_context=config
        checks=dict(working.validate()['whole_model'],phase=manifest['phase'])
        if 'master/preopening.snbt' in manifest['files'] or working.preopening is not None:
            if ('master/preopening.snbt' not in manifest['files'] or not working.preopening
                    or working.preopening.get('passed') is not True):
                raise ValueError('受管制作版的开洞前原始证据不完整')
            closed,_=working._closed
            preopening=closed.check_sealed(config.get('interior_probes',[]))
            if preopening!=working.preopening:
                raise ValueError('受管制作版的开洞前原始证据与回读不一致')
            checks.update(preopening=preopening,original_preopening_proof=True)
    else:
        from nbt_detail_control import context_readiness,default_settings,normalize_validation_context
        model,walls=read_master(source)
        if not context_readiness(model,context,source)['ready']:
            raise ValueError('缺少可接手的坐标与保护配置，不能定稿')
        config=normalize_validation_context(model,context,default_settings(),source=source)
        checks=validate(model,config)
        walls=resolve_wall_mask(model,walls,config)
        export_context=dict(canonical_context(context),**config)
        export_context.pop('floor_context',None)
    version=project_paths(source)['version']
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.finalize-',dir=target.parent) as temporary:
        stage=Path(temporary)/'release'
        result=export_binary(model,walls,config,checks,stage)
        write(stage/'coordinates.json',export_context)
        for name in ['cameras.json','room_description.json']:
            if (version/name).is_file():shutil.copy2(version/name,stage/name)
        description_file=stage/'room_description.json'
        if description_file.is_file():
            description=json.loads(description_file.read_text(encoding='utf8'))
            description.update(master='master/model.nbt',context_file='coordinates.json',master_file_sha256=sha(result['nbt_master']),
                               geometry_sha256=model.fingerprint())
            write(description_file,description)
        (stage/'validation').mkdir();write(stage/'validation/whole_model.json',checks)
        if release_inputs(source,saved_coordinates(source))!=inputs:
            raise ValueError('定稿期间制作源或坐标配置已变化')
        if manifest and managed_manifest(source)!=manifest:
            raise ValueError('定稿期间受管制作清单已变化')
        if expected_inputs_sha256 is not None and inspect_inputs(workspace,source)!=reviewed:
            raise ValueError('定稿期间审阅绑定的输入已变化')
        files={p.relative_to(stage).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size)
               for p in stage.rglob('*') if p.is_file()}
        result.update(schema_version=1,status='finalized',source=source.relative_to(workspace).as_posix(),
                      source_sha256=inputs['source_sha256'],source_inputs=inputs,geometry_sha256=model.fingerprint(),
                      files=files,runtime_relative=[Path(p).relative_to(stage).as_posix() for p in result.pop('runtime_files')],
                      master_relative=Path(result.pop('nbt_master')).relative_to(stage).as_posix(),
                      source_unchanged=True,game_verified=False)
        write(stage/'release.json',result)
        try:
            stage.rename(target)
        except OSError:
            if receipt.is_file():return load_release(target,inputs)
            raise
    result=released_result(target,result)
    if register_history:
        from nbt_history import record_produced_version
        result['history']=record_produced_version(workspace,source,message='定稿并导出 NBT',actor='human')
    return result
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('--source',required=True)
    parser.add_argument('--inspect-inputs',action='store_true');parser.add_argument('--source-sha256');parser.add_argument('--inputs-sha256');args=parser.parse_args()
    try:
        if args.inspect_inputs:
            result=inspect_inputs(args.workspace,args.source)
        else:
            if not args.source_sha256 or not args.inputs_sha256:
                raise ValueError('定稿须提供审阅时记录的 --source-sha256 与 --inputs-sha256；用 --inspect-inputs 只读查看输入')
            result=finalize(args.workspace,args.source,expected_source_sha256=args.source_sha256,expected_inputs_sha256=args.inputs_sha256)
        print(json.dumps(result,ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError,AssertionError) as error:print(json.dumps(dict(error=str(error)),ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
