"""Private Git-backed building history; never operates on the project's own Git."""
import argparse,copy,hashlib,json,os,re,shutil,subprocess,time,uuid
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
from nbt_web_paths import project_paths,reserve_version

ENGINE=Path(__file__).resolve().parents[1]
SHA=re.compile(r'^[a-f0-9]{64}$')
IDENTIFIER=re.compile(r'^v_[a-f0-9]{24}$')
MAX_FILE=256*1024*1024
MAX_STATE=64*1024*1024
SKIP={'.git','.nbtcreator','node_modules','__pycache__','_workspaces'}
PRIVATE={'api-settings.json','credentials.json','secrets.json'}
EXTENSIONS={'.json','.gz','.nbt','.snbt','.png','.jpg','.jpeg','.webp','.md','.txt','.py'}

def encode(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8')
def digest(value):return hashlib.sha256(value).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def file_hash(file):
    h=hashlib.sha256()
    with Path(file).open('rb') as stream:
        for data in iter(lambda:stream.read(1048576),b''):h.update(data)
    return h.hexdigest()
def relative(workspace,file):return Path(file).resolve().relative_to(workspace).as_posix()
def model_file(workspace,value):
    if not isinstance(value,(str,Path)):raise ValueError('请选择建筑主模型')
    file=(workspace/Path(value)).resolve()
    if not file.is_relative_to(workspace/'nbt_models'):raise ValueError('版本历史只管理当前工作区 nbt_models 内的建筑')
    return file
def owned(root,file):
    file=Path(file)
    if not file.resolve().is_relative_to(root.resolve()) or file.is_symlink():raise ValueError('历史目录含越界路径或符号链接')
    return file
def safe_name(name):
    if not isinstance(name,str) or '\\' in name or ':' in name or not name or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:raise ValueError('历史文件路径无效')
    if any(part.lower().split('.')[0] in {'con','prn','aux','nul',*(f'com{i}' for i in range(1,10)),*(f'lpt{i}' for i in range(1,10))} for part in PurePosixPath(name).parts):raise ValueError('历史文件名称不可用于 Windows')
    return name

def resolve_git(workspace=None):
    explicit=os.environ.get('NBTCREATOR_GIT')
    if explicit:
        resolved=shutil.which(explicit)
        if resolved:return str(Path(resolved).resolve())
        raise ValueError('指定的 Git 运行环境不可用')
    for parent in [ENGINE,*ENGINE.parents]:
        candidate=parent/'runtime/git/cmd/git.exe'
        if candidate.is_file():return str(candidate)
    # Frozen workspace Skills can share the application's verified Git binary.
    # The renderer's installed engine never executes a workspace-selected binary.
    if workspace and (ENGINE/'runtime-manifest.json').is_file():
        binding=Path(workspace)/'.nbtcreator/history-runtime.json'
        pin=ENGINE/'assets/git-runtime.json'
        if binding.is_file() and pin.is_file():
            if binding.stat().st_size>4096:raise ValueError('Git 运行环境绑定无效')
            data=json.loads(binding.read_text(encoding='utf8'));expected=json.loads(pin.read_text(encoding='utf8'))
            candidate=(binding.parent/data.get('executable','')).resolve()
            if data.get('schema_version')==1 and expected.get('executable_sha256') and candidate.is_file() and file_hash(candidate)==expected['executable_sha256']:return str(candidate)
    installed=shutil.which('git')
    if installed:return str(Path(installed).resolve())
    raise ValueError('Git 运行环境不可用；请使用包含内置 Git 的完整便携版，或重新同步工作区 Skill')

def write_git_binding(workspace,engine=ENGINE):
    pin=Path(engine)/'assets/git-runtime.json'
    if not pin.is_file():return
    try:executable=Path(resolve_git(workspace));expected=json.loads(pin.read_text(encoding='utf8'))
    except (ValueError,OSError):return
    if file_hash(executable)!=expected.get('executable_sha256'):return
    folder=Path(workspace)/'.nbtcreator';folder.mkdir(parents=True,exist_ok=True)
    try:location=os.path.relpath(executable,folder).replace('\\','/')
    except ValueError:location=str(executable)
    temporary=folder/('history-runtime.'+uuid.uuid4().hex+'.tmp');temporary.write_bytes(encode(dict(schema_version=1,executable=location)));temporary.replace(folder/'history-runtime.json')

class History:
    def __init__(self,workspace):
        self.workspace=Path(workspace).resolve();self.folder=self.workspace/'.nbtcreator/history';self.repository=self.folder/'repository.git';self.objects=self.folder/'objects'
        owned(self.workspace,self.folder);owned(self.folder,self.repository);owned(self.folder,self.objects)
        self.git=resolve_git(self.workspace)
        self.env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
        self.env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_SYSTEM=os.devnull,GIT_TERMINAL_PROMPT='0',GIT_AUTHOR_NAME='NBTCreator',GIT_AUTHOR_EMAIL='history@nbtcreator.local',GIT_COMMITTER_NAME='NBTCreator',GIT_COMMITTER_EMAIL='history@nbtcreator.local')
    def run(self,args,data=None,check=True):
        args=[self.git,'-c','commit.gpgsign=false','-c','core.hooksPath='+str(self.folder/'empty-hooks'),'--git-dir='+str(self.repository),*args]
        result=subprocess.run(args,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=self.env,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if len(result.stdout)>MAX_STATE:raise ValueError('版本历史超出读取上限')
        if check and result.returncode:raise ValueError('本地版本历史未完成：'+result.stderr.decode('utf8',errors='replace')[-1500:])
        return result
    @contextmanager
    def lock(self):
        if self.workspace==ENGINE.parents[2] and (self.workspace/'desktop/main.cjs').is_file():raise ValueError('软件源码目录不是创作工作区')
        self.folder.mkdir(parents=True,exist_ok=True);owned(self.workspace,self.folder)
        with (self.folder/'.write.lock').open('a+b') as stream:
            if stream.seek(0,2)==0:stream.write(b'0');stream.flush()
            deadline=time.monotonic()+10
            while True:
                try:
                    stream.seek(0)
                    if os.name=='nt':
                        import msvcrt
                        msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
                    else:
                        import fcntl
                        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic()>deadline:raise ValueError('另一窗口正在登记版本，请稍后重试') from None
                    time.sleep(.025)
            try:
                if not self.repository.exists():self.run(['init','--bare','--template=','--initial-branch=history',str(self.repository)])
                if not (self.repository/'HEAD').is_file():raise ValueError('专用历史目录不是有效仓库，未覆盖')
                yield
            finally:
                stream.seek(0)
                if os.name=='nt':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
                else:fcntl.flock(stream,fcntl.LOCK_UN)
    def state(self):
        if not (self.repository/'HEAD').is_file():return dict(schema_version=1,versions={},current={}),None
        result=self.run(['rev-parse','--verify','refs/heads/history'],check=False)
        if result.returncode:return dict(schema_version=1,versions={},current={}),None
        head=result.stdout.decode().strip();raw=self.run(['show',head+':index.json']).stdout;value=json.loads(raw)
        if value.get('schema_version')!=1 or not isinstance(value.get('versions'),dict) or not isinstance(value.get('current'),dict) or any(not IDENTIFIER.fullmatch(key) for key in value['versions']):raise ValueError('版本历史索引格式无效')
        return value,head
    def commit(self,state,head,message):
        raw=encode(state)
        if len(raw)>MAX_STATE:raise ValueError('版本历史索引过大')
        blob=self.run(['hash-object','-w','--stdin'],raw).stdout.decode().strip()
        tree=self.run(['mktree'],('100644 blob '+blob+'\tindex.json\n').encode()).stdout.decode().strip()
        commit=self.run(['commit-tree',tree,*(['-p',head] if head else []),'-m',message]).stdout.decode().strip()
        self.run(['update-ref','refs/heads/history',commit,head or '0'*40]);return commit
    def object_file(self,sha):
        if not isinstance(sha,str) or not SHA.fullmatch(sha):raise ValueError('历史文件哈希无效')
        return owned(self.objects,self.objects/sha[:2]/sha)
    def archive(self,file):
        file=Path(file)
        if file.is_symlink() or not file.is_file():raise ValueError('历史版本不接收符号链接或特殊文件')
        before=file.stat()
        if before.st_size>MAX_FILE:raise ValueError('单个历史文件超过256MiB：'+file.name)
        raw=file.read_bytes();after=file.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('文件正在变化，请稍后登记：'+file.name)
        sha=digest(raw);target=self.object_file(sha);target.parent.mkdir(parents=True,exist_ok=True)
        try:
            with target.open('xb') as stream:stream.write(raw)
        except FileExistsError:
            if file_hash(target)!=sha:raise ValueError('历史归档已损坏，未覆盖：'+sha)
        item=dict(sha256=sha,bytes=len(raw))
        if file.suffix.lower() in {'.json','.snbt','.md','.txt','.py'} and len(raw)<=2*1024*1024:
            try:item['text']=raw.decode('utf-8-sig')
            except UnicodeError:pass
        return item
    def lookup(self,state,identifier):
        if not isinstance(identifier,str) or not IDENTIFIER.fullmatch(identifier) or identifier not in state['versions']:raise ValueError('建筑版本不存在，请刷新版本历史')
        return state['versions'][identifier]
    def snapshot(self,state,request):
        source=model_file(self.workspace,request.get('source'));paths=project_paths(source);version=paths['version'];workdir=paths['workdir']
        if version==self.workspace/'nbt_models':raise ValueError('请把建筑主模型放入独立的建筑版本目录')
        if not source.is_file():raise ValueError('主模型文件不存在')
        from nbt_refine import read_master
        model,_=read_master(source);source_sha=file_hash(source);source_path=relative(self.workspace,source)
        identifier='v_'+digest((source_path+'\n'+source_sha).encode())[:24];previous=state['versions'].get(identifier)
        building=digest(relative(self.workspace,workdir).encode())[:24]
        parent=request.get('parent')
        if parent:
            if not isinstance(parent,str):raise ValueError('父版本编号无效')
            parent_node=self.lookup(state,parent)
            if parent_node['building']!=building or parent==identifier:raise ValueError('父版本必须属于同一建筑且不能是当前版本')
        if previous:
            if parent and parent!=previous.get('parent'):raise ValueError('已有版本的父子关系不重写')
            parent=previous.get('parent')
        actor=request.get('actor',previous.get('actor') if previous else 'import')
        if actor not in {'human','internal_ai','external_agent','import'}:raise ValueError('版本来源无效')
        message=request.get('message',previous.get('message') if previous else '登记已有建筑版本')
        if not isinstance(message,str) or not 1<=len(message.strip())<=4000:raise ValueError('修改说明须为1～4000字')
        tasks=request.get('tasks',previous.get('tasks',[]) if previous else [])
        if not isinstance(tasks,list) or len(tasks)>128 or any(not isinstance(t,str) or not 1<=len(t)<=160 for t in tasks):raise ValueError('关联任务编号无效')
        files={};total=0
        for directory,dirs,names in os.walk(version,followlinks=False):
            dirs[:]=sorted(d for d in dirs if d not in SKIP|{'versions','提示词方案'} and not (Path(directory)/d).is_symlink())
            for name in sorted(names):
                file=Path(directory)/name
                if file.suffix.lower() not in EXTENSIONS or name in PRIVATE or name.startswith('.env') or file.is_symlink():continue
                if not file.resolve().is_relative_to(version):raise ValueError('建筑文件越出版本目录')
                total+=file.stat().st_size
                if len(files)>=10000 or total>2*1024*1024*1024:raise ValueError('单个版本超过归档限制（10000文件/2GiB）')
                files[safe_name(file.relative_to(version).as_posix())]=self.archive(file)
        source_relative=source.relative_to(version).as_posix()
        if source_relative not in files or file_hash(source)!=source_sha:raise ValueError('归档期间主模型已变化，未登记')
        comments=[]
        index=version/'修改意见/评论索引.json'
        if index.is_file():
            for record in json.loads(index.read_text(encoding='utf8')).get('records',[]):
                for note in record.get('notes',[]):comments.append(dict(id=str(note.get('id','')),source_sha256=record.get('source_sha256'),status=note.get('status')))
        contexts={}
        from nbt_prompts import load_index
        for index_file in dict.fromkeys([workdir/'提示词方案/提示词索引.json',version/'提示词方案/提示词索引.json']):
            if not index_file.is_file():continue
            _,prompts=load_index(self.workspace,index_file);contexts[relative(self.workspace,index_file)]=self.archive(index_file)
            for prompt in prompts['records']:
                for item in prompt['files'].values():
                    file=model_file(self.workspace,index_file.parent/item['path'])
                    if not file.is_relative_to(index_file.parent) or file_hash(file)!=item['sha256']:raise ValueError('关联提示词已变化，请重新保存后再登记版本')
                    contexts[relative(self.workspace,file)]=self.archive(file)
        origin_actor=previous['actor'] if previous else actor
        node=dict(id=identifier,building=building,source=source_path,version=relative(self.workspace,version),workdir=relative(self.workspace,workdir),source_file=source_relative,source_sha256=source_sha,geometry_sha256=model.fingerprint(),size=list(model.size),parent=parent,actor=origin_actor,message=message.strip(),tasks=tasks,comments=comments,files=files,context=contexts,created_at=previous['created_at'] if previous else now(),acceptance=previous.get('acceptance') if previous else 'pending_user_review' if origin_actor=='external_agent' else 'not_granted_by_history')
        release=self.workspace/'nbt_models/_exports'/version.relative_to(self.workspace/'nbt_models')/'release.json'
        if release.is_file():
            metadata=json.loads(release.read_text(encoding='utf8'))
            if metadata.get('status')=='finalized' and metadata.get('source_sha256')==source_sha:node['release']=dict(directory=relative(self.workspace,release.parent),manifest_sha256=file_hash(release),master=metadata.get('master_relative'),geometry_sha256=metadata.get('geometry_sha256'))
        if previous and {k:v for k,v in previous.items() if k!='updated_at'}==node:return previous,False
        node['updated_at']=now();state['versions'][identifier]=node;return node,True
    def summary(self,node,verify=True):
        source=model_file(self.workspace,node['source']);exists=source.is_file()
        return {k:node.get(k) for k in ['id','building','source','version','source_sha256','geometry_sha256','size','parent','actor','message','tasks','comments','created_at','updated_at','acceptance','release']}|dict(absolute_source=str(source),format=source.suffix.lower().lstrip('.'),file_count=len(node['files']),bytes=sum(item['bytes'] for item in node['files'].values()),source_exists=exists,source_matches=(exists and file_hash(source)==node['source_sha256']) if verify else None)
    def record(self,request):
        if 'set_current' in request and type(request['set_current']) is not bool:raise ValueError('当前工作版选项须为布尔值')
        with self.lock():
            state,head=self.state();before=encode(state)
            if request.get('parent_source'):
                parent,_=self.snapshot(state,dict(source=request['parent_source']));request=dict(request,parent=parent['id'])
            node,changed=self.snapshot(state,request)
            if request.get('set_current',False):state['current'][node['building']]=node['id']
            commit=self.commit(state,head,'版本记录：'+node['message']) if encode(state)!=before else head
            return dict(version=self.summary(node),commit=commit,unchanged=commit==head,current=state['current'].get(node['building']))
    def list(self,source=None):
        state,head=self.state();building=None
        if source:building=digest(relative(self.workspace,project_paths(model_file(self.workspace,source))['workdir']).encode())[:24]
        versions=[self.summary(node,verify=bool(source)) for node in state['versions'].values() if building is None or node['building']==building]
        return dict(versions=sorted(versions,key=lambda item:item['created_at'],reverse=True),current=state['current'],commit=head,git_available=True,repository=relative(self.workspace,self.repository),approval='not_granted_by_history')
    def get(self,identifier):
        state,head=self.state();node=self.lookup(state,identifier)
        for name,item in [*node['files'].items(),*node.get('context',{}).items()]:
            safe_name(name);file=self.object_file(item['sha256'])
            if not file.is_file() or file.stat().st_size!=item['bytes'] or file_hash(file)!=item['sha256']:raise ValueError('历史文件缺失或已损坏：'+name)
        return dict(version=self.summary(node),manifest=node,commit=head)
    def current(self,identifier):
        with self.lock():
            state,head=self.state();node=self.lookup(state,identifier);summary=self.summary(node)
            if not summary['source_matches']:raise ValueError('该版本文件缺失或已变化，可从历史归档另存恢复')
            if state['current'].get(node['building'])==identifier:return dict(current=identifier,commit=head,unchanged=True)
            state['current'][node['building']]=identifier;return dict(current=identifier,commit=self.commit(state,head,'设为当前工作版：'+node['version']))
    def derive(self,identifier,message='从历史版本继续编辑'):
        with self.lock():
            state,head=self.state();node=self.lookup(state,identifier)
            # Verify every archived byte before allocating a new version.
            for name,item in [*node['files'].items(),*node.get('context',{}).items()]:
                safe_name(name);file=self.object_file(item['sha256'])
                if not file.is_file() or file.stat().st_size!=item['bytes'] or file_hash(file)!=item['sha256']:raise ValueError('历史归档缺失或已变化：'+name)
            source=model_file(self.workspace,node['source']);_,target=reserve_version(source)
            for name,item in node['files'].items():
                if PurePosixPath(name).parts[0] in {'修改意见','Agent交接','提示词方案'} or name=='conversion.json':continue
                output=owned(target,target/safe_name(name));output.parent.mkdir(parents=True,exist_ok=True)
                with output.open('xb') as stream:stream.write(self.object_file(item['sha256']).read_bytes())
            derived=target/safe_name(node['source_file'])
            from nbt_refine import read_master
            if read_master(derived)[0].fingerprint()!=node['geometry_sha256']:raise ValueError('恢复的主模型回读不一致')
            if derived.suffix.lower()!='.snbt':
                from nbt_snbt import save_snbt
                model,walls=read_master(derived);derived=target/'master/model.snbt';save_snbt(derived,model,walls)
            description=target/'room_description.json'
            if description.is_file():
                from nbt_library import register_building
                meta=json.loads(description.read_text(encoding='utf8'))
                if meta.get('name_zh'):register_building(derived,meta['name_zh'],meta.get('cells'),mode=meta.get('mode') if meta.get('mode') in {'standalone','saodg'} else None)
            new,_=self.snapshot(state,dict(source=str(derived),parent=identifier,message=message,actor='human',tasks=[]));state['current'][node['building']]=new['id']
            return dict(source=str(derived),version=self.summary(new),commit=self.commit(state,head,'派生版本：'+message),parent=identifier,source_unchanged=True,approval='not_granted_by_history')

def dispatch(workspace,action,request):
    history=History(workspace)
    if action=='list':return history.list(request.get('source'))
    if action=='get':return history.get(request['id'])
    if action=='record':return history.record(request)
    if action=='current':return history.current(request['id'])
    if action=='derive':return history.derive(request['id'],request.get('message','从历史版本继续编辑'))
    if action=='finalize':
        node=history.get(request['id'])['version']
        if not node['source_matches']:raise ValueError('制作源已变化；请先从该历史版本另存恢复后再定稿')
        from nbt_finalize import finalize
        return finalize(history.workspace,node['absolute_source'])
    raise ValueError('未知版本历史操作')

def record_produced_version(workspace,source,parent=None,message='保存建筑新版本',actor='human',tasks=None,set_current=False):
    try:return dispatch(workspace,'record',dict(source=str(source),**({'parent_source':str(parent)} if parent else {}),message=message,actor=actor,tasks=tasks or [],set_current=set_current))
    except (ValueError,OSError,subprocess.SubprocessError) as error:return dict(recorded=False,error=str(error))

def source_workspace(source):
    for parent in Path(source).resolve().parents:
        if parent.name=='nbt_models':return parent.parent
    raise ValueError('主模型不在工作区 nbt_models 中')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('action',choices=['list','get','record','current','derive','finalize']);parser.add_argument('--request',type=Path);parser.add_argument('--source');parser.add_argument('--parent');parser.add_argument('--id');parser.add_argument('--message');parser.add_argument('--actor',choices=['human','internal_ai','external_agent','import']);parser.add_argument('--set-current',action='store_true');args=parser.parse_args()
    try:
        request=json.loads(args.request.read_text(encoding='utf-8-sig')) if args.request else {}
        for key in ('source','parent','id','message','actor'):
            if getattr(args,key) is not None:request[key]=getattr(args,key)
        if args.set_current:request['set_current']=True
        print(json.dumps(dispatch(args.workspace,args.action,request),ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as error:print(json.dumps(dict(error=str(error)),ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
