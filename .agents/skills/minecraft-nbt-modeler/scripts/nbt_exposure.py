"""Workspace-local skill facade. Knowledge selection is guidance, not a filesystem ACL."""
import argparse
import json
import os
import hashlib
import shutil
import tomllib
import uuid
import re
from pathlib import Path
from collections import Counter
from functools import wraps
from nbt_capabilities import capabilities
ENGINE=Path(__file__).resolve().parents[1]
MISE_ENTRY='.agents/skills/nbtcreator-workspace/nbt.py'
AGENT_ENTRY='.agents/skills/nbtcreator-agent/SKILL.md'
KNOWLEDGE_BYTES=2*1024*1024
CONFIG_BYTES=256*1024
MISE_TASK='.mise/conf.d/nbtcreator.toml'
MISE_COMMAND='mise run nbt --'
MISE_DIRECT=f'mise run ./{MISE_ENTRY} --'
MISE_CONFIG=f'# NBTCreator generated workspace task\n[tasks.nbt]\ndescription = "Run NBTCreator in this workspace"\nfile = "{MISE_ENTRY}"\n'.encode('utf8')
GROUPS={
 'core':('工作流、验收与协作（按任务读取）',['knowledge-map','simple-building','whole-model-workflow','player-scale','design-principles','spatial-detail-design','validation-workflow','collision-envelopes','refinement','delivery-workflow','output-storage','exposed-tools','agent-feedback','comment-tasks','prompt-archive','batch-workspaces','selection-edit','reference-retrieval','diagnostic-guidance','agent-task-return','agent-protocol','creation-workflows','architect-tools','architecture-workflow','whole-building-planning','ai-creative-preferences','version-history','snbt-authoring']),
 'architecture':('建筑风格、场所与构造',['architecture-knowledge-base','structure-atlas','design-grammar','architectural-bays','classical-columns']),
 'organic':('洞穴与自由形空间',['organic-spaces']),
 'linked':('多空间与跨层联动',['linked-spaces']),
 'props':('细微道具',['micro-props']),
 'materials':('混材、地面与风化',['patterns','floors','weathering']),
 'modelling':('构件、纹样与模型装配',['working-model','large-assembly','orthographic-reference','curved-surface','modelling-tools','toolkit','parametric-components','pattern-authoring','pattern-fitting','surface-mounting','modeling-sessions','object-scenes','compute-transforms','pattern-spectral']),
 'rendering':('纹理预览与图像评审',['rendering']),
 'saodg':('可选：SAODG接入',['saodg-constraints','mod-structures','SAOartguide','room-examples','sealed-examples']),
 'desktop':('桌面、提示词与网页转换',['nbtcreator','detail-control','prompt-console','web-revision']),
 'library':('建筑库与选择器',['library-archive','structure-selector','component-assets','asset-libraries','reusable-recipes','project-batch']),
 'handoff':('委派阅读记录',['delegation-and-review']),
 'maintenance':('可选：软件工具维护与接口扩展',['state-and-maintenance','extensions']),
}

def sync_runtime(workspace):
    """Copy a verified local runtime, preserving any previous or edited snapshot."""
    from nbt_runtime.render import write_render_binding
    write_render_binding(workspace, ENGINE)
    from nbt_project.history import write_git_binding
    write_git_binding(workspace,ENGINE)
    files=[]
    for directory,dirs,names in os.walk(ENGINE):
        dirs[:]=[d for d in dirs if d not in {'node_modules','__pycache__','.git','.vite'}]
        for name in names:
            p=Path(directory)/name
            if p.is_symlink():raise ValueError('Skill来源含不支持的符号链接')
            if name=='runtime-manifest.json' or p.suffix in {'.pyc','.pyo'}:continue
            files.append((p,p.relative_to(ENGINE).as_posix(),hashlib.sha256(p.read_bytes()).hexdigest()))
    files.sort(key=lambda entry:entry[1])
    bundle=hashlib.sha256(json.dumps([(name,digest) for _,name,digest in files],separators=(',',':')).encode()).hexdigest()
    folder=Path(workspace)/'.nbtcreator/runtimes';folder.mkdir(parents=True,exist_ok=True);target=folder/bundle[:16]
    manifest=target/'runtime-manifest.json'
    if target.is_dir() and manifest.is_file():
        try:recorded=json.loads(manifest.read_text(encoding='utf8'))
        except (OSError,ValueError):recorded={}
        if isinstance(recorded,dict) and recorded.get('bundle_sha256')==bundle and all((target/name).is_file() and hashlib.sha256((target/name).read_bytes()).hexdigest()==digest for _,name,digest in files):return target
    if target.exists():target=folder/(bundle[:16]+'_'+uuid.uuid4().hex[:8])
    staging=folder/('.staging_'+uuid.uuid4().hex);staging.mkdir()
    for source,name,digest in files:
        dest=staging/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        if hashlib.sha256(dest.read_bytes()).hexdigest()!=digest:raise ValueError('Skill复制校验失败：'+name)
    (staging/'runtime-manifest.json').write_text(json.dumps(dict(schema_version=1,bundle_sha256=bundle,files=[dict(path=name,sha256=digest) for _,name,digest in files]),ensure_ascii=False,indent=2),encoding='utf8')
    staging.rename(target)
    return target

