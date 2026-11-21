"""Resolve optional shared rendering dependencies without copying them per workspace."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def _relative(file, folder):
    try:
        return os.path.relpath(file, folder).replace('\\', '/')
    except ValueError:  # Different Windows drives cannot have a relative path.
        return str(file)


def write_render_binding(workspace, engine):
    """Bind installed app dependencies; model/runtime source remains workspace-local."""
    engine, workspace = Path(engine).resolve(), Path(workspace).resolve()
    package = engine / 'assets/viewer/node_modules/playwright/package.json'
    if not package.is_file():
        return  # Standalone sources can install their own locked viewer dependencies.
    folder = workspace / '.nbtcreator'
    folder.mkdir(parents=True, exist_ok=True)
    node = shutil.which(os.environ.get('NBTCREATOR_NODE', 'node'))
    data = dict(schema_version=1, playwright_package=_relative(package, folder))
    data['python_hint']=sys.executable
    if engine.parent.name=='skills' and engine.parent.parent.name=='.agents':
        app=engine.parents[2]
        install=app.parents[1] if app.name=='app' and app.parent.name=='resources' else app
        data['install_hint']=str(install)
    if node:
        data.update(node=_relative(Path(node).resolve(), folder),
                    node_is_electron=os.environ.get('NBTCREATOR_NODE_IS_ELECTRON') == '1')
    browser = os.environ.get('NBTCREATOR_BROWSER')
    if browser and Path(browser).is_file():
        data['browser'] = _relative(Path(browser).resolve(), folder)
    cache=os.environ.get('PLAYWRIGHT_BROWSERS_PATH')
    if cache and Path(cache).is_absolute() and Path(cache).is_dir():
        data['browser_cache']=_relative(Path(cache).resolve(),folder)
    elif not browser:
        # A later knowledge sync can update the installation without dropping
        # a locally selected browser cache. The renderer rechecks its version.
        try:prior=json.loads((folder/'render-runtime.json').read_text(encoding='utf8'))
        except (ValueError,OSError):prior=None
        if isinstance(prior,dict) and isinstance(prior.get('browser_cache'),str):
            data['browser_cache']=prior['browser_cache']
    save_binding(folder,data)

def save_binding(folder,data):
    from nbt_asset_libraries import atomic
    atomic(folder/'render-runtime.json',(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf8'))

def synced_browser_version(engine):
    file=engine/'assets/viewer/node_modules/playwright-core/browsers.json'
    try:
        rows=json.loads(file.read_text(encoding='utf8'))['browsers']
        return next(row['browserVersion'] for row in rows if row['name']=='chromium')
    except (OSError,ValueError,KeyError,TypeError,StopIteration):
        # A standalone model-only installation can still expose the engine.
        return None

def frozen_folder(engine):
    runtime_dir=engine.parent
    if runtime_dir.name=='runtimes' and runtime_dir.parent.name=='.nbtcreator':
        return runtime_dir.parent
    return None


def check_lock(engine,viewer):
    expected=json.loads((engine/'assets/viewer/package-lock.json').read_text(encoding='utf8'))['packages']
    actual=json.loads((viewer/'package-lock.json').read_text(encoding='utf8'))['packages']
    for name in ('playwright','playwright-core'):
        key='node_modules/'+name
        if (not expected[key].get('integrity') or
                any(expected[key][field]!=actual[key].get(field) for field in ('version','integrity'))):
            raise ValueError(f'所选应用的 {name} 锁文件校验值与冻结引擎不同')


def selected_install(install,folder,synced,engine,cache=None):
    """Only inspect the named NBTCreator installation and standard package layout."""
    root=Path(install).resolve(strict=True)
    app=root/'resources/app' if (root/'resources/app/package.json').is_file() else root
    metadata=json.loads((app/'package.json').read_text(encoding='utf8'))
    if metadata.get('name')!='nbtcreator' or metadata.get('main')!='desktop/main.cjs':
        raise ValueError('所选目录不是可识别的 NBTCreator 安装或源码目录')
    viewer=app/'.agents/skills/minecraft-nbt-modeler/assets/viewer'
    module=viewer/'node_modules/playwright/package.json'
    for path in (app/'package.json',viewer/'node_modules/playwright',viewer/'node_modules/playwright-core',viewer/'package-lock.json'):
        if not path.resolve().is_relative_to(root):
            raise ValueError('所选渲染依赖越过可信安装目录')
    check_lock(engine,viewer)
    binding=dict(schema_version=1,playwright_package=_relative(module,folder),install_hint=str(root),python_hint=sys.executable)
    electron=app!=root or bool(synced.get('electron'))
    if electron:
        if app!=root:
            node=root/'NBTCreator.exe'
        else:
            node=app/'node_modules/electron/dist/electron.exe'
        pinned=metadata.get('devDependencies',{}).get('electron')
        if synced.get('electron') and pinned!=synced['electron']:
            raise ValueError(f'所选应用的 Electron {pinned} 与同步版本 {synced["electron"]} 不符')
        if not pinned:raise ValueError('所选应用缺少 Electron 版本登记')
        binding['electron_version']=pinned
    else:
        executable=shutil.which('node')
        if not executable:raise ValueError('当前项目环境缺少 Node，请用原 mise 环境运行')
        node=Path(executable)
    if not node.is_file():raise ValueError(f'所选应用缺少渲染执行文件：{node}')
    if electron and not node.resolve().is_relative_to(root):raise ValueError('Electron 越过可信安装目录')
    binding.update(node=_relative(node.resolve(),folder),node_is_electron=electron)
    browser=app/'runtime/browser/chrome.exe'
    if cache is not None:
        if not Path(cache).is_dir():raise ValueError('所选 Chromium 缓存目录不存在')
        binding['browser_cache']=_relative(Path(cache).resolve(),folder)
    elif browser.is_file():
        if not browser.resolve().is_relative_to(root):raise ValueError('便携浏览器越过可信安装目录')
        binding['browser']=_relative(browser.resolve(),folder)
    return binding


def render_environment(engine, environ=None, *, selection=None):
    """Use local dependencies first, then a workspace's explicit app binding."""
    engine = Path(engine).resolve()
    env = dict(os.environ if environ is None else environ)
    viewer = engine / 'assets/viewer'
    expected = json.loads((viewer / 'package.json').read_text(encoding='utf8'))['dependencies']['playwright']
    binding, base = {}, frozen_folder(engine)
    if selection is not None:
        if not base:raise ValueError('请通过创作工作区的冻结入口检查或恢复安装关联')
        binding=selection
        # An explicit recovery must prove the offered files, including when
        # a stale application or cache is still present in the calling shell.
        for key in ('NBTCREATOR_NODE','NBTCREATOR_NODE_IS_ELECTRON','NBTCREATOR_PLAYWRIGHT_MODULE',
                    'NBTCREATOR_BROWSER','ELECTRON_RUN_AS_NODE'):
            env.pop(key,None)
    elif base and (candidate:=base/'render-runtime.json').is_file():
        try:
            binding=json.loads(candidate.read_text(encoding='utf8'))
            if not isinstance(binding,dict) or binding.get('schema_version')!=1:raise ValueError('unsupported binding')
        except (ValueError,OSError) as error:
            raise RuntimeError(f'Render runtime binding is invalid: {candidate}: {error}') from error
    frozen=base and (engine/'runtime-manifest.json').is_file()
    synced={}
    if frozen:
        from nbt_paths import python_versions
        synced=json.loads((base/'engine-runtime.json').read_text(encoding='utf8'))
        stamp=json.loads((engine/'runtime-manifest.json').read_text(encoding='utf8'))
        if not isinstance(synced,dict) or synced.get('bundle_sha256')!=stamp.get('bundle_sha256'):
            raise ValueError('当前冻结引擎与同步登记不同，请使用工作区的当前入口')
        if python_versions()!=synced.get('python'):
            raise ValueError('当前 Python 或依赖与同步版本不同。请用 paths --runtime 列出的匹配解释器运行同一入口')
        env.update(NBTCREATOR_PINNED_RENDER='1',NBTCREATOR_PLAYWRIGHT_VERSION=expected)
        if synced.get('chromium'):env['NBTCREATOR_RENDER_CHROMIUM']=synced['chromium']

    local = viewer / 'node_modules/playwright/package.json'
    explicit = env.get('NBTCREATOR_PLAYWRIGHT_MODULE')
    if explicit:
        package = Path(explicit).resolve() / 'package.json'
    elif local.is_file() and selection is None:
        package = local
    elif base and binding.get('playwright_package'):
        package = (base / binding['playwright_package']).resolve()
    else:
        package = local
    if not package.is_file():
        raise RuntimeError(
            f'Playwright {expected} is unavailable. Re-sync Skill exposure from the installed NBTCreator app, '
            f'or run npm ci --prefix "{viewer}" using its included package-lock.json. '
            'For a moved install inspect paths --runtime --trusted-install <directory>; add --rebind after checking.')
    actual = json.loads(package.read_text(encoding='utf8'))
    if not isinstance(actual,dict):raise ValueError('Playwright package.json 格式无效')
    if actual.get('name') != 'playwright' or actual.get('version') != expected:
        raise RuntimeError(f'Rendering requires Playwright {expected}; found {actual.get("version")} at {package}. '
                           'Re-sync from a matching application or install the included lockfile.')
    if frozen:
        check_lock(engine,package.parents[2])
        core=json.loads((package.parents[1]/'playwright-core/package.json').read_text(encoding='utf8'))
        if not isinstance(core,dict) or (core.get('name'),core.get('version'))!=('playwright-core',expected):
            raise ValueError(f'所选 Playwright Core 与锁定版本 {expected} 不同')
    env['NBTCREATOR_PLAYWRIGHT_MODULE'] = str(package.parent)
    if base:
        if binding.get('browser_cache'):
            env['PLAYWRIGHT_BROWSERS_PATH']=str((base/binding['browser_cache']).resolve())
        for key, name in [('node', 'NBTCREATOR_NODE'), ('browser', 'NBTCREATOR_BROWSER')]:
            if not env.get(name) and binding.get(key):
                executable = (base / binding[key]).resolve()
                if executable.is_file():
                    env[name] = str(executable)
                    if key == 'node' and binding.get('node_is_electron'):
                        env['NBTCREATOR_NODE_IS_ELECTRON'] = '1'
                else:
                    raise RuntimeError(f'Bound {key} is missing: {executable}. Inspect paths --runtime --trusted-install and --rebind.')
        if frozen:
            if binding.get('node_version'):env['NBTCREATOR_RENDER_NODE_VERSION']=binding['node_version']
            if binding.get('node_is_electron'):
                pin=synced.get('electron') or binding.get('electron_version')
                if not pin:raise ValueError('缺少用于出图的 Electron 版本，请从可信安装重新绑定')
                env['NBTCREATOR_RENDER_ELECTRON']=pin
    if env.get('NBTCREATOR_NODE_IS_ELECTRON') == '1':
        env['ELECTRON_RUN_AS_NODE'] = '1'
    return env


