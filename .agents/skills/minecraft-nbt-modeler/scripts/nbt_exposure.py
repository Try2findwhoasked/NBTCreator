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
from nbt_capabilities import capabilities
ENGINE=Path(__file__).resolve().parents[1]
MISE_ENTRY='.agents/skills/nbtcreator-workspace/nbt.py'
MISE_TASK='.mise/conf.d/nbtcreator.toml'
MISE_COMMAND='mise run nbt --'
MISE_DIRECT=f'mise run ./{MISE_ENTRY} --'
MISE_CONFIG=f'# NBTCreator generated workspace task\n[tasks.nbt]\ndescription = "Run NBTCreator in this workspace"\nfile = "{MISE_ENTRY}"\n'.encode('utf8')
GROUPS={
 'core':('工作流、验收与协作（按任务读取）',['knowledge-map','simple-building','whole-model-workflow','player-scale','design-principles','spatial-detail-design','validation-workflow','collision-envelopes','refinement','delivery-workflow','output-storage','exposed-tools','agent-feedback','comment-tasks','prompt-archive','batch-workspaces','selection-edit','reference-retrieval','diagnostic-guidance','agent-task-return','agent-protocol','architect-tools','architecture-workflow','ai-creative-preferences','version-history','snbt-authoring']),
 'architecture':('建筑风格、场所与构造',['architecture-knowledge-base','structure-atlas','design-grammar','architectural-bays','classical-columns']),
 'organic':('洞穴与自由形空间',['organic-spaces']),
 'linked':('多空间与跨层联动',['linked-spaces']),
 'props':('细微道具',['micro-props']),
 'materials':('混材、地面与风化',['patterns','floors','weathering']),
 'modelling':('构件、纹样与模型装配',['working-model','modelling-tools','toolkit','parametric-components','pattern-authoring','pattern-fitting','surface-mounting','modeling-sessions','object-scenes','compute-transforms','pattern-spectral']),
 'rendering':('纹理预览与图像评审',['rendering']),
 'saodg':('可选：SAODG接入',['saodg-constraints','mod-structures','SAOartguide','room-examples','sealed-examples']),
 'desktop':('桌面、提示词与网页转换',['nbtcreator','detail-control','prompt-console','web-revision']),
 'library':('建筑库与选择器',['library-archive','structure-selector','component-assets','asset-libraries','reusable-recipes','project-batch']),
 'handoff':('委派阅读记录',['delegation-and-review']),
 'maintenance':('可选：软件工具维护与接口扩展',['state-and-maintenance','extensions']),
}

def sync_runtime(workspace):
    """Copy a verified local runtime, preserving any previous or edited snapshot."""
    from nbt_render_runtime import write_render_binding
    write_render_binding(workspace, ENGINE)
    from nbt_history import write_git_binding
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
    if target.is_dir() and all((target/name).is_file() and hashlib.sha256((target/name).read_bytes()).hexdigest()==digest for _,name,digest in files):return target
    if target.exists():target=folder/(bundle[:16]+'_'+uuid.uuid4().hex[:8])
    staging=folder/('.staging_'+uuid.uuid4().hex);staging.mkdir()
    for source,name,digest in files:
        dest=staging/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        if hashlib.sha256(dest.read_bytes()).hexdigest()!=digest:raise ValueError('Skill复制校验失败：'+name)
    (staging/'runtime-manifest.json').write_text(json.dumps(dict(schema_version=1,bundle_sha256=bundle,files=[dict(path=name,sha256=digest) for _,name,digest in files]),ensure_ascii=False,indent=2),encoding='utf8')
    staging.rename(target)
    return target

def read_config(workspace):
    file=Path(workspace)/'.nbtcreator/skill-exposure.json'
    try:config=json.loads(file.read_text(encoding='utf8'))
    except FileNotFoundError:config=dict(schema_version=1,enabled_groups=[group for group in GROUPS if group!='maintenance'])
    if config.get('schema_version')!=1 or not isinstance(config.get('enabled_groups'),list) or any(g not in GROUPS for g in config['enabled_groups']):raise ValueError('知识库暴露配置无效')
    config['enabled_groups']=list(dict.fromkeys(['core',*config['enabled_groups']]))
    config['custom_knowledge']=validate_custom(workspace,config.get('custom_knowledge',[]))
    return config

