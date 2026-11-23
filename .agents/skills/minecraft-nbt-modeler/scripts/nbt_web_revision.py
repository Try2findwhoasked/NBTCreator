"""Convert saved website settings / preview JSON into a new authoring version.

Run only for a human-selected saved effect. This script never fabricates approval
receipts, changes the source version or installs files into a world/room pool.
"""
import argparse
import json
from pathlib import Path
import tempfile
from nbt_detail_control import read_json,write_json,digest,canonical,preview_effect
from nbt_refine import read_master,validate,layout,protections,resolve_wall_mask,binary_wall_mask_hash
from nbt_assembly import Volume
from nbt_project.web_paths import project_paths,reserve_version
from nbt_project.request_paths import read_request,portable_request
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
    from nbt_working_model import publication_lock
    from nbt_history import source_workspace
    source=Path(request['source']).resolve()
    workspace=source_workspace(source)
    root=Path(workdir).resolve() if workdir else project_paths(source)['workdir']
    skill=Path(__file__).resolve().parents[1]
    if root==skill or skill in root.parents or not root.is_relative_to(workspace/'nbt_models'):
        raise ValueError('请选择实际工作区 nbt_models 内的建筑目录')
    if not root.is_dir():raise ValueError('原建筑工作文件夹不存在')
    if (project_paths(source)['version']/'model-version.json').is_file() and root!=project_paths(source)['workdir']:
        raise ValueError('受管制作版沿用原建筑版本目录；跨建筑复制请先显式导入')
    with publication_lock(workspace,root):
        from nbt_working_model import WorkingModel
        guard=WorkingModel.open(workspace,source,request['context'])
        guard._assert_parent(project_paths(source)['workdir'])
        return _convert_web_json(input_file,workdir,(request_file,request,expected))


