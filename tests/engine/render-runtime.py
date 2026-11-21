"""Shared render dependencies: no per-workspace node_modules or ambient app env."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / '.agents/skills/minecraft-nbt-modeler'
sys.path.insert(0, str(ENGINE / 'scripts'))
from nbt_render_runtime import render_environment
from nbt_exposure import apply
from nbt_assembly import Volume
from nbt_refine import save_master
from nbt_task import inspect_source, checked_preview_snapshot


class RenderRuntime(unittest.TestCase):
    def test_preview_snapshot_checks_raw_geometry_display_states_and_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);source=folder/'source.master.json.gz'
            model=Volume((8,8,8));model.box((0,0,0),(7,0,7),'stone_bricks')
            save_master(source,model,set())
            data=inspect_source(source)
            data.update(preview_only=True,master_blocks=[[list(p),value] for p,value in sorted(model.blocks.items())])
            snapshot=folder/'after.json';snapshot.write_text(json.dumps(data),encoding='utf8')
            self.assertEqual(checked_preview_snapshot(snapshot)[0],source.resolve())
            altered=json.loads(json.dumps(data));altered['blocks'][0][1]='minecraft:gold_block'
            snapshot.write_text(json.dumps(altered),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'display states'):checked_preview_snapshot(snapshot)
            altered=json.loads(json.dumps(data));altered['master_blocks'][0][1]='minecraft:gold_block'
            snapshot.write_text(json.dumps(altered),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'fingerprint'):checked_preview_snapshot(snapshot)
            snapshot.write_text(json.dumps(data),encoding='utf8');source.write_bytes(source.read_bytes()+b'changed')
            with self.assertRaisesRegex(ValueError,'source or wall mask has changed'):checked_preview_snapshot(snapshot)

    def fixture(self, root):
        engine = root / 'workspace/.nbtcreator/runtimes/test'
        viewer = engine / 'assets/viewer'
        viewer.mkdir(parents=True)
        (viewer / 'package.json').write_text(json.dumps({'dependencies': {'playwright': '1.64.1'}}))
        package = root / 'app/modules/playwright/package.json'
        package.parent.mkdir(parents=True)
        package.write_text(json.dumps({'name': 'playwright', 'version': '1.64.1'}))
        binding = root / 'workspace/.nbtcreator/render-runtime.json'
        binding.write_text(json.dumps({'schema_version': 1, 'playwright_package': '../../app/modules/playwright/package.json'}))
        return engine, package, binding

    def test_relative_binding_survives_moving_app_and_workspace_together(self):
        with tempfile.TemporaryDirectory() as temporary:
            before = Path(temporary) / 'before'
            engine, package, _ = self.fixture(before)
            after = Path(temporary) / 'after'
            before.rename(after)
            env = render_environment(after / engine.relative_to(before), {})
            self.assertEqual(Path(env['NBTCREATOR_PLAYWRIGHT_MODULE']), (after / package.parent.relative_to(before)).resolve())

    def test_missing_and_mismatched_shared_dependency_refuse_before_render(self):
        with tempfile.TemporaryDirectory() as temporary:
            engine, package, _ = self.fixture(Path(temporary))
            package.write_text(json.dumps({'name': 'playwright', 'version': '0.0.0'}))
            with self.assertRaisesRegex(RuntimeError, 'requires Playwright 1.64.1'):
                render_environment(engine, {})
            package.unlink()
            with self.assertRaisesRegex(RuntimeError, 'Re-sync Skill exposure'):
                render_environment(engine, {})

    def test_synced_facade_renders_using_shared_install_without_ambient_settings(self):
        # This integration requires the repository's pinned viewer install/browser.
        with tempfile.TemporaryDirectory(prefix='render-contract-', dir=ROOT / 'build') as temporary:
            folder = Path(temporary)
            workspace = folder / 'workspace'
            apply(workspace)
            runtime = next((workspace / '.nbtcreator/runtimes').iterdir())
            self.assertFalse((runtime / 'assets/viewer/node_modules').exists())
            self.assertTrue((runtime / 'assets/viewer/package-lock.json').is_file())
            source = folder / 'tiny.master.json.gz'
            model = Volume((8, 8, 8))
            model.box((0, 0, 0), (7, 1, 7), 'stone_bricks')
            save_master(source, model, set())
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            cameras = folder / 'cameras.json'
            cameras.write_text(json.dumps([dict(id='whole', eye=[15, 13, 15], target=[4, 1, 4])]))
            env = {key: value for key, value in os.environ.items() if not key.startswith('NBTCREATOR_')}
            env['PYTHONUTF8'] = '1'
            cli=[sys.executable,str(workspace/'.agents/skills/nbtcreator-workspace/nbt.py')]
            runtime_info=json.loads(subprocess.check_output([*cli,'paths','--runtime'],cwd=workspace,env=env,encoding='utf8',timeout=30))
            self.assertEqual(runtime_info['active_python'],runtime_info['synced']['python'])
            self.assertEqual(runtime_info['runtime_bundle_sha256'],runtime_info['synced']['bundle_sha256'])
            self.assertTrue(runtime_info['render']['ready'],runtime_info['issues'])
            # A common-parent rename preserves relative paths. Changing the
            # depth of the workspace independently invalidates the old binding.
            cache=next(p.parent for p in Path(runtime_info['render']['browser']).parents if p.name.startswith('chromium-'))
            moved=folder/'elsewhere/deeper/project'
            moved.parent.mkdir(parents=True)
            workspace.rename(moved)
            workspace=moved
            cli=[sys.executable,str(workspace/'.agents/skills/nbtcreator-workspace/nbt.py')]
            env.pop('PLAYWRIGHT_BROWSERS_PATH',None)
            def status(*options):
                run=subprocess.run([*cli,'paths','--runtime',*map(str,options)],cwd=workspace,env=env,
                                   encoding='utf8',capture_output=True,timeout=40)
                result=json.loads(run.stdout)
                self.assertEqual(run.returncode,int('--rebind' in options and not result['rebound']),run.stderr)
                return result
            broken=status()
            self.assertFalse(broken['render']['ready'])
            self.assertIn('--trusted-install',broken['actions'][0])
            install=folder/'trusted'
            install.mkdir()
            shutil.copy(ROOT/'package.json',install/'package.json')
            viewer=install/'.agents/skills/minecraft-nbt-modeler/assets/viewer'
            viewer.mkdir(parents=True)
            original=ENGINE/'assets/viewer'
            shutil.copy(original/'package-lock.json',viewer/'package-lock.json')
            for name in ('playwright','playwright-core'):
                shutil.copytree(original/'node_modules'/name,viewer/'node_modules'/name)
            binding=workspace/'.nbtcreator/render-runtime.json'
            binding.write_bytes(b'{truncated')
            self.assertFalse(status()['render']['ready'])
            def recover(*options):
                return status('--trusted-install',install,'--browser-cache',cache,*options)
            core=viewer/'node_modules/playwright-core/package.json'
            contents=core.read_bytes()
            core.write_text(json.dumps(dict(json.loads(contents),version='0.0.1')),encoding='utf8')
            wrong=recover('--rebind')
            self.assertFalse(wrong['rebound']);self.assertIn('Playwright Core',str(wrong['issues']))
            self.assertEqual(binding.read_bytes(),b'{truncated')
            core.write_bytes(contents)
            # Read-only status must not run a program named in a damaged registry.
            original_binding=dict(schema_version=1,playwright_package=str(viewer/'node_modules/playwright/package.json'),
                                  node=sys.executable,browser=runtime_info['render']['browser'])
            binding.write_text(json.dumps(original_binding),encoding='utf8')
            static=status()
            self.assertFalse(static['render']['ready'])
            self.assertIn('Node',str(static['issues']))
            binding.write_bytes(b'{truncated')
            synchronized=workspace/'.nbtcreator/engine-runtime.json'
            original_sync=synchronized.read_bytes()
            data=json.loads(original_sync);data['python']['version']='0.0.1'
            synchronized.write_text(json.dumps(data),encoding='utf8')
            self.assertFalse(recover('--rebind')['rebound'])
            self.assertEqual(binding.read_bytes(),b'{truncated')
            synchronized.write_bytes(original_sync)
            registry=viewer/'node_modules/playwright-core/browsers.json'
            original_registry=registry.read_bytes()
            data=json.loads(original_registry)
            next(b for b in data['browsers'] if b['name']=='chromium')['browserVersion']='0.0.1'
            registry.write_text(json.dumps(data),encoding='utf8')
            self.assertIn('registry version',str(recover('--rebind')['issues']))
            synchronized.write_text(json.dumps(dict(json.loads(original_sync),chromium='0.0.1')),encoding='utf8')
            self.assertIn('requires Chromium 0.0.1',str(recover('--rebind')['issues']))
            synchronized.write_bytes(original_sync)
            self.assertEqual(binding.read_bytes(),b'{truncated')
            registry.write_bytes(original_registry)
            checked=recover()
            self.assertTrue(checked['render']['ready'],checked['issues'])
            self.assertFalse(checked['rebound'])
            self.assertEqual(binding.read_bytes(),b'{truncated')
            self.assertTrue(recover('--rebind')['rebound'])
            # The maintained source CLI can relink a previously synchronized
            # project whose frozen entry predates the repair command/Chromium pin.
            legacy=json.loads(original_sync)
            legacy.pop('chromium')
            synchronized.write_text(json.dumps(legacy),encoding='utf8')
            installed=['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(workspace),
                       'paths','--runtime','--trusted-install',str(install),'--browser-cache',str(cache),'--rebind']
            old=json.loads(subprocess.check_output(installed,cwd=workspace,env=dict(env,NBTCREATOR_PYTHON=sys.executable),
                                                   encoding='utf8',timeout=40))
            self.assertTrue(old['rebound'],old['issues'])
            self.assertIn('target_frozen_engine',old)
            self.assertEqual(old['render']['browser_version'],runtime_info['synced']['chromium'])
            synchronized.write_bytes(original_sync)
            # Move the named installation again, keeping the project stationary.
            new_install=folder/'applications/nested/NBTCreator'
            new_install.parent.mkdir(parents=True)
            install.rename(new_install)
            install=new_install
            self.assertFalse(status()['render']['ready'])
            self.assertTrue(recover('--rebind')['rebound'])
            if os.name=='nt':self.assertTrue(status('--browser-cache',cache,'--rebind')['rebound'])
            restored=status()
            self.assertTrue(restored['render']['ready'],restored['issues'])
            self.assertEqual(restored['render']['expected_chromium'],runtime_info['synced']['chromium'])
            if os.name=='nt':
                pin=json.loads((ROOT/'package.json').read_text(encoding='utf8'))['devDependencies']['electron']
                def electron_version(value):
                    synchronized.write_text(json.dumps(dict(json.loads(original_sync),electron=value)),encoding='utf8')
                    return status('--trusted-install',ROOT,'--browser-cache',cache,'--rebind')
                before_binding=binding.read_bytes()
                self.assertFalse(electron_version('0.0.1')['rebound'])
                self.assertEqual(binding.read_bytes(),before_binding)
                from_electron=electron_version(pin)
                self.assertTrue(from_electron['rebound'],from_electron['issues'])
                self.assertEqual(from_electron['render']['electron'],pin)
            result = subprocess.run([sys.executable, str(workspace / '.agents/skills/nbtcreator-workspace/nbt.py'),
                                     'render', '--source', str(source), '--cameras', str(cameras),
                                     '--output', str(folder / 'rendered'), '--width', '320', '--height', '240'],
                                    cwd=workspace, env=env, capture_output=True, text=True, encoding='utf8', timeout=90000)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads((folder / 'rendered/render_manifest.json').read_text(encoding='utf8'))
            self.assertEqual(manifest['status'], 'complete')
            self.assertEqual(manifest['browser_version'],runtime_info['synced']['chromium'])
            self.assertEqual(len(manifest['images']), 1)
            image=folder/'rendered'/manifest['images'][0]['image']
            self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(),manifest['images'][0]['sha256'])
            self.assertTrue(all(manifest['cleanup'].values()))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)


if __name__ == '__main__':
    (ROOT / 'build').mkdir(exist_ok=True)
    unittest.main(verbosity=2)