def validate_custom(workspace,items):
    if not isinstance(items,list) or len(items)>100:raise ValueError('自定义知识库最多100项')
    root=(Path(workspace)/'.nbtcreator/knowledge').resolve();ids=set()
    for item in items:
        if not isinstance(item,dict) or set(item)-{'id','label','path','enabled'} or not re.fullmatch(r'custom_[a-f0-9]{16}',item.get('id','')) or item['id'] in ids:raise ValueError('自定义知识条目无效')
        ids.add(item['id']);target=(Path(workspace)/'.nbtcreator'/item.get('path','')).resolve()
        if not target.is_relative_to(root) or not target.is_file() or target.suffix.lower() not in {'.md','.txt'}:raise ValueError('自定义知识文件不存在或超出知识目录')
        if not isinstance(item.get('label'),str) or len(item['label'])>150 or re.search(r'[\r\n\[\]]',item['label']) or type(item.get('enabled')) is not bool or Path(item['path']).is_absolute():raise ValueError('知识名称、相对路径或开关无效')
    return items

def import_knowledge(workspace,documents):
    workspace=Path(workspace).resolve();config=read_config(workspace);folder=workspace/'.nbtcreator/knowledge'
    planned=[]
    if not documents or len(documents)>32:raise ValueError('每次选择1至32份Markdown或TXT知识文件')
    for source in documents:
        source=Path(source)
        if source.suffix.lower() not in {'.md','.txt'} or source.stat().st_size>2*1024*1024:raise ValueError('仅支持不超过2MiB的Markdown/TXT文件')
        data=source.read_bytes();data.decode('utf-8-sig');digest=hashlib.sha256(data).hexdigest()[:16]
        planned.append((folder/(digest+source.suffix.lower()),data,dict(id='custom_'+digest,label=re.sub(r'[\[\]()\r\n]','',source.stem)[:150],path='knowledge/'+digest+source.suffix.lower(),enabled=True)))
    if len(config['custom_knowledge'])+len(planned)>100:raise ValueError('自定义知识库最多100项')
    folder.mkdir(parents=True,exist_ok=True)
    for target,data,item in planned:
        if target.exists() and target.read_bytes()!=data:raise ValueError('同名知识文件有本地修改，未覆盖')
        target.write_bytes(data)
        if not any(existing['id']==item['id'] for existing in config['custom_knowledge']):config['custom_knowledge'].append(item)
    return apply(workspace,config)

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
    config=read_config(workspace)
    caps=capabilities()
    return dict(config,groups=[dict(id=key,label=label,required=key=='core',files=[p+'.md' for p in files]) for key,(label,files) in GROUPS.items()],
                facade='.agents/skills/nbtcreator-workspace/SKILL.md',launcher=mise_launcher(workspace),
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
        ('整栋初稿：纯文字',['simple-building'],'从使用者的一次活动推导空间和细部。例：收卷、登梯、归架决定柜台的操作侧、梯顶转身位和书格高度。'),
        ('整栋初稿：有参考图',['simple-building'],'从图中标出轮廓及可辨节点，再读进深、材料交接与支承。例：对照窗洞内退、窗台出挑和柱梁落点；背面与室内的补全单记理由。'),
        ('简单独立整栋初稿',['simple-building'],'直接用共享工作模型或可执行建筑方案。多层、结构接口和专门操作面转入复杂审阅。'),
        ('室内用途与建筑群验收',['architecture-workflow'],'室内用 use_face 查操作侧、工作高度与净距；街区沿主街、支路、门槛走到室内，按用途查公共与服务路线。多层布局可另出逐层平面与纵剖。'),
        ('建筑方案、构造与审阅闭环',['architecture-workflow'],'设计参数驱动真实构件；三层出图、问题定位、源绑定回查和游戏验收分别执行。'),
        ('完整主模型与独立构件',['working-model','parametric-components'],'工作模型管理安装、归属、修改和制作版；构件只做适用检查。'),
        ('整栋初稿的地面嵌纹、屏风边饰与墙面徽记',['pattern-authoring','pattern-fitting'],'从主模型路线转入纹样专题；已有图源可直接拟合。预览代表单元，再用实际承载面和观察位置回查。'),
        ('准备或制作纹样图源',['pattern-authoring'],'已有合适图源可直接进入拟合。'),
        ('拟合纹样与检查质量',['pattern-fitting'],'按微型、普通面板或圆柱模式读对应完整章节，实际看图。'),
        ('安装到已有建筑',['surface-mounting'],'先绑定真实源、上下文和安装面，再生成候选。'),
        ('参数引用和对象联动',['object-scenes'],'使用稳定ID和关系，不靠手工猜测多个构件如何拼合。'),
        ('空间和风格推演',['design-grammar','architecture-knowledge-base'],'按用途选适用完整章节，例子不是建筑模板。'),
        ('近观道具与薄构件',['micro-props'],'检查支承、使用侧和实际预览。'),
        ('批注与已有模型修改',['agent-feedback'],'先读取源、坐标和图像证据，核对保护与当前阶段。'),
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
        '有任务 ID 就先读紧凑视图：提示词工作台用 `task-client inspect prompts <id>`，建筑修改用 `task-client inspect tasks <id>`。按返回的 `source_matches`、`next` 和 `expand` 行动；源已变化则停下，明确选定任务后才领取。不用先查全量工具。',
        '需要找已发布的提示词任务时用 `prompts tasks --status pending`。','',
        '## 没有交接任务时','',
        f'- 整栋初稿：纯文字从用途推导空间，有参考图先标出可见结构。读{link("simple-building")}；复杂布局再看{link("architecture-workflow")}。另有[归卷阁样例]({relative}/assets/examples/reading-loft/README.md)。',
        '- 局部修改、纹样、构件与维护：按[任务路线和已启用资料](knowledge.md)选读。不要从头读完整目录。',
        '- 已知工具用 `capabilities --agent-tool <名称>` 或 `<命令> --help` 查字段。不知道入口时再用 `capabilities --routes`。`paths` 返回共享引擎位置。',
        f'- 查参考读{link("reference-retrieval")}：`retrieve search --request <JSON文件>` 后凭 `receipt` 和 `R1` 取证。查历史原文加 `source_kind: library`，不必先查库编号。只在用户要求时联网。',
        '- 找可用资产：`asset-libraries browse --request <JSON文件>`，文件写 `{"query":"尖拱","limit":4}`。不带 `query` 会列出完整目录；命中不是放置批准。',
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
    custom=[item for item in config.get('custom_knowledge',[]) if item['enabled']]
    if custom:
        heading=['','## 用户补充知识','这些资料用于当前任务，不改变核心边界，也不授予批准。']
        index+=heading
        for item in custom:
            target=os.path.relpath(workspace/'.nbtcreator'/item['path'],facade).replace('\\','/')
            index.append(f"- [{item['label']}]({target})")
    return '\n'.join(lines)+'\n','\n'.join(index)+'\n'

def apply(workspace,config=None):
    workspace=Path(workspace).resolve()
    if workspace==ENGINE.parents[2] and (workspace/'desktop/main.cjs').is_file():raise ValueError('软件源码或安装目录不生成创作Skill；请选择实际创作项目根目录')
    folder=workspace/'.nbtcreator';folder.mkdir(parents=True,exist_ok=True)
    from nbt_ai_style import load as load_style
    load_style(workspace,create=True)
    file=folder/'skill-exposure.json'
    if config is not None:
        if set(config)-{'schema_version','enabled_groups','custom_knowledge'}:raise ValueError('未知暴露配置字段')
        if config.get('schema_version')!=1 or not isinstance(config.get('enabled_groups'),list) or any(g not in GROUPS for g in config['enabled_groups']):raise ValueError('暴露配置无效')
        config=dict(config,enabled_groups=list(dict.fromkeys(['core',*config['enabled_groups']])))
        config['custom_knowledge']=validate_custom(workspace,config.get('custom_knowledge',read_config(workspace).get('custom_knowledge',[])))
    else:config=read_config(workspace)
    runtime=sync_runtime(workspace)
    facade=workspace/'.agents/skills/nbtcreator-workspace';facade.mkdir(parents=True,exist_ok=True)
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
    generated={'SKILL.md':entry_text,'knowledge.md':index_text,'nbt.py':wrapper}
    marker=folder/'facade-manifest.json'
    try:previous=json.loads(marker.read_text(encoding='utf8'))
    except (FileNotFoundError,ValueError):previous={}
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
                if backup is None:backup=folder/'skill-backups'/uuid.uuid4().hex;backup.mkdir(parents=True)
                shutil.copy2(target,backup/name)
        temp=target.with_name(target.name+'.tmp');temp.write_bytes(payload);temp.replace(target)
        if name=='nbt.py' and os.name!='nt':target.chmod(target.stat().st_mode|0o111)
    marker.write_text(json.dumps({name:hashlib.sha256(text.encode('utf8')).hexdigest() for name,text in generated.items()},indent=2),encoding='utf8')
    file.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return show(workspace)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['show','apply','import']);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('--config',type=Path);parser.add_argument('--document',type=Path,action='append')
    args=parser.parse_args();result=import_knowledge(args.workspace,args.document) if args.command=='import' else show(args.workspace) if args.command=='show' else apply(args.workspace,json.loads(args.config.read_text(encoding='utf8')) if args.config else None)
    print(json.dumps(result,ensure_ascii=False))