def probe(engine,env):
    node=env.get('NBTCREATOR_NODE') or shutil.which('node')
    if not node:raise RuntimeError('找不到 Node 或绑定的 Electron')
    module=(engine/'assets/viewer/browser-launch.mjs').as_uri()
    script='import {probeRenderRuntime} from '+json.dumps(module)+'; try { console.log(JSON.stringify(await probeRenderRuntime())) } catch(e) {console.log(JSON.stringify({error:e.message}));process.exitCode=1}'
    run=subprocess.run([node,'--input-type=module','-e',script],env=env,encoding='utf8',errors='replace',
                       capture_output=True,timeout=22,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if run.returncode:
        # Playwright can emit verbose launch and shutdown traces on stderr.
        # Keep the probe's version mismatch diagnostic in its JSON response.
        try:message=json.loads(run.stdout)['error']
        except (ValueError,KeyError,TypeError):message=run.stderr.strip()[-1200:]
        raise RuntimeError((message or '无法启动渲染执行文件')[:1200])
    return dict(ready=True,node=node,playwright=env['NBTCREATOR_PLAYWRIGHT_MODULE'],**json.loads(run.stdout),
                checked='headless launch and version; render verifies images')


def windows_version(executable):
    """Inspect the fixed PE product version without loading or executing the image."""
    import ctypes
    from ctypes import wintypes
    api=ctypes.windll.version
    file=str(executable)
    size=api.GetFileVersionInfoSizeW(file,None)
    if not 0<size<=4*1024*1024:return None
    data=ctypes.create_string_buffer(size)
    if not api.GetFileVersionInfoW(file,0,size,data):return None
    pointer=ctypes.POINTER(wintypes.DWORD)()
    length=wintypes.UINT()
    if not api.VerQueryValueW(data,'\\',ctypes.byref(pointer),ctypes.byref(length)) or length.value<52:return None
    if pointer[0]!=0xFEEF04BD:return None
    return '.'.join(str(n) for n in (pointer[4]>>16,pointer[4]&65535,pointer[5]>>16,pointer[5]&65535))


def static_runtime(env):
    """Read installation metadata and the named cache without running their programs."""
    node=Path(env.get('NBTCREATOR_NODE') or shutil.which('node') or '')
    if not node.is_file():raise ValueError('找不到已登记的 Node 或 Electron')
    if node.name.lower() not in ('node','node.exe','electron','electron.exe','nbtcreator.exe'):
        raise ValueError(f'绑定的执行文件不是可识别的 Node 或 Electron：{node}')
    module=Path(env['NBTCREATOR_PLAYWRIGHT_MODULE'])
    core=module.parent/'playwright-core'
    registry=json.loads((core/'browsers.json').read_text(encoding='utf8'))
    chromium=next((item for item in registry['browsers'] if item['name']=='chromium'),{})
    version=chromium.get('browserVersion')
    if not version or env.get('NBTCREATOR_RENDER_CHROMIUM',version)!=version:
        raise ValueError('Chromium registry version differs from the synchronized installation')
    browser=env.get('NBTCREATOR_BROWSER')
    if browser:
        executable=Path(browser)
    else:
        cache=env.get('PLAYWRIGHT_BROWSERS_PATH')
        if cache=='0':root=core/'.local-browsers'
        elif cache:root=Path(cache)
        elif os.name=='nt':root=Path(os.environ['LOCALAPPDATA'])/'ms-playwright'
        elif sys.platform=='darwin':root=Path.home()/'Library/Caches/ms-playwright'
        else:root=Path(os.environ.get('XDG_CACHE_HOME',Path.home()/'.cache'))/'ms-playwright'
        directory=root/('chromium-'+chromium['revision'])
        locations=['chrome-win64/chrome.exe','chrome-win/chrome.exe'] if os.name=='nt' else (
            ['chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',
             'chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'] if sys.platform=='darwin' else
            ['chrome-linux64/chrome','chrome-linux/chrome'])
        executable=next((directory/p for p in locations if (directory/p).is_file()),directory/locations[0])
    if not executable.is_file():raise ValueError(f'找不到匹配的 Chromium {version}：{executable}')
    actual=windows_version(executable) if os.name=='nt' else None
    if os.name=='nt' and actual!=version:raise ValueError(f'Chromium 实际文件版本 {actual} 与锁定版本 {version} 不符')
    node_pin=env.get('NBTCREATOR_RENDER_ELECTRON') or env.get('NBTCREATOR_RENDER_NODE_VERSION')
    exe_version=windows_version(node) if os.name=='nt' else None
    if os.name=='nt' and not exe_version:raise ValueError('无法读取 Node 或 Electron 可执行文件的版本')
    if os.name=='nt' and node_pin and exe_version not in (node_pin,node_pin+'.0'):
        raise ValueError(f'出图执行文件版本 {exe_version} 与绑定的 {node_pin} 不符')
    return dict(ready=True,node=str(node),executable_version=exe_version,playwright=str(module),
                playwright_version=json.loads((module/'package.json').read_text(encoding='utf8'))['version'],
                expected_chromium=version,browser=str(executable),browser_version=actual,
                checked='files and metadata only; render verifies launch and images')
