"""Resolve optional shared rendering dependencies without copying them per workspace."""
import json
import os
from pathlib import Path
import shutil


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
    if node:
        data.update(node=_relative(Path(node).resolve(), folder),
                    node_is_electron=os.environ.get('NBTCREATOR_NODE_IS_ELECTRON') == '1')
    browser = os.environ.get('NBTCREATOR_BROWSER')
    if browser and Path(browser).is_file():
        data['browser'] = _relative(Path(browser).resolve(), folder)
    file = folder / 'render-runtime.json'
    temporary = file.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    temporary.replace(file)


def render_environment(engine, environ=None):
    """Use local dependencies first, then a workspace's explicit app binding."""
    engine = Path(engine).resolve()
    env = dict(os.environ if environ is None else environ)
    viewer = engine / 'assets/viewer'
    expected = json.loads((viewer / 'package.json').read_text(encoding='utf8'))['dependencies']['playwright']
    binding, base = {}, None
    for parent in [engine, *engine.parents]:
        candidate = parent / '.nbtcreator/render-runtime.json'
        if candidate.is_file():
            try:
                binding = json.loads(candidate.read_text(encoding='utf8'))
                if binding.get('schema_version') != 1:
                    raise ValueError('unsupported binding version')
                base = candidate.parent
            except (ValueError, OSError) as error:
                raise RuntimeError(f'Render runtime binding is invalid: {candidate}: {error}') from error
            break

    local = viewer / 'node_modules/playwright/package.json'
    explicit = env.get('NBTCREATOR_PLAYWRIGHT_MODULE')
    if explicit:
        package = Path(explicit).resolve() / 'package.json'
    elif local.is_file():
        package = local
    elif base and binding.get('playwright_package'):
        package = (base / binding['playwright_package']).resolve()
    else:
        package = local
    if not package.is_file():
        raise RuntimeError(
            f'Playwright {expected} is unavailable. Re-sync Skill exposure from the installed NBTCreator app, '
            f'or run npm ci --prefix "{viewer}" using its included package-lock.json. '
            'A moved/uninstalled app may need to be linked again; no model files were changed.')
    actual = json.loads(package.read_text(encoding='utf8'))
    if actual.get('name') != 'playwright' or actual.get('version') != expected:
        raise RuntimeError(f'Rendering requires Playwright {expected}; found {actual.get("version")} at {package}. '
                           'Re-sync from a matching application or install the included lockfile.')
    env['NBTCREATOR_PLAYWRIGHT_MODULE'] = str(package.parent)
    if base:
        for key, name in [('node', 'NBTCREATOR_NODE'), ('browser', 'NBTCREATOR_BROWSER')]:
            if not env.get(name) and binding.get(key):
                executable = (base / binding[key]).resolve()
                if executable.is_file():
                    env[name] = str(executable)
                    if key == 'node' and binding.get('node_is_electron'):
                        env['NBTCREATOR_NODE_IS_ELECTRON'] = '1'
    if env.get('NBTCREATOR_NODE_IS_ELECTRON') == '1':
        env['ELECTRON_RUN_AS_NODE'] = '1'
    return env
