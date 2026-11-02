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
 'core':('必需：工作流与验收',['whole-model-workflow','player-scale','design-principles','spatial-detail-design','validation-workflow','state-and-maintenance','refinement','delivery-workflow','output-storage','exposed-tools']),
 'architecture':('建筑风格与场所',['architecture-knowledge-base','structure-atlas','design-grammar']),
 'organic':('洞穴与自由形空间',['organic-spaces']),
 'linked':('多空间与跨层联动',['linked-spaces']),
 'props':('细微道具',['micro-props']),
 'materials':('混材、地面与风化',['patterns','floors','weathering']),
 'modelling':('通用建模工具',['modelling-tools','toolkit']),
 'rendering':('纹理预览与图像评审',['rendering']),
 'saodg':('可选：SAODG接入',['saodg-constraints','mod-structures']),
 'desktop':('桌面、提示词与网页转换',['nbtcreator','detail-control','prompt-console','web-revision']),
 'library':('建筑库与选择器',['library-archive','structure-selector']),
 'handoff':('委派阅读记录',['delegation-and-review']),
}

def sync_runtime(workspace):
    """Copy a verified local runtime, preserving any previous or edited snapshot."""
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
    workspace=Path(workspace).resolve();folder=workspace/'.nbtcreator';folder.mkdir(parents=True,exist_ok=True)
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
      '无界面调用：`python .agents/skills/nbtcreator-workspace/nbt.py capabilities`；`control --help`、`refine --help`。Electron无需启动。',
      '工具能力与应用保持一致，AI结构建议只覆盖其中的受限子集。已有批准/预览均绑定源哈希；不要并发写出同一建筑。','','## 已启用知识库']
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
if len(sys.argv)==1:raise SystemExit('调用方式：nbt.py capabilities | control --help | refine --help')
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
