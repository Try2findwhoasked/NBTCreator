"""Shared render dependencies: no per-workspace node_modules or ambient app env."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
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
            with self.assertRaisesRegex(ValueError,'source has changed'):checked_preview_snapshot(snapshot)

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
            result = subprocess.run([sys.executable, str(workspace / '.agents/skills/nbtcreator-workspace/nbt.py'),
                                     'render', '--source', str(source), '--cameras', str(cameras),
                                     '--output', str(folder / 'rendered'), '--width', '320', '--height', '240'],
                                    cwd=workspace, env=env, capture_output=True, text=True, encoding='utf8', timeout=90000)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads((folder / 'rendered/render_manifest.json').read_text(encoding='utf8'))
            self.assertEqual(manifest['status'], 'complete')
            self.assertEqual(len(manifest['images']), 1)
            self.assertTrue(all(manifest['cleanup'].values()))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)


if __name__ == '__main__':
    (ROOT / 'build').mkdir(exist_ok=True)
    unittest.main(verbosity=2)