def config_bytes(workspace):
    file=Path(workspace)/'.nbtcreator/skill-exposure.json'
    try:
        with file.open('rb') as stream:raw=stream.read(CONFIG_BYTES+1)
    except FileNotFoundError:return None
    if len(raw)>CONFIG_BYTES:raise ValueError('skill-exposure.json 超过 256 KiB，请在配置目录备份并检查原文件')
    return raw

def parse_config(raw):
    if raw is None:return dict(schema_version=1,enabled_groups=[group for group in GROUPS if group!='maintenance'],custom_knowledge=[])
    try:config=json.loads(raw.decode('utf-8-sig'))
    except (ValueError,RecursionError):raise ValueError('skill-exposure.json 不是可读的 UTF-8 JSON') from None
    if (not isinstance(config,dict) or type(config.get('schema_version')) is not int or config['schema_version']!=1
            or set(config)-{'schema_version','enabled_groups','custom_knowledge'}
            or not isinstance(config.get('enabled_groups'),list) or any(not isinstance(g,str) or g not in GROUPS for g in config['enabled_groups'])
            or not isinstance(config.get('custom_knowledge',[]),list) or len(config.get('custom_knowledge',[]))>100):
        raise ValueError('skill-exposure.json 的版本、阅读范围或自定义登记列表无效')
    return dict(config,enabled_groups=list(dict.fromkeys(['core',*config['enabled_groups']])),custom_knowledge=config.get('custom_knowledge',[]))

def selected_config(config,issues):
    rows=config['custom_knowledge']
    counts=Counter(item['id'] for item in rows if isinstance(item,dict) and isinstance(item.get('id'),str))
    valid=[]
    for index,item in enumerate(rows):
        try:
            validate_custom([item])
            if counts[item['id']]>1:raise ValueError('资料编号重复，已隔离所有同编号登记')
            valid.append(item)
        except ValueError as failure:
            issues.append(dict(row=index,id='registration:'+str(index),label='自定义登记第 '+str(index+1)+' 项',error=str(failure)))
    return dict(config,custom_knowledge=valid)

def read_config(workspace,issues=None):
    return selected_config(parse_config(config_bytes(workspace)),issues if issues is not None else [])

def config_write(function):
    @wraps(function)
    def write(workspace,*args,**kwargs):
        from nbt_knowledge.libraries import inside,write_lock
        workspace=Path(workspace).resolve()
        if workspace==ENGINE.parents[2] and (workspace/'desktop/main.cjs').is_file():raise ValueError('软件源码或安装目录不生成创作Skill；请选择实际创作项目根目录')
        with write_lock(inside(workspace,workspace/'.nbtcreator/exposure-lock')):
            return function(workspace,*args,**kwargs)
    return write

def validate_custom(items):
    if not isinstance(items,list) or len(items)>100:raise ValueError('自定义知识库最多100项')
    ids=set()
    for item in items:
        if not isinstance(item,dict) or set(item)!={'id','label','path','enabled'} or not isinstance(item['id'],str) or not re.fullmatch(r'custom_[a-f0-9]{16}',item['id']) or item['id'] in ids:raise ValueError('自定义知识条目无效')
        ids.add(item['id'])
        if not isinstance(item['label'],str) or len(item['label'])>150 or re.search(r'[\r\n\[\]]',item['label']) or type(item['enabled']) is not bool or not isinstance(item['path'],str) or len(item['path'])>512:raise ValueError('知识名称、相对路径或开关无效')
    return items

def knowledge_path(workspace,item):
    workspace=Path(workspace).resolve()
    root=workspace/'.nbtcreator/knowledge'
    relative=Path(item['path'])
    if relative.anchor or '..' in relative.parts or not relative.parts or relative.parts[0]!='knowledge' or relative.suffix.lower() not in {'.md','.txt'}:
        raise ValueError('资料须位于 .nbtcreator/knowledge 并使用 .md 或 .txt')
    path=(workspace/'.nbtcreator'/relative).resolve()
    if root.resolve()!=root or not path.is_relative_to(root):
        raise ValueError('资料路径越出工作区知识目录')
    return path

