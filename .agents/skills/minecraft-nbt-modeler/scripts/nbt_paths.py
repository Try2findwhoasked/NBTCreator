"""Describe the active exposed engine for task scripts, without guessing an install path."""
import argparse
import hashlib
import json
import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import subprocess
import sys


def paths(workspace=None):
    engine = Path(__file__).resolve().parents[1]
    manifest = engine/'runtime-manifest.json'
    return dict(schema_version=1, workspace=str(Path(workspace or Path.cwd()).resolve()),
                engine=str(engine), scripts=str(engine/'scripts'), references=str(engine/'references'),
                viewer=str(engine/'assets/viewer'), python=sys.executable,
                runtime_bundle_sha256=json.loads(manifest.read_text(encoding='utf8')).get('bundle_sha256') if manifest.is_file() else None,
                commands=json.loads((engine/'tool-catalog.json').read_text(encoding='utf8'))['commands'],
                note='Read-only discovery. Import task APIs from scripts; keep generated files outside this engine.')


def python_versions():
    packages={}
    for name in ('numpy','Pillow','nbtlib'):
        try:packages[name]=version(name)
        except PackageNotFoundError:packages[name]=None
    return dict(version='.'.join(map(str,sys.version_info[:3])),packages=packages)

def registered_engine(folder,expected):
    """Locate a frozen data snapshot by the synchronized bundle and its lockfile hash."""
    bundle=expected.get('bundle_sha256')
    if not isinstance(bundle,str) or not re.fullmatch('[a-f0-9]{64}',bundle):
        raise ValueError('冻结引擎登记缺少有效摘要')
    for candidate in sorted((folder/'runtimes').glob(bundle[:16]+'*')):
        if candidate.resolve().parent!=(folder/'runtimes').resolve():continue
        file=candidate/'runtime-manifest.json'
        if not file.is_file():continue
        manifest=json.loads(file.read_text(encoding='utf8'))
        if manifest.get('bundle_sha256')!=bundle:continue
        files=[(row['path'],row['sha256']) for row in manifest['files']]
        if hashlib.sha256(json.dumps(files,separators=(',',':')).encode()).hexdigest()!=bundle:continue
        for name in ('assets/viewer/package.json','assets/viewer/package-lock.json'):
            path=candidate/name
            if (not path.resolve().is_relative_to(candidate.resolve()) or
                    hashlib.sha256(path.read_bytes()).hexdigest()!=dict(files).get(name)):
                break
        else:return candidate
    raise ValueError('无法按同步哈希找到匹配的冻结引擎和依赖锁文件')


