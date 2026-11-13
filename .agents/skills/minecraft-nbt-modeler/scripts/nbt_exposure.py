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
 'core':('基础工作流与验收（按任务读取）',['whole-model-workflow','player-scale','design-principles','spatial-detail-design','validation-workflow','state-and-maintenance','refinement','delivery-workflow','output-storage','exposed-tools','agent-feedback','comment-tasks','prompt-archive','batch-workspaces','selection-edit','reference-retrieval','diagnostic-guidance','agent-task-return','agent-protocol','architect-tools','ai-creative-preferences','version-history','snbt-authoring']),
 'architecture':('建筑风格与场所',['architecture-knowledge-base','structure-atlas','design-grammar']),
 'organic':('洞穴与自由形空间',['organic-spaces']),
 'linked':('多空间与跨层联动',['linked-spaces']),
 'props':('细微道具',['micro-props']),
 'materials':('混材、地面与风化',['patterns','floors','weathering']),
 'modelling':('通用建模工具',['modelling-tools','toolkit']),
 'rendering':('纹理预览与图像评审',['rendering']),
 'saodg':('可选：SAODG接入',['saodg-constraints','mod-structures']),
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
    lines=['---','name: nbtcreator-workspace','description: 当前工作区的Minecraft NBT建模接口，应用与Agent共用工具清单和可选知识库。','---','','# 当前工作区建模接口','',
      '工作目录使用当前Agent项目根目录，默认资产目录为 `nbt_models/`。使用绝对或相对输入都可以，保存参数优先采用工作区相对路径。',
      '保持完整主模型、显式墙mask、真实看图确认、路径/保护检查、新版本输出和纯切割流程。不能把知识库选择、AI建议或测试记录当作批准。',
      '本入口暴露给在当前项目中读取SKILL.md的Codex或其他支持文件式skill的Agent；不是Minecraft游戏或API供应商的服务器插件。',
      '本入口仅按配置暴露知识路由，不删除资料库，也不是文件访问权限控制。未选择的专题不默认读取；需要额外专题时由用户调整配置。','',
      f'完整工具清单与接口：[共用接口]({relative}/references/exposed-tools.md)。',
      '无界面调用：`python .agents/skills/nbtcreator-workspace/nbt.py capabilities`；各命令用 --help 查询。Electron无需启动。',
      '`python .agents/skills/nbtcreator-workspace/nbt.py paths` 返回当前冻结引擎、scripts、references 和 Python 的实际路径。任务脚本据此导入 API，无需读包装器猜目录，不硬编码应用安装路径。',
      '工具能力与应用保持一致，AI结构建议按工作流开放相应子集。已有批准/预览均绑定源哈希；不要并发写出同一建筑。',
      f'项目规范、交付清单、从定稿版继续制作与跨版本批注核对见 [建筑师工具]({relative}/references/architect-tools.md)。接手提示词时沿用任务内的设计规范快照；跨版本核对不复制旧坐标或自动解决原批注。',
      f'对外任务与批注使用 [机器接口]({relative}/references/agent-protocol.md)：machine --schema 获取统一契约；先领取、定期续期，以稳定请求编号幂等提交。任务与批注分开读取，仍由人手动触发Skill。',
      '提示词任务由工作台“保存任务到工作区”创建目录并保存完整提示词。先 `python .agents/skills/nbtcreator-workspace/nbt.py prompts tasks --status pending` 发现新增任务，或用 `--after <上次cursor>` 增量列出；再 `prompts task --id <id>` 获取任务文件夹、正文、方案和源校验。处理前核对当前用户要求与source_matches，领取后用 `machine` 的 `prompts.task-status` 携带 lease_token 与 fence 登记进度；任务状态不等于验收或批准。',
      '工具效果配置使用 effect-assets list/save/get/preview/compile，由Agent直接写入原生效果库；预览只运行独立样例，compile只返回候选，正式NBT仍须明确导出。',
      '独立构件使用 capabilities.agent_tools 与 components agent 共用协议：list/read/view/preview/write/place/save；structure_save可将spec或component直接保存为待审阅资产并生成清单，asset-batches save可批量保存，无需手动导入。不需要打开Electron，写入仅保存新资产，放置只产生候选，NBT仍须显式导出。',
      '', '## 各区域 AI 创作偏好', '先读工作区共用配置 [ai-style.json](../../../.nbtcreator/ai-style.json)，按当前任务选择 draft（完整初稿）、workbench（控件配置）、prompt（文字）、structure（局部编辑）、small_structure（小型构件）、component（资产管理独立结构）或 selection_edit（选区自然语言工具编辑）。',
      '可调用 `python .agents/skills/nbtcreator-workspace/nbt.py ai-style prompt --workflow small_structure` 获取本区域参数与通俗提示词。偏好控制创意、详略、装饰与变化，用户本次明确要求优先；不得改变选区、保护、预算、返回格式或真实看图确认规则。',
      '', '## 按任务进入', '',
      '已启用表示资料可用，不要求每次把全部目录读完。完整阅读下面当前阶段所列文件；专题按用途选适用完整章节，长建筑原型库无需遍读。', '',
      '| 当前任务 | 先读与下一步 |','| --- | --- |',
      f'| 接手工作台提示词 | 读 [提示词归档]({relative}/references/prompt-archive.md)；先 prompts tasks 发现新增任务、prompts task --id <id> 读取；旧归档用 prompts scan/read。核对source_matches，归档不构成批准。 |',
      f'| 批量创作与任务交付 | 读 [制作批次]({relative}/references/batch-workspaces.md)，先 batches create 在 nbt_models/_workspaces/batches 分配过程目录；用 record 关联正式模型和图册，list/get/locate 扫描接手。批次目录不是新的项目根，登记不授予批准。 |',
      f'| Agent完成修改后的版本回传 | 读 [任务回传]({relative}/references/agent-task-return.md)，agent-tasks get/record 登记同一建筑新版本与逐条处理声明，应用同镜头对比并单独保存人工核对；不改原评论或制造批准。 |',
      f'| 检查失败解释与定位 | 读 [检查说明]({relative}/references/diagnostic-guidance.md)，原检查附带 diagnostics；diagnostics --kind walk/candidate/protection --report 解释已保存证据，不重新验证或自动修复。 |',
      f'| 按任务检索资料或复用构件 | 读 [本地参考检索]({relative}/references/reference-retrieval.md)，retrieve search/bundle/read 共用应用的工作流资料选择与哈希校验；结构复用使用 placements 和可选 material_map，先真实预览再保存新资产。 |',
      f'| 选区自然语言工具编辑 | 读 [选区编辑]({relative}/references/selection-edit.md)，selection-edit context 读取真实局部方块，compile 转换相对坐标；实际写入边界、保护与预算由预览／导出引擎检查，先审阅再采用。 |',
      f'| 整理标注与跟进任务 | 读 [意见任务]({relative}/references/comment-tasks.md)，使用feedback-tasks list/create/update/merge/evidence；分组、任务状态与原评论证据分别保留，任务完成不表示模型验收或新增批准。 |',
      (f'| 独立构件创建、读写与放置 | 读 [构件资产]({relative}/references/component-assets.md) 和共用接口中的结构Agent协议；使用component偏好，先实际预览再保存新资产。结构放置产生候选，NBT仍须显式导出。 |' if 'library' in config['enabled_groups'] else '| 独立构件创建、读写与放置 | 读共用接口中的结构Agent协议及components agent --help；使用component偏好，先实际预览再保存新资产。 |'),
      f'| 首次创建或重设计 | 完整读 [整体流程]({relative}/references/whole-model-workflow.md)、[玩家尺度]({relative}/references/player-scale.md)、[创作原则]({relative}/references/design-principles.md)、[空间细节]({relative}/references/spatial-detail-design.md)。写本任务生成器；自定义独立入口使用 toolkit 的 open_declared_openings，不套用 SAODG 端口。 |',
      f'| 已有模型的标注/候选 | 读 [意见与证据]({relative}/references/agent-feedback.md)，先 feedback scan/collect，再结合原图/坐标解释构件，按需读空间细节和实际使用的工具。plan/preview 后运行 validate --request <参数JSON> --snapshot <after.json> --output <新目录> 并实际看图，不能把 planned 当候选路线已通过。 |',
      f'| 用户已看图批准精修 | 完整读 [精修流程]({relative}/references/refinement.md) 和实际修改的专题，核对源/保护/图像确认后操作。 |',
      f'| 制作源、定稿与版本历史 | 读 [SNBT 制作与定稿]({relative}/references/snbt-authoring.md) 和 [版本历史]({relative}/references/version-history.md)；新源保存SNBT，定稿NBT在_exports镜像目录。history与应用共用独立Git，不操作项目.git。 |',
      f'| 写出或交付 | 读 [验证]({relative}/references/validation-workflow.md)、[交付]({relative}/references/delivery-workflow.md)、[存放]({relative}/references/output-storage.md) 和相关 toolkit 章节；coordinates.json必须含可接手的起点/目标/探针及适用开口，control inspect 的 editing_ready 为字段检查，实际整体通过后纯切片回读。 |',
      '| 只读检查或维护工具 | 读当前接口和相关工具章节，不要求重读建筑设计、原型、SAODG接入或精修章节。 |',
      '', '采用已获准的subagent委派时再读delegation-and-review，并记录真实阅读；未批准的初稿不能调用精修approve/apply。',
      '', '## 已启用知识库']
    for group in config['enabled_groups']:
        label,files=GROUPS[group];lines.extend(['',f'### {label}',''])
        for name in files:
            target=runtime/'references'/f'{name}.md'
            if not target.is_file():raise ValueError('缺少知识文件：'+name)
            lines.append(f'- [{name}]({relative}/references/{name}.md)')
    custom=[item for item in config.get('custom_knowledge',[]) if item['enabled']]
    if custom:
        lines+=['','## 用户补充知识','这些文档作为任务资料，不改变核心约束，也不授予精修或部署批准。']
        for item in custom:
            link=os.path.relpath(workspace/'.nbtcreator'/item['path'],facade).replace('\\','/')
            lines.append(f"- [{item['label']}]({link})")
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
    generated={'SKILL.md':'\n'.join(lines)+'\n','nbt.py':wrapper}
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