def read_custom(workspace,item):
    try:
        with knowledge_path(workspace,item).open('rb') as stream:
            raw=stream.read(KNOWLEDGE_BYTES+1)
    except FileNotFoundError:
        raise ValueError('资料文件缺失，请恢复原路径或重新导入') from None
    except (OSError,RuntimeError):
        raise ValueError('资料文件无法读取，请检查路径与权限') from None
    if len(raw)>KNOWLEDGE_BYTES or b'\x00' in raw:
        raise ValueError('资料须为不超过 2 MiB 的文本')
    try:
        return raw,raw.decode('utf-8-sig')
    except UnicodeError:
        raise ValueError('资料须使用 UTF-8 编码') from None

def custom_issues(workspace,items):
    issues=[]
    for item in items:
        try:read_custom(workspace,item)
        except ValueError as failure:issues.append(dict(**item,error=str(failure)))
    return issues

@config_write
def edit_knowledge(workspace,identifier,setting):
    config=parse_config(config_bytes(workspace))
    item=next((item for item in selected_config(config,[])['custom_knowledge'] if item['id']==identifier),None)
    if item is None:raise ValueError('找不到自定义资料，请刷新列表')
    if setting=='enable':
        read_custom(workspace,item)
        item['enabled']=True
    elif setting=='disable':item['enabled']=False
    elif setting=='remove':config['custom_knowledge'].remove(item)
    else:raise ValueError('请选择 enable、disable 或 remove')
    return sync_config(workspace,config)

@config_write
def recover(workspace,expected,setting,row=None):
    raw=config_bytes(workspace)
    if raw is None or hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('登记已变化，请重新查看 exposure show')
    try:config=parse_config(raw)
    except ValueError:
        if setting!='reset-core' or row is not None:raise ValueError('请使用 reset-core 备份损坏配置并仅启用核心资料')
        config=dict(schema_version=1,enabled_groups=['core'],custom_knowledge=[])
    else:
        issues=[];selected_config(config,issues)
        if type(row) is not int or not any(issue['row']==row for issue in issues):raise ValueError('请选择本次诊断中的坏登记行')
        rows=config['custom_knowledge'];item=rows[row]
        if setting=='restore':
            if not isinstance(item,dict) or not isinstance(item.get('path'),str) or len(item['path'])>512:raise ValueError('缺少有效的原文件路径，请移除登记后重新导入')
            data,_=read_custom(workspace,item);identifier='custom_'+hashlib.sha256(data).hexdigest()[:16]
            if any(i!=row and isinstance(other,dict) and other.get('id')==identifier for i,other in enumerate(rows)):raise ValueError('正文已登记，请核对并移除重复项')
            label=re.sub(r'[\r\n\[\]()]','',Path(item['path']).stem)[:150]
            rows[row]=dict(id=identifier,label=label,path=item['path'],enabled=False)
        elif setting=='remove':rows.pop(row)
        else:raise ValueError('请选择 restore 或 remove')
        # Resolving a duplicate must never silently grant the surviving row access.
        if isinstance(item,dict) and isinstance(item.get('id'),str):
            for other in rows:
                if isinstance(other,dict) and other.get('id')==item['id']:other['enabled']=False
    from nbt_knowledge.libraries import inside
    folder=inside(workspace,workspace/'.nbtcreator/skill-backups');folder.mkdir(parents=True,exist_ok=True)
    backup=inside(folder,folder/(expected+'.json.bak'))
    try:
        with backup.open('xb') as stream:stream.write(raw)
    except FileExistsError:
        if backup.read_bytes()!=raw:raise ValueError('配置备份哈希不匹配')
    return dict(sync_config(workspace,config),backup=backup.relative_to(workspace).as_posix())

def preview_knowledge(workspace,identifier):
    item=next((item for item in read_config(workspace)['custom_knowledge'] if item['id']==identifier),None)
    if item is None:raise ValueError('找不到自定义资料，请刷新列表')
    return dict(title=item['label'],text=read_custom(workspace,item)[1])

@config_write
def inherit(workspace,previous):
    workspace=Path(workspace).resolve()
    if (workspace/'.nbtcreator/skill-exposure.json').exists():
        return sync_config(workspace,parse_config(config_bytes(workspace)))
    issues=[]
    try:config=read_config(previous,issues)
    except (ValueError,OSError):
        return dict(sync_config(workspace,dict(schema_version=1,enabled_groups=['core'],custom_knowledge=[])),inherit_notice='原工作区资料配置无法读取，新入口仅启用核心资料。')
    for item in config['custom_knowledge'][:]:
        try:
            raw,_=read_custom(previous,item)
            target=knowledge_path(workspace,item)
            target.parent.mkdir(parents=True,exist_ok=True)
            try:
                with target.open('xb') as stream:stream.write(raw)
            except FileExistsError:
                if read_custom(workspace,item)[0]!=raw:raise ValueError('目标已有不同资料，已保留该文件')
        except (ValueError,OSError):
            # A missing or conflicting source cannot grant exposure in the new workspace.
            config['custom_knowledge'].remove(item)
            issues.append(dict(id=item['id'],label=item['label']))
    return dict(sync_config(workspace,config),inherit_skipped=issues)