def runtime_status(workspace,install=None,cache=None,rebind=False):
    from nbt_render_runtime import render_environment,selected_install,save_binding,probe,static_runtime,_relative,frozen_folder
    info=paths(workspace);active=python_versions();issues=[]
    implementation=Path(info['engine'])
    engine=implementation
    folder=Path(info['workspace'])/'.nbtcreator'
    binding=folder/'engine-runtime.json'
    try:expected=json.loads(binding.read_text(encoding='utf8'))
    except FileNotFoundError:expected=None
    except (ValueError,OSError):
        expected=None;issues.append('运行时登记无法读取。请从当前应用重新同步助手入口。')
    if expected is not None and (not isinstance(expected,dict) or not {'python','bundle_sha256'}<=expected.keys()):
        expected=None
        issues.append('运行时登记格式无效。请从当前应用重新同步助手入口。')
    if expected:
        if expected['python']!=active:
            issues.append('当前解释器或依赖版本与同步时不同。用所需 Python 运行同一命令并重查，或从当前应用重新同步。')
        if info['runtime_bundle_sha256'] and expected['bundle_sha256']!=info['runtime_bundle_sha256']:
            issues.append('当前冻结引擎与同步记录不同。请通过当前工作区生成的入口运行。')
    if any(value is None for value in active['packages'].values()):
        issues.append('当前解释器缺少建模依赖。用该解释器安装共享引擎 requirements.txt 后再验证。')
    render=dict(ready=False);rebound=False;hints={};selection=None
    file=folder/'render-runtime.json'
    previous=None
    try:
        previous=file.read_bytes() if file.is_file() else None
        old=json.loads(previous or b'{}')
        if not isinstance(old,dict):old={}
    except (ValueError,OSError):
        old={}
    for key in ('install_hint','python_hint'):
        path=old.get(key)
        if isinstance(path,str) and Path(path).is_absolute() and not path.startswith(('\\\\','//')):
            hints[key]=dict(path=path,exists=Path(path).exists())
    try:
        if issues:raise ValueError('请核对同步登记和 Python 环境后重试')
        if expected and not frozen_folder(engine):
            engine=registered_engine(folder,expected)
            info['target_frozen_engine']=str(engine)
        if frozen_folder(engine) and (folder!=frozen_folder(engine) or not expected):
            raise ValueError('请从该冻结引擎所属的工作区根目录核对运行时')
        if install or cache or rebind:
            if folder!=frozen_folder(engine) or not expected or issues:
                raise ValueError('恢复须通过该工作区的冻结入口及匹配的 Python 运行。请先核对同步登记')
            if install:
                selection=selected_install(install,folder,expected,engine,cache)
            elif cache and old.get('schema_version')==1 and old.get('playwright_package') and old.get('node'):
                if not Path(cache).is_dir():raise ValueError('所选 Chromium 缓存目录不存在')
                selection=dict(old,browser_cache=_relative(Path(cache).resolve(),folder))
                selection.pop('browser',None)
            else:raise ValueError('请显式给出 --trusted-install；原安装仍有效时也可仅给出 --browser-cache')
        env=render_environment(engine,selection=selection)
        # Never execute an executable or JavaScript module named by a workspace
        # binding during ordinary discovery. Only an explicitly trusted install
        # is probed with the running entry's own renderer helper.
        render=probe(implementation,env) if install else static_runtime(env)
        if rebind:
            if not install and not render.get('browser_version'):
                raise ValueError('本平台不能静态读取浏览器实际版本，请用 --trusted-install 验证后重新绑定')
            from nbt_knowledge.libraries import write_lock,inside
            with write_lock(inside(folder.parent,folder/'exposure-lock')):
                if ((file.read_bytes() if file.is_file() else None)!=previous or
                        json.loads(binding.read_text(encoding='utf8'))!=expected):
                    raise ValueError('探测期间运行时登记已变化，请重新检查')
                selection['browser']=_relative(Path(render['browser']).resolve(),folder)
                if install:selection['node_version']=render['node_version']
                save_binding(folder,selection);rebound=True
    except (RuntimeError,ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as failure:
        issues.append(str(failure))
    actions=['paths --runtime --trusted-install <已知可信的应用目录> [--browser-cache <本机缓存目录>]',
             '在同一命令加 --rebind，以探测通过的依赖替换本工作区出图关联。']
    return dict(info,active_python=active,synced=expected,render=render,issues=issues,hints=hints,actions=actions,rebound=rebound)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    parser.add_argument('--runtime',action='store_true',help='核对当前 Python、同步版本与真实渲染依赖路径')
    parser.add_argument('--trusted-install',type=Path,help='显式选择已知可信的 NBTCreator Portable 根或源码安装目录')
    parser.add_argument('--browser-cache',type=Path,help='使用所选本地 Playwright 浏览器缓存，不下载')
    parser.add_argument('--rebind',action='store_true',help='验证通过后更新当前冻结工作区的出图关联')
    args = parser.parse_args()
    if (args.trusted_install or args.browser_cache or args.rebind) and not args.runtime:
        parser.error('安装探测和重新绑定须配合 --runtime')
    result=runtime_status(args.workspace,args.trusted_install,args.browser_cache,args.rebind) if args.runtime else paths(args.workspace)
    print(json.dumps(result,ensure_ascii=False))
    if args.rebind and not result['rebound']:raise SystemExit(1)
