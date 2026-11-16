"""Workspace-local skill facade. Knowledge selection is guidance, not a filesystem ACL."""
import argparse
import json
import os
import hashlib
import shutil
import uuid
import re
from pathlib import Path
from nbt_capabilities import capabilities
ENGINE=Path(__file__).resolve().parents[1]
GROUPS={
 'core':('工作流、验收与协作（按任务读取）',['knowledge-map','whole-model-workflow','player-scale','design-principles','spatial-detail-design','validation-workflow','collision-envelopes','state-and-maintenance','refinement','delivery-workflow','output-storage','exposed-tools','agent-feedback','comment-tasks','prompt-archive','batch-workspaces','selection-edit','reference-retrieval','diagnostic-guidance','agent-task-return','agent-protocol','architect-tools','architecture-workflow','ai-creative-preferences','version-history','snbt-authoring']),
 'architecture':('建筑风格、场所与构造',['architecture-knowledge-base','structure-atlas','design-grammar','architectural-bays','classical-columns']),
 'organic':('洞穴与自由形空间',['organic-spaces']),
 'linked':('多空间与跨层联动',['linked-spaces']),
 'props':('细微道具',['micro-props']),
 'materials':('混材、地面与风化',['patterns','floors','weathering']),
 'modelling':('构件、纹样与模型装配',['working-model','modelling-tools','toolkit','parametric-components','pattern-authoring','pattern-fitting','surface-mounting','modeling-sessions','object-scenes','compute-transforms','pattern-spectral','extensions']),
 'rendering':('纹理预览与图像评审',['rendering']),
 'saodg':('可选：SAODG接入',['saodg-constraints','mod-structures','SAOartguide','room-examples','sealed-examples']),
 'desktop':('桌面、提示词与网页转换',['nbtcreator','detail-control','prompt-console','web-revision']),
 'library':('建筑库与选择器',['library-archive','structure-selector','component-assets','reusable-recipes','project-batch']),
 'handoff':('委派阅读记录',['delegation-and-review']),
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
    except FileNotFoundError:config=dict(schema_version=1,enabled_groups=list(GROUPS))
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

def show(workspace):
    config=read_config(workspace)
    caps=capabilities()
    return dict(config,groups=[dict(id=key,label=label,required=key=='core',files=[p+'.md' for p in files]) for key,(label,files) in GROUPS.items()],
                facade='.agents/skills/nbtcreator-workspace/SKILL.md',tool_count=len(caps['tools']),capabilities_sha256=caps['capabilities_sha256'])


def facade_knowledge(runtime, facade, workspace, relative, config):
    """Keep task selection in the entrypoint and the selected inventory separate."""
    enabled={name for group in config['enabled_groups'] for name in GROUPS[group][1]}
    def link(name):
        file=runtime/'references'/(name+'.md')
        if not file.is_file():raise ValueError('缺少知识文件：'+name)
        title=next((line.lstrip('# ').strip() for line in file.read_text(encoding='utf8').splitlines() if line.startswith('# ')),name)
        return f'[{title}]({relative}/references/{name}.md)'
    routes=[
        ('整栋初稿：纯文字',['architecture-workflow'],'从使用者的一次活动推导空间和细部。例：收卷、登梯、归架决定柜台的操作侧、梯顶转身位和书格高度。'),
        ('整栋初稿：有参考图',['architecture-workflow'],'从图中标出轮廓及可辨节点，再读进深、材料交接与支承。例：对照窗洞内退、窗台出挑和柱梁落点；背面与室内的补全单记理由。'),
        ('两条路线共用的初稿步骤',['whole-model-workflow','player-scale','design-principles','spatial-detail-design'],'完整读这四篇，再把代表节点做进主模型。从玩家站位看整体、入口、使用面与构造交接，改动细部后复验相邻通路。'),
        ('室内用途与建筑群验收',['architecture-workflow'],'室内用 use_face 查操作侧、工作高度与净距；街区沿主街、支路、门槛走到室内，按用途查公共与服务路线。多层布局可另出逐层平面与纵剖。'),
        ('建筑方案、构造与审阅闭环',['architecture-workflow'],'设计参数驱动真实构件；三层出图、问题定位、源绑定回查和游戏验收分别执行。'),
        ('完整主模型与独立构件',['working-model','parametric-components'],'工作模型管理安装、归属、修改和制作版；构件只做适用检查。'),
        ('准备或制作纹样图源',['pattern-authoring'],'已有合适图源可直接进入拟合。'),
        ('拟合纹样与检查质量',['pattern-fitting'],'按微型、普通面板或圆柱模式读对应完整章节，实际看图。'),
        ('安装到已有建筑',['surface-mounting'],'先绑定真实源、上下文和安装面，再生成候选。'),
        ('参数引用和对象联动',['object-scenes'],'使用稳定ID和关系，不靠手工猜测多个构件如何拼合。'),
        ('空间和风格推演',['design-grammar','architecture-knowledge-base'],'按用途选适用完整章节，例子不是建筑模板。'),
        ('近观道具与薄构件',['micro-props'],'检查支承、使用侧和实际预览。'),
        ('批注与已有模型修改',['agent-feedback'],'先读取源、坐标和图像证据，核对保护与当前阶段。'),
        ('用户看图后批准精修',['refinement'],'确认仍绑定相同源与图像后再执行。'),
        ('只读检查与失败定位',['validation-workflow','diagnostic-guidance'],'解释真实检查证据，不把字段检查写成模型已通过。'),
        ('验证和看图',['validation-workflow','rendering'],'技术、空间、构造与主题分别给结论。'),
        ('已有资产保存与放置',['component-assets','reusable-recipes'],'先查询与预览，放置只生成受保护的候选。'),
        ('保存、续版与交付',['snbt-authoring','version-history','output-storage'],'默认保存SNBT；定稿NBT必须明确要求。'),
        ('任务领取与结果回传',['agent-protocol','agent-task-return'],'先读取任务和租约，稳定请求编号幂等回传，不制造批准。'),
        ('单工具检查与维护',['state-and-maintenance'],'只读当前实现及所改专题，不默认生成建筑。'),
        ('注册器与接口扩展',['extensions'],'新增公共能力时再读注册与目录同步要求。')]
    lines=['---','name: nbtcreator-workspace','description: 当前工作区的Minecraft NBT建模接口，按任务读取已选择知识，共用受检引擎与工具契约。','---','',
        '# 当前工作区建模接口','',
        '工作目录使用当前 Agent 项目根目录，资产在 `nbt_models/`。这是可迁移的冻结引擎入口，Electron无需启动；不硬编码应用安装路径。',
        '完整主模型用全局坐标，保留显式墙mask、实例归属、源/上下文/图像哈希、保护、留白与预算。候选、保存、采用与定稿分别执行，工具成功不表示批准。',
        '整栋先密闭并保存开洞前证据，再按声明开门、验路线与实际看图。独立构件只做适用检查；维护不默认生成建筑。只有用户明确要求SAODG接入才采用专用端口协议。',
        '初稿向用户展示对应缩略图后，明确同意才授权精修；沿用仍有效的原授权。无回复、超时、知识文件、AI建议和测试记录都不构成确认。默认保存并回读SNBT，明确要求定稿才写交付NBT。','',
        '## 找到接口与本次资料','',
        '`python .agents/skills/nbtcreator-workspace/nbt.py paths` 返回实际引擎路径；已知工具用 `capabilities --agent-tool <名称>`，主模型用 `capabilities --model`，建筑方案用 `capabilities --architecture`，各命令用 `--help` 查询。工具目录是严格字段和CLI映射的唯一来源。',
        '任务脚本据 `paths` 导入共享API；model --request 管理完整主模型，parametric_compile 编译构件，pattern_microfit 拟合单元，scene_compile 管理联动候选。需要连续纯候选调用时再用 session。',
        '先读工作区 [ai-style.json](../../../.nbtcreator/ai-style.json) 的当前工作流区域，可用 `ai-style prompt --workflow <区域>` 查询；用户本次要求优先，偏好不改变约束和批准。',
        '下面只列已启用资料能支持的路线。已启用不等于每次通读；完整专题目录见[本次知识索引](knowledge.md)，未选专题不默认读取。知识选择不是额外执行权限。','',
        '## 选择当前任务','',
        f'整栋初稿按下面两种输入开工。可直接运行[归卷阁与归卷院样例]({relative}/assets/examples/reading-loft/README.md)，对照堵梯口、站错侧、逐层剖视与街道到案前的通路。','',
        '| 当前任务 | 先读 | 下一步与范围 |','| --- | --- | --- |']
    for label,names,action in routes:
        if all(name in enabled for name in names):lines.append('| '+label+' | '+'、'.join(link(name) for name in names)+' | '+action+' |')
    lines+=['',
        '接手工作台提示词时，先 `prompts tasks --status pending` 发现，再 `prompts task --id <id>` 读取正文、方案、任务目录和 source_matches；登记状态使用任务租约，状态不等于验收。',
        '交付时给真实源、图像与验证路径。用 review-record 的 delivery_summary 说明已查通路、已看与待看的位置、待回查问题；再写实际观察和相应的游戏实测情况。']
    index=['# 本次已启用知识','',
        '这是按工作区选择生成的目录，供按任务查找；不用从第一篇读到最后一篇。先按 SKILL.md 选择任务阶段，再读对应完整章节。严格工具字段仍从 capabilities 查询。','']
    for group in config['enabled_groups']:
        label,names=GROUPS[group];index+=['## '+label,'']
        index.extend('- '+link(name) for name in names)
        index.append('')
    custom=[item for item in config.get('custom_knowledge',[]) if item['enabled']]
    if custom:
        heading=['','## 用户补充知识','这些资料用于当前任务，不改变核心边界，也不授予批准。']
        lines+=heading;index+=heading
        for item in custom:
            target=os.path.relpath(workspace/'.nbtcreator'/item['path'],facade).replace('\\','/')
            row=f"- [{item['label']}]({target})";lines.append(row);index.append(row)
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
    entry_text,index_text=facade_knowledge(runtime,facade,workspace,relative,config)
    wrapper='''"""Generated workspace entry; implementation remains in the shared application engine."""
from pathlib import Path
import sys,subprocess,json
engine=(Path(__file__).resolve().parent/ENGINE_RELATIVE).resolve()
if not engine.is_dir():raise SystemExit('引擎路径变化，请在应用AI设置重新同步Skill暴露配置')
catalog=json.loads((engine/'tool-catalog.json').read_text(encoding='utf8'))
if len(sys.argv)==1:raise SystemExit('调用方式：nbt.py paths | capabilities | feedback --help | control --help | refine --help')
command,*args=sys.argv[1:]
script=catalog['commands'].get(command)
if script is None:raise SystemExit('未知工具，请先调用capabilities')
if command in ('inspect','snapshot','render','regress'):args=[command,*args]
raise SystemExit(subprocess.call([sys.executable,'-B',str(engine/'scripts'/script),*args],cwd=Path.cwd()))
'''.replace('ENGINE_RELATIVE',repr(relative))
    generated={'SKILL.md':entry_text,'knowledge.md':index_text,'nbt.py':wrapper}
    marker=folder/'facade-manifest.json'
    try:previous=json.loads(marker.read_text(encoding='utf8'))
    except (FileNotFoundError,ValueError):previous={}
    backup=None
    for name,text in generated.items():
        target=facade/name
        if target.is_file():
            current=target.read_bytes();digest=hashlib.sha256(current).hexdigest()
            if current!=text.encode('utf8') and previous.get(name)!=digest:
                if backup is None:backup=folder/'skill-backups'/uuid.uuid4().hex;backup.mkdir(parents=True)
                shutil.copy2(target,backup/name)
        temp=target.with_name(target.name+'.tmp');temp.write_text(text,encoding='utf8');temp.replace(target)
    marker.write_text(json.dumps({name:hashlib.sha256(text.encode('utf8')).hexdigest() for name,text in generated.items()},indent=2),encoding='utf8')
    file.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return show(workspace)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['show','apply','import']);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('--config',type=Path);parser.add_argument('--document',type=Path,action='append')
    args=parser.parse_args();result=import_knowledge(args.workspace,args.document) if args.command=='import' else show(args.workspace) if args.command=='show' else apply(args.workspace,json.loads(args.config.read_text(encoding='utf8')) if args.config else None)
    print(json.dumps(result,ensure_ascii=False))