@config_write
def import_knowledge(workspace,documents):
    config=parse_config(config_bytes(workspace))
    selected=selected_config(config,[])['custom_knowledge']
    planned=[]
    if not documents or len(documents)>32:raise ValueError('每次选择1至32份Markdown或TXT知识文件')
    for source in documents:
        source=Path(source)
        if source.suffix.lower() not in {'.md','.txt'} or source.stat().st_size>KNOWLEDGE_BYTES:raise ValueError('仅支持不超过2MiB的Markdown/TXT文件')
        with source.open('rb') as stream:data=stream.read(KNOWLEDGE_BYTES+1)
        if len(data)>KNOWLEDGE_BYTES or b'\x00' in data:raise ValueError('仅支持不超过2MiB的Markdown/TXT文件')
        data.decode('utf-8-sig');digest=hashlib.sha256(data).hexdigest()[:16]
        item=dict(id='custom_'+digest,label=re.sub(r'[\[\]()\r\n]','',source.stem)[:150],path='knowledge/'+digest+source.suffix.lower(),enabled=True)
        existing=next((entry for entry in selected if entry['id']==item['id']),None)
        if not existing and any(isinstance(entry,dict) and entry.get('id')==item['id'] for entry in config['custom_knowledge']):
            raise ValueError('资料编号与隔离登记冲突，请先处理坏登记')
        item=existing or item
        planned.append((knowledge_path(workspace,item),data,item))
    existing_ids={entry['id'] for entry in selected}
    if len(config['custom_knowledge'])+len({item['id'] for _,_,item in planned}-existing_ids)>100:raise ValueError('自定义知识库最多100项')
    for target,data,item in planned:
        target.parent.mkdir(parents=True,exist_ok=True)
        try:
            with target.open('xb') as stream:stream.write(data)
        except FileExistsError:
            if read_custom(workspace,item)[0]!=data:raise ValueError('同名知识文件有本地修改，未覆盖')
        if item['id'] not in existing_ids:
            config['custom_knowledge'].append(item);existing_ids.add(item['id'])
    return sync_config(workspace,config)

def local_mise_task(workspace, managed):
    roots=[workspace/name for name in ('mise','.mise','.config/mise')]
    task_dirs=[workspace/'mise-tasks',*(root/'tasks' for root in roots)]
    if any(file.is_file() and file.stem.casefold()=='nbt' for folder in task_dirs for file in folder.glob('nbt*')):
        return True
    configs=[*workspace.glob('mise*.toml'),*workspace.glob('.mise*.toml'),*(workspace/'.config').glob('mise*.toml')]
    for root in roots:
        configs.extend(root.glob('config*.toml'));configs.extend(root.glob('mise*.toml'))
        configs.extend((root/'conf.d').glob('*.toml'));configs.extend((root/'conf.d').glob('*/mise.toml'))
    configs.extend(file for folder in task_dirs for file in folder.glob('*.toml'))
    for file in configs:
        if file==managed:
            continue
        with file.open('rb') as stream:
            data=tomllib.load(stream)
        tasks=data if file.parent in task_dirs else data.get('tasks',{})
        if 'nbt' in tasks or data.get('task_config',{}).get('includes'):
            return True
        for task in tasks.values():
            aliases=task.get('alias',[]) if isinstance(task,dict) else []
            if aliases=='nbt' or isinstance(aliases,list) and 'nbt' in aliases:
                return True
    return False


def mise_launcher(workspace, install=False):
    workspace=Path(workspace).resolve();file=workspace/MISE_TASK
    try:
        if not file.resolve().is_relative_to(workspace) or file.is_symlink():
            return MISE_DIRECT
        current=file.read_bytes() if file.is_file() else None
        if current is not None and current!=MISE_CONFIG:
            return MISE_DIRECT
        if local_mise_task(workspace,file):
            if install and current==MISE_CONFIG:
                file.unlink()
            return MISE_DIRECT
        if current is None and install:
            file.parent.mkdir(parents=True,exist_ok=True)
            with file.open('xb') as stream:
                stream.write(MISE_CONFIG)
            return MISE_COMMAND
        return MISE_COMMAND if current==MISE_CONFIG else MISE_DIRECT
    except (OSError,ValueError,TypeError,AttributeError):
        return MISE_DIRECT


def show(workspace):
    raw=config_bytes(workspace)
    sha=hashlib.sha256(raw).hexdigest() if raw is not None else None
    issues=[]
    try:config=selected_config(parse_config(raw),issues)
    except ValueError as failure:
        return dict(config_error=str(failure),config_sha256=sha,enabled_groups=[],custom_knowledge=[],groups=[],registration_issues=[])
    caps=capabilities()
    return dict(config,config_sha256=sha,registration_issues=issues,custom_issues=custom_issues(workspace,config['custom_knowledge']),groups=[dict(id=key,label=label,required=key=='core',files=[p+'.md' for p in files]) for key,(label,files) in GROUPS.items()],
                facade='.agents/skills/nbtcreator-workspace/SKILL.md',agent_facade=AGENT_ENTRY,launcher=mise_launcher(workspace),
                tool_count=len(caps['tools']),capabilities_sha256=caps['capabilities_sha256'])


