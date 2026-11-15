"""Synthetic managed assembly for real shared-renderer regression only."""
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_working_model import WorkingModel, verify_version


def main():
    workspace, output = map(Path, sys.argv[1:3])
    assembly = runpy.run_path(str(ROOT / 'tests/scene-interfaces.py'))['assembly']
    model = WorkingModel(workspace, [48, 20, 30], kind='component')
    model.apply_operations([dict(kind='box', label='合成测试地面', classification='body', lo=[0,0,0], hi=[47,0,29], state='smooth_sandstone')])
    model.install('portal', dict(tool='scene_compile', arguments=dict(graph=assembly())), [10,1,8])
    cameras = [dict(id='assembly', role='合成组合前后同机位', eye=[40,19,-15], target=[20,4,14], fov=48)]
    before = model.preview(output / 'before', cameras)
    first = model.save_draft('合成组合渲染回归')
    model.update('portal', dict(tool='scene_compile', arguments=dict(graph=assembly(7))))
    after = model.preview(output / 'after', cameras)
    second = model.save_draft()
    assert verify_version(Path(first['output']))['revision'] != verify_version(Path(second['output']))['revision']
    assert model.validate()['assembly']['passed']
    (output / 'fixture.json').write_text(json.dumps(dict(before=before, after=after, first=first, second=second)), encoding='utf8')


if __name__ == '__main__':
    main()