def _convert_web_json(input_file,workdir,resolved):
    from nbt_library import canonical_context,coordinates_hash,inherit_edit_constraints,saved_coordinates_hash

    request_file,request,expected=resolved
    source=Path(request['source']).resolve();source_hash=digest(source)
    mask_hash=binary_wall_mask_hash(source)
    source_context_hash=saved_coordinates_hash(source)
    context_hash=coordinates_hash(request['context'])
    camera_hash=digest(request['cameras']) if request.get('cameras') else None
    draft_only=request.get('draft_only',True)
    if type(draft_only) is not bool:raise ValueError('制作版保存选项无效')
    if request.get('source_sha256') and request['source_sha256']!=source_hash:raise ValueError('原建筑已变化，请重新打开原版本并保存设置')
    from nbt_detail_control import authoring_context,load_managed_model
    working=load_managed_model(dict(request,source_sha256=source_hash))
    baseline,base_walls=(working.model,working.walls) if working else read_master(source)
    settings=request['settings'];config=authoring_context(request,baseline,settings,working=working)
    base_walls=resolve_wall_mask(baseline,base_walls,config)
    standalone=validation_mode(config)=='standalone'
    original_config=canonical_context(request['context'])
    if not working:
        original_config=inherit_edit_constraints(original_config,source)
    baseline_checks=working.validate() if working else validate(baseline,config)
    root=Path(workdir).resolve() if workdir else project_paths(source)['workdir']
    skill=Path(__file__).resolve().parents[1]
    if root==skill or skill in root.parents or root==Path(root.anchor):raise ValueError('不能把skill安装目录或磁盘根目录当建筑工作目录')
    if not root.is_dir():raise ValueError('原建筑工作文件夹不存在，请检查源路径')
    with tempfile.TemporaryDirectory(prefix='.web_conversion_',dir=root) as scratch:
        result=preview_effect(dict(request,source_sha256=source_hash),Path(scratch)/'preview')
        after=read_json(result['snapshot'])
        if expected is not None:
            # Match the exact displayed state array as well as source/geometry identity.
            if any(expected.get(key)!=after.get(key) for key in (
                    'source_sha256','binary_wall_mask_sha256','geometry_sha256','size','master_blocks','blocks','wall_positions')):
                raise ValueError('预览JSON与原稿/设置不一致，拒绝导出不同于所看效果的建筑')
        model=Volume(after['size'])
        for p,value in after['master_blocks']:
            p=tuple(p)
            if p in model.blocks:raise ValueError('预览中有重复坐标')
            model.put(p,value)
        if model.fingerprint()!=after['geometry_sha256']:raise ValueError('修改后几何哈希不符')
        walls={tuple(p) for p in after['wall_positions']}
        if working is None:
            cells=layout(model,config)
            if standalone and not walls and config.get('allow_empty_wall_mask') is not True:
                raise ValueError('独立素材的空墙mask须显式设置allow_empty_wall_mask=true')
            if not standalone and any(not any((p[0]//48,p[2]//48)==tuple(cell) for p in walls) for cell in cells):
                raise ValueError('每个有效分片都需要原稿中明确记录的墙体归属，不能按方块材质猜测')
        from nbt_composition.change_policy import enforce_changes,change_sets
        difference=enforce_changes(baseline.blocks,model.blocks,base_walls,walls,
            protected=protections(baseline,config),maximum=config['max_changed_blocks'])
        geometry_changed,layers_changed=change_sets(baseline.blocks,model.blocks,base_walls,walls)
        if working:
            working.patch_candidate(model,walls)
        else:
            checks=validate(model,config)
        if digest(source)!=source_hash or binary_wall_mask_hash(source)!=mask_hash:
            raise ValueError('转换期间原建筑或墙层附属文件变化，请重新预览')
        if coordinates_hash(request['context'])!=context_hash or (camera_hash and digest(request['cameras'])!=camera_hash):raise ValueError('转换期间坐标上下文或机位变化，请重新预览')
        if saved_coordinates_hash(source)!=source_context_hash:
            raise ValueError('转换期间源制作版坐标发生变化，请重新预览')
        if working:
            return save_managed_revision(working,config,request,input_file,draft_only)
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
            authored=master/'model.snbt'
            saved=save_snbt(authored,model,walls,palette=getattr(baseline,'_snbt_palette',None),extras=getattr(baseline,'_snbt_extras',None))
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
            # Published SNBT owns the new mask. Do not carry a legacy mask override into the next version.
            original_config.pop('wall_positions',None)
            if 'floor_context' in original_config:
                original_config['floor_context'].pop('wall_positions',None)
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
                register_building(authored,read_json(description)['name_zh'],cells,mode='standalone' if standalone else None,cell_size=config.get('cell_size',48))
            receipt.update(status='complete',master=str(authored),runtime_parts=0,runtime_files=[],delivery_nbt=0,geometry_sha256=model.fingerprint(),source_unchanged=True,source_format='snbt',draft_only=draft_only)
            write_json(target/'conversion.json',receipt)
        except Exception as error:
            receipt.update(status='failed',error=str(error));write_json(target/'conversion.json',receipt);raise
        from nbt_history import source_workspace,record_produced_version
        workspace=source_workspace(authored)
        try:
            release_converted_version(workspace,receipt,saved['source_sha256'])
        finally:
            message='定稿并导出 NBT' if receipt.get('finalized') else '保存 SNBT 制作版'
            receipt['history']=record_produced_version(workspace,authored,parent=source,message=message,
                                                       actor='human',set_current=True)
            write_json(target/'conversion.json',receipt)
        return receipt


def release_converted_version(workspace, receipt, source_hash):
    if receipt['draft_only']:
        return
    from nbt_finalize import finalize

    try:
        released=finalize(workspace,receipt['master'],register_history=False,expected_source_sha256=source_hash)
    except (ValueError,OSError,KeyError,TypeError,AssertionError) as error:
        receipt.update(release_status='failed',release_error=str(error))
        raise ValueError(f"制作版已保存至 {receipt['master']}，定稿失败：{error}") from error
    receipt.update(runtime_parts=released['runtime_parts'],runtime_files=released['runtime_files'],
        delivery_nbt=released['delivery_nbt'],nbt_master=released['nbt_master'],release_dir=released['output'],
        finalized=True,release_status='complete')


def save_managed_revision(working,config,request,input_file,draft_only):
    """Desktop/manual edits preserve managed baselines and share draft publication."""
    workspace,source,source_hash=working.workspace,working.source,working.source_sha256
    working.context['cameras']=config['cameras']
    saved=working.save_draft(actor='human',attachments={
        'settings.json':portable_request(request,workspace),
        'input.json':read_json(input_file) if Path(input_file).is_file() else portable_request(request,workspace),
    })
    target=Path(saved['output']);authored=Path(saved['source'])
    receipt=dict(schema_version=1,status='complete',source=str(source),source_sha256=source_hash,
        master=str(authored),output=str(target),geometry_sha256=working.model.fingerprint(),draft_only=draft_only,
        source_format='snbt',source_unchanged=True,runtime_parts=0,runtime_files=[],delivery_nbt=0,
        managed_revision=saved['revision'],history=saved.get('history'),history_pending=saved['history_pending'])
    write_json(target/'conversion.json',receipt)
    try:
        release_converted_version(workspace,receipt,working.source_sha256)
    finally:
        write_json(target/'conversion.json',receipt)
        # Refresh derived history without changing the immutable authoring manifest.
        history=working._history_receipt(target,read_json(target/'model-version.json'),working._building)
        receipt['history']=history.get('history');receipt['history_pending']=history['history_pending']
        if history.get('history_error'):receipt['history_error']=history['history_error']
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--workdir',type=Path)
    args=parser.parse_args()
    try:print(json.dumps(dict(ok=True,result=convert_web_json(args.input,args.workdir)),ensure_ascii=False));return 0
    except Exception as error:print(json.dumps(dict(ok=False,error=str(error)),ensure_ascii=False));return 1

if __name__=='__main__':raise SystemExit(main())