def facade_knowledge(runtime, facade, workspace, relative, config, launcher):
    """Keep task selection in the entrypoint and the selected inventory separate."""
    enabled={name for group in config['enabled_groups'] for name in GROUPS[group][1]}
    def link(name):
        file=runtime/'references'/(name+'.md')
        if not file.is_file():raise ValueError('缺少知识文件：'+name)
        title=next((line.lstrip('# ').strip() for line in file.read_text(encoding='utf8').splitlines() if line.startswith('# ')),name)
        return f'[{title}]({relative}/references/{name}.md)'
    routes=[
        ('整栋初稿：纯文字',['simple-building','spatial-detail-design'],'先按代表活动布置主件、配套、操作侧和下一站。在主模型上从玩家来路看清这组关系；细节参考读沿实际使用路线审细部。'),
        ('整栋初稿：有参考图',['simple-building','spatial-detail-design'],'从轮廓和开间选一处能辨认的交接，先做进深、材料与支承，再按实际构造重复；背面与室内的补全单记理由。'),
        ('复杂整栋的面积与多层布局',['whole-building-planning'],'检查分层、面积和连接，比较候选后再绑定制作源复验。'),
        ('简单独立整栋初稿',['simple-building'],'已有几何用 model；需要记录空间、构件和审阅绑定时用 architect plan-build。'),
        ('室内用途与建筑群验收',['architecture-workflow'],'室内用 use_face 查操作侧、工作高度与净距；街区沿主街、支路、门槛走到室内，按用途查公共与服务路线。多层布局可另出逐层平面与纵剖。'),
        ('建筑方案、构造与审阅闭环',['architecture-workflow'],'设计参数驱动真实构件；三层出图、问题定位、源绑定回查和游戏验收分别执行。'),
        ('完整主模型与独立构件',['working-model','parametric-components'],'工作模型管理安装、归属、修改和制作版；构件只做适用检查。'),
        ('大型组装与协作切片',['large-assembly'],'校验每个分区、全局保护与路线，切片回装保持来源绑定和失败可重试。'),
        ('三视参考与正交审阅',['orthographic-reference'],'登记来源、坐标和不确定性，比较真实轮廓与绑定机位；审阅不等于批准。'),
        ('曲面纹样与构件复用',['curved-surface'],'按真实宿主规划分层、背衬及连接；素材切片与候选须分别核对来源和看图。'),
        ('整栋初稿的地面嵌纹、屏风边饰与墙面徽记',['pattern-authoring','pattern-fitting'],'从主模型路线转入纹样专题；已有图源可直接拟合。预览代表单元，再用实际承载面和观察位置回查。'),
        ('准备或制作纹样图源',['pattern-authoring'],'已有合适图源可直接进入拟合。'),
        ('拟合纹样与检查质量',['pattern-fitting'],'按微型、普通面板或圆柱模式读对应完整章节，实际看图。'),
        ('安装到已有建筑',['surface-mounting'],'先绑定真实源、上下文和安装面，再生成候选。'),
        ('参数引用和对象联动',['object-scenes'],'使用稳定ID和关系，不靠手工猜测多个构件如何拼合。'),
        ('空间和风格推演',['design-grammar','architecture-knowledge-base'],'按用途选适用完整章节，例子不是建筑模板。'),
        ('近观道具与薄构件',['micro-props'],'检查支承、使用侧和实际预览。'),
        ('批注与已有模型修改',['agent-feedback'],'先读取源、坐标和图像证据，核对保护与当前阶段。'),
        ('给已有模型局部换材',['selection-edit'],'从真实源或候选读取选区；局部步骤编译成带写入边界的全局操作后接回原计划。'),
        ('用户看图后批准精修',['refinement'],'确认仍绑定相同源与图像后再执行。'),
        ('验证、看图与失败定位',['validation-workflow','diagnostic-guidance']+(['rendering'] if 'rendering' in enabled else []),'用 `render --help` 查询出图参数，查看实际图片后记录观察，分别报告技术、空间、构造与主题结论。'),
        ('已有资产保存与放置',['component-assets','reusable-recipes'],'先查询与预览，放置只生成受保护的候选。'),
        ('保存、续版与交付',['snbt-authoring','version-history','output-storage'],'默认保存SNBT；定稿NBT必须明确要求。'),
        ('任务领取与结果回传',['agent-protocol','agent-task-return'],'用 task-client 查看、领取及回传指定任务，自动管理租约和幂等重放。'),
        ('单工具检查与维护',['state-and-maintenance'],'只读当前实现及所改专题，不默认生成建筑。'),
        ('注册器与接口扩展',['extensions'],'新增公共能力时再读注册与目录同步要求。')]
    lines=['---','name: nbtcreator-workspace','description: 当前创作项目的 Minecraft NBT 建模、任务交接与验证入口。','---','',
        '# 当前工作区建模接口','',
        f'在创作项目根目录运行 `{launcher} <命令>`。下文省略该前缀。无需启动 Electron；资产在 `nbt_models/`。','',
        '## 先处理交接任务','',
        '读紧凑视图：提示词用 `task-client inspect prompts <id>`，修改用 `task-client inspect tasks <id>`。核对 `source_matches`，按 `next` 与 `expand` 继续。选定任务后再领取。',
        '只知道编号时用 `task --id <id> --view compact`。待办用 `task-client list --pending`。旧候选用 `--view candidates`，以 `check-candidate` 核对后用 `reuse-candidate` 登记。','',
        '- 整栋初稿的触发入口是 [nbtcreator-agent](../nbtcreator-agent/SKILL.md)。',
        '## 没有交接任务时','',
        f'- 整栋初稿用 `architect plan-build --request <JSON文件>`，查 `capabilities --architect-action plan-build`。填 `save_draft` 后返回制作版与 `next.request`。见{link("simple-building")}与{link("architecture-workflow")}。[归卷阁样例]({relative}/assets/examples/reading-loft/README.md)。',
        '- 复杂整栋先用 `architect layout-check`，见知识索引。',
        '- 装配或续版用 `model --request <JSON文件>`，查 `capabilities --model`。指定 `save_draft` 另存制作版。',
        f'- 给旧建筑局部换材：`selection-edit context --request <JSON文件>` 读取实际选区，取得局部方块和几何哈希。按{link("selection-edit")}编译局部步骤，再在同一上下文中预览和验证。',
        '- 查已有尖拱等资产：`asset-libraries browse --request <JSON文件>`，文件写 `{"query":"尖拱","limit":4}`。查 `asset-libraries --help`。得到带来源及版本绑定的命中，保留整组绑定用于预览。',
        '- 其他任务先查 `capabilities --routes`，再按[任务路线和已启用资料](knowledge.md)选读。已知命令用 `<命令> --help`；单个 JSON 工具查 `capabilities --agent-tool <名称>`。',
        '- 读取回执时同时看退出码、业务状态和源绑定。候选 `validate` 用 `result.passed`；建筑简报失败后把 `report.path` 指向的完整报告交给 `diagnostics`。',
        f'- 按{link("spatial-detail-design")}的「方块配色复核」选主材与收边，用实纹理小样核对后将方块状态写回方案。',
        '- `paths` 返回冻结引擎位置，`paths --runtime` 核对解释器和出图依赖。移动项目后的恢复参数查 `paths --help`；用 `exposure show` 查看资料缺项。',
        f'- 查参考读{link("reference-retrieval")}：`retrieve search --request <JSON文件>` 后凭 `receipt` 和 `R1` 取证。查历史原文加 `source_kind: library`，不必先查库编号。只在用户要求时联网。',
        '- 创作偏好按 `ai-style prompt --workflow <区域>` 读取。用户本次要求优先，不更改保护或批准。','',
        '## 不可跳过的检查','',
        '核对源、坐标和已选项目约束，保留显式墙层、实例归属、保护、留白和修改预算。按声明检查开洞、通路与必要净空，实际查看审阅图。SAODG 专用端口仅在显式选用时使用。',
        '初稿审阅图交给用户，核对同一源和图像绑定，明确批准后才精修。候选、保存制作版、采用和定稿是不同动作；默认另存并回读 SNBT，明确要求定稿才写交付 NBT。']
    index=['# 任务路线与已启用资料','',
        '按当前任务选择一条路线；引用中的其他专题仅在启用或用户明确指定时读取。知识不授予批准或执行权限。','',
        '| 当前任务 | 先读 | 下一步与范围 |','| --- | --- | --- |']
    for label,names,action in routes:
        if all(name in enabled for name in names):index.append('| '+label+' | '+'、'.join(link(name) for name in names)+' | '+action+' |')
    index+=['', '已知工具查 `capabilities --agent-tool <名称>`；主模型查 `--model`，建筑方案查 `--architecture`，纹样样件查 `capabilities --agent-tool pattern_microfit`。一次性书库可用 `retrieve architecture --library <目录> search <关键词>`。','']
    for group in config['enabled_groups']:
        label,names=GROUPS[group];index+=['## '+label,'']
        index.extend('- '+link(name) for name in names)
        index.append('')
    issues=custom_issues(workspace,config['custom_knowledge'])
    unavailable={item['id'] for item in issues}
    custom=[item for item in config['custom_knowledge'] if item['enabled'] and item['id'] not in unavailable]
    if custom:
        heading=['','## 用户补充知识','这些资料用于当前任务，不改变核心边界，也不授予批准。']
        index+=heading
        for item in custom:
            target=os.path.relpath(workspace/'.nbtcreator'/item['path'],facade).replace('\\','/')
            index.append(f"- [{item['label']}]({target})")
    if issues:
        index+=['','## 暂不可读的自定义资料','从外部建造助手设置恢复文件、重新导入或移除登记。','']
        index.extend(f"- {item['label']}（{item['id']}）：{item['error']}" for item in issues)
    return '\n'.join(lines)+'\n','\n'.join(index)+'\n'

