"""Describe the active exposed engine for task scripts, without guessing an install path."""
import argparse
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import shutil
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


def runtime_status(workspace):
    from nbt_render_runtime import render_environment
    info=paths(workspace);active=python_versions();issues=[]
    binding=Path(info['workspace'])/'.nbtcreator/engine-runtime.json'
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
    render=dict(ready=False)
    try:
        engine=Path(info['engine']);env=render_environment(engine)
        node=env.get('NBTCREATOR_NODE') or shutil.which('node')
        if not node:raise RuntimeError('找不到 Node 或同步绑定的 Electron。请重新同步或准备 Node。')
        script=engine/'assets/viewer/browser-launch.mjs'
        probe=("import {resolveRenderBrowser} from "+json.dumps(script.as_uri())+
               "; console.log(JSON.stringify({browser:await resolveRenderBrowser(),electron:process.versions.electron??null}))")
        run=subprocess.run([node,'--input-type=module','-e',probe],env=env,encoding='utf8',capture_output=True,timeout=10,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if run.returncode:raise RuntimeError('无法找到可用 Chromium。请重新同步应用，或为当前 Playwright 安装 Chromium。')
        browser=json.loads(run.stdout)
        if expected and expected.get('electron') and browser['electron'] and browser['electron']!=expected['electron']:
            issues.append('用于出图的 Electron 版本与同步记录不同。请从当前应用重新同步。')
        render=dict(ready=True,node=node,playwright=env['NBTCREATOR_PLAYWRIGHT_MODULE'],**browser,
                    checked='executable_present; run render to verify launch and actual images')
    except (RuntimeError,ValueError,OSError,subprocess.SubprocessError) as failure:
        issues.append(str(failure))
    return dict(info,active_python=active,synced=expected,render=render,issues=issues)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    parser.add_argument('--runtime',action='store_true',help='核对当前 Python、同步版本与真实渲染依赖路径')
    args = parser.parse_args()
    print(json.dumps(runtime_status(args.workspace) if args.runtime else paths(args.workspace), ensure_ascii=False))
