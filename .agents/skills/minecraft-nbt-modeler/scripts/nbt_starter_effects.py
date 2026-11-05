"""Install versioned, data-only starter effects without replacing workspace assets."""
import hashlib,json,shutil,uuid
from pathlib import Path
from nbt_project_batch import write

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'assets/starter-tool-effects'
FILES={'effect.json','preview/before.json','preview/after.json','preview/thumbnail.jpg','preview/report.json'}


def sha(file):return hashlib.sha256(file.read_bytes()).hexdigest()


def engine_sha():
    names=['nbt_effect_assets.py','nbt_detail_control.py','nbt_tools.py','nbt_floors.py','nbt_weathering.py','nbt_patterns.py','nbt_operation_parameters.py','nbt_change_policy.py','nbt_operation_scope.py','nbt_collision.py','nbt_model.py','nbt_assembly.py']
    files=[ROOT/'tool-catalog.json',*(ROOT/'scripts'/name for name in names)]
    return hashlib.sha256(''.join(sha(file) for file in files).encode()).hexdigest()


def catalog():
    file=BUNDLE/'manifest.json'
    if not file.is_file():return None
    data=json.loads(file.read_text(encoding='utf8'))
    if data.get('schema_version')!=1 or data.get('asset_type')!='tool_effect_starter_pack' or not isinstance(data.get('items'),list) or not 1<=len(data['items'])<=100:raise ValueError('初始效果资料清单无效')
    import re
    ids=set()
    for item in data['items']:
        if not re.fullmatch('[a-f0-9]{32}',item.get('id','')) or item['id'] in ids or set(item.get('files',{}))!=FILES:raise ValueError('初始效果资料文件无效')
        if any(not re.fullmatch('[a-f0-9]{64}',value) for value in item['files'].values()):raise ValueError('初始效果资料哈希无效')
        ids.add(item['id'])
    return data


def checked_files(item):
    files={name:BUNDLE/item['id']/name for name in FILES}
    if any(not file.resolve().is_relative_to(BUNDLE.resolve()) or not file.is_file() or sha(file)!=item['files'][name] for name,file in files.items()):raise ValueError('初始效果资料缺失或内容变化：'+item['id'])
    return files


def install(workspace):
    from nbt_effect_assets import root,validate
    bundle=catalog()
    if bundle is None:return dict(installed=0)
    workspace=Path(workspace).resolve();base=root(workspace);ledger=base/'.starter-effects.json'
    if not ledger.resolve().is_relative_to(workspace):raise ValueError('初始效果登记路径越界')
    state=json.loads(ledger.read_text(encoding='utf8')) if ledger.is_file() else dict(schema_version=1,installed=[])
    if state.get('schema_version')!=1 or not isinstance(state.get('installed'),list):raise ValueError('初始效果入库记录无效')
    known=set(state['installed']);pending=[item for item in bundle['items'] if item['id'] not in known]
    # Verify the entire pending pack before changing any workspace files.
    planned=[]
    for item in pending:
        files=checked_files(item);value=validate(json.loads(files['effect.json'].read_text(encoding='utf8')))
        if value['content_sha256']!=item['content_sha256']:raise ValueError('初始效果内容绑定无效')
        planned.append((item,files))
    installed=0
    for item,files in planned:
        target=base/item['id']
        if not target.resolve().is_relative_to(workspace):raise ValueError('初始效果目录越界')
        if not target.exists():
            staging=base/('.install-'+uuid.uuid4().hex);staging.mkdir(parents=True)
            try:
                for name,file in files.items():
                    dest=staging/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,dest)
                try:staging.rename(target);installed+=1
                except FileExistsError:pass # Another process installed the same stable ID.
            finally:
                for file in sorted(staging.rglob('*'),reverse=True) if staging.exists() else []:
                    file.rmdir() if file.is_dir() else file.unlink()
                if staging.exists():staging.rmdir()
        known.add(item['id'])
    if pending:write(ledger,dict(schema_version=1,bundle_version=bundle['version'],installed=sorted(known)))
    return dict(installed=installed)


def cached_preview(workspace,data):
    from nbt_effect_assets import file_for
    folder=file_for(workspace,data['id']).parent/'preview';report=folder/'report.json'
    if not report.resolve().is_relative_to(Path(workspace).resolve()) or not report.is_file():return None
    try:
        value=json.loads(report.read_text(encoding='utf8'))
        if value.get('content_sha256')!=data['content_sha256'] or value.get('engine_sha256')!=engine_sha():return None
        paths={name:folder/name for name in ['before.json','after.json','thumbnail.jpg']}
        if any(not file.resolve().is_relative_to(Path(workspace).resolve()) or sha(file)!=value['files'][name] for name,file in paths.items()):return None
        return dict(before_snapshot=str(paths['before.json']),after_snapshot=str(paths['after.json']),thumbnail=str(paths['thumbnail.jpg']),cameras=value['cameras'],changed_blocks=value['changed_blocks'],sample_only=True,asset_written=False,nbt_exported=False,precomputed=True,warning='预生成的工具样例；应用到当前建筑仍需实际候选预览')
    except (OSError,ValueError,KeyError,TypeError):return None