def agent_entry(launcher, relative):
    return f"""---
name: nbtcreator-agent
description: 触发 NBTCreator 本地整栋建筑初稿流程。用任务编号接续工作台交接，或从明确的建筑要求新建任务，运行性价比或极限效果模式并交付实图审阅。
---

# 运行 NBTCreator 建造 Agent

从当前创作项目根目录运行 `{launcher} <命令>`。下文省略命令前缀。用 `paths` 核对当前工作区和冻结引擎。读取 [完整创作流程]({relative}/references/creation-workflows.md) 中适用的阶段。需要建模与资料接口时读 [当前工作区建模入口](../nbtcreator-workspace/SKILL.md)。

## 确定要运行的任务

- 有任务编号时用 `task --id <编号> --view compact` 核对阶段、来源和交接模式。只读规划、已有建筑的修改或精修按该任务返回的入口处理。
- 用户要接手待办时，用 `task-client list --kind prompts --pending` 发现任务。按用户已经给出的编号、建筑名或选择定位；有多个合理匹配时先核对任务。
- 用户直接要求制作新的整栋建筑时，按 [直接建立任务]({relative}/references/creation-workflows.md#从外部对话直接建立初稿任务) 将其原文与硬条件登记为提示词并交接。只编写要求时交付稿件供审阅。

## 运行与回传

1. 用 `task-client --session <会话> start prompts <编号> --owner <执行者>` 领取已选任务。已有本会话时先查状态并沿用，以 `keepalive` 保持长任务租约。
2. 用 `creation --session <会话> start` 读冻结简报。极限效果附带设计轴 JSON；用 `brief --expand` 核对完整需求和约束。按该任务的模型档位和批次继续。
3. 按简报提交建筑方案或 WorkingModel，查看失败定位与下一步。本地故障用原请求 `retry`；来源或租约变化时重核任务。按要求查看真实候选图，解决影响用途的缺口后再选用。
4. 用 `select`、`publish`、`observe` 和 `finish` 交付入选制作版；极限效果先完成匿名比选。向用户展示制作版实图和检查结论。精修须经用户对这份实图明确同意，定稿 NBT 由用户明确要求后独立导出。
"""


def write_facade(facade, generated, marker, backup_subdir=None):
    from nbt_knowledge.libraries import atomic
    facade.mkdir(parents=True,exist_ok=True)
    try:previous=json.loads(marker.read_text(encoding='utf8'))
    except (FileNotFoundError,ValueError):previous={}
    if not isinstance(previous,dict):previous={}
    backup=None
    for name,text in generated.items():
        target=facade/name
        payload=text.encode('utf8')
        if target.is_file():
            current=target.read_bytes()
            # Older Windows writes used CRLF with a manifest of the LF bytes.
            normalized=current.replace(b'\r\n',b'\n')
            if current!=payload and normalized!=payload and previous.get(name) not in {
                    hashlib.sha256(current).hexdigest(),hashlib.sha256(normalized).hexdigest()}:
                if backup is None:
                    backup=marker.parent/'skill-backups'/uuid.uuid4().hex
                    if backup_subdir:
                        backup=backup/backup_subdir
                    backup.mkdir(parents=True)
                shutil.copy2(target,backup/name)
        temp=target.with_name(target.name+'.tmp');temp.write_bytes(payload);temp.replace(target)
        if name=='nbt.py' and os.name!='nt':target.chmod(target.stat().st_mode|0o111)
    atomic(marker,json.dumps({name:hashlib.sha256(text.encode('utf8')).hexdigest() for name,text in generated.items()},indent=2).encode('utf8'))


@config_write
def apply(workspace,config=None):
    current=parse_config(config_bytes(workspace))
    if config is not None:
        if 'custom_knowledge' in config:validate_custom(config['custom_knowledge'])
        current=parse_config(json.dumps(dict(config,custom_knowledge=config.get('custom_knowledge',current['custom_knowledge']))).encode())
    return sync_config(workspace,current)

def sync_config(workspace,raw_config):
    workspace=Path(workspace).resolve()
    if workspace==ENGINE.parents[2] and (workspace/'desktop/main.cjs').is_file():raise ValueError('软件源码或安装目录不生成创作Skill；请选择实际创作项目根目录')
    folder=workspace/'.nbtcreator';folder.mkdir(parents=True,exist_ok=True)
    from nbt_ai_style import load as load_style
    load_style(workspace,create=True)
    file=folder/'skill-exposure.json'
    config=selected_config(raw_config,[])
    runtime=sync_runtime(workspace)
    facade=workspace/'.agents/skills/nbtcreator-workspace'
    relative=os.path.relpath(runtime,facade).replace('\\','/')
    launcher=mise_launcher(workspace,install=True)
    entry_text,index_text=facade_knowledge(runtime,facade,workspace,relative,config,launcher)
    wrapper='''#!/usr/bin/env python
"""Generated workspace entry; implementation remains in the shared application engine."""
from pathlib import Path
import os,sys,subprocess,json
entry=Path(__file__).resolve()
engine=(entry.parent/ENGINE_RELATIVE).resolve()
if not engine.is_dir():raise SystemExit('引擎路径变化，请在应用AI设置重新同步Skill暴露配置')
catalog=json.loads((engine/'tool-catalog.json').read_text(encoding='utf8'))
aliases=catalog['command_aliases']
if len(sys.argv)==1 or sys.argv[1] in ('-h','--help'):
 print('Usage: '+ENTRY_COMMAND+' <command> [options]')
 print('Commands: '+' | '.join([*catalog['commands'],*aliases]))
 print('用 capabilities --routes 速查入口，用 <命令> --help 查看参数。')
 raise SystemExit(0)
command,*args=sys.argv[1:]
if command in aliases:
 command,*prefix=aliases[command]
 args=[*prefix,*args]
script=catalog['commands'].get(command)
if script is None:raise SystemExit(f'未知命令 {command}。用 --help 查看命令，或用 capabilities --routes 速查入口。')
args=[*catalog['command_prefixes'].get(command,[]),*args]
task_file=os.environ.get('MISE_TASK_FILE')
workspace=entry.parents[3] if task_file and Path(task_file).resolve()==entry else Path.cwd()
raise SystemExit(subprocess.call([sys.executable,'-B',str(engine/'scripts'/script),*args],cwd=workspace))
'''.replace('ENGINE_RELATIVE',repr(relative)).replace('ENTRY_COMMAND',repr(launcher))
    write_facade(facade,{'SKILL.md':entry_text,'knowledge.md':index_text,'nbt.py':wrapper},folder/'facade-manifest.json')
    agent=workspace/AGENT_ENTRY
    agent_relative=os.path.relpath(runtime,agent.parent).replace('\\','/')
    write_facade(agent.parent,{'SKILL.md':agent_entry(launcher,agent_relative)},folder/'agent-facade-manifest.json',agent.parent.name)
    from nbt_knowledge.libraries import atomic
    from nbt_paths import python_versions
    metadata=json.loads((runtime/'runtime-manifest.json').read_text(encoding='utf8'))
    from nbt_runtime.render import synced_browser_version
    binding=dict(python=python_versions(),bundle_sha256=metadata['bundle_sha256'],electron=os.environ.get('NBTCREATOR_ELECTRON_VERSION'),
                 chromium=synced_browser_version(ENGINE))
    atomic(folder/'engine-runtime.json',(json.dumps(binding,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    try:existing=json.loads(config_bytes(workspace) or b'null')
    except (ValueError,RecursionError):existing=None
    if existing!=raw_config:atomic(file,(json.dumps(raw_config,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    return show(workspace)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['show','apply','import','edit','preview','inherit','recover']);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('--config',type=Path);parser.add_argument('--document',type=Path,action='append');parser.add_argument('--id');parser.add_argument('--setting',choices=['enable','disable','remove','restore','reset-core']);parser.add_argument('--previous',type=Path)
    parser.add_argument('--sha256',help='exposure show 返回的 config_sha256');parser.add_argument('--row',type=int,help='registration_issues 中的 row')
    args=parser.parse_args()
    try:
        if args.command=='recover':result=recover(args.workspace,args.sha256,args.setting,args.row)
        elif args.command=='import':result=import_knowledge(args.workspace,args.document)
        elif args.command=='edit':result=edit_knowledge(args.workspace,args.id,args.setting)
        elif args.command=='preview':result=preview_knowledge(args.workspace,args.id)
        elif args.command=='inherit':result=inherit(args.workspace,args.previous)
        elif args.command=='show':result=show(args.workspace)
        else:result=apply(args.workspace,json.loads(args.config.read_text(encoding='utf8')) if args.config else None)
        print(json.dumps(result,ensure_ascii=False))
    except (ValueError,OSError) as failure:
        print(json.dumps(dict(error=str(failure)),ensure_ascii=False))
        raise SystemExit(1)
