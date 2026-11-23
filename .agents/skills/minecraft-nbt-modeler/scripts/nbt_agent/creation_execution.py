"""Run the same readback, validation and rendering steps for both creation modes."""

import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic
from uuid import uuid4

from nbt_agent.creation_inputs import evidence, gates
from nbt_building.workflow import dispatch
from nbt_composition.working_model import ModelConflict, WorkingModel
from nbt_project.history import file_hash
from nbt_project.prompts import inside
from nbt_project.queues import write
from nbt_review.diagnostic_delta import delta


STALE_CODES = {'STALE_SOURCE','STALE_PARENT','SOURCE_CHANGED','TASK_EVIDENCE_CHANGED','TASK_SUPERSEDED',
               'REVISION_CONFLICT','LEASE_EXPIRED','LEASE_FENCE_CONFLICT','SESSION_NOT_ACTIVE','REVIEW_CHANGED'}
SCRIPT = Path(__file__).resolve().parents[1] / 'nbt_task.py'


def read(file):
    return json.loads(file.read_text(encoding='utf8'))


def reference(path):
    return dict(path=str(path), sha256=file_hash(path))


def saved_binding(saved):
    return {key: saved[key] for key in ('source', 'source_sha256')}


class StageError(Exception):
    def __init__(self, outcome):
        self.outcome = outcome


class Execution:
    def __init__(self, workspace, directory, ensure_live):
        self.workspace, self.directory, self.ensure_live = workspace, directory, ensure_live
        self.steps = []

    def step(self, name, function, *, design=False, diagnostic=None, previous=None):
        receipt = self.directory / (name + '.json')
        self.ensure_live()
        if receipt.is_file():
            self.steps.append(reference(receipt))
            return read(receipt)['result']
        start = monotonic()
        try:
            result = function()
        except Exception as error:
            code = getattr(error, 'code', None)
            stale = code in STALE_CODES
            validation = not stale and (isinstance(error, ModelConflict) or design and isinstance(error, ValueError))
            kind = 'stale' if stale else 'design' if validation else 'local_execution'
            code = code or ('DESIGN_INVALID_INPUT' if validation else 'LOCAL_EXECUTION_FAILED')
            failure = self.directory / f'{name}-failure-{uuid4().hex[:12]}.json'
            write(failure, dict(ok=False, stage=name, code=code, error=str(error),
                                conflicts=getattr(error, 'conflicts', []), details=getattr(error, 'details', {}),
                                quality=getattr(error, 'quality', None), elapsed_ms=round((monotonic()-start)*1000)))
            report = reference(failure)
            outcome = dict(status='failed', category=kind, stage=name, code=code, message=str(error)[:400],
                           receipt=report, steps=self.steps)
            if validation and diagnostic:
                current = diagnostic if isinstance(diagnostic, Path) else failure
                kind = 'review' if isinstance(diagnostic, Path) else diagnostic
                baseline = evidence(self.workspace,dict(path=previous['path'],sha256=previous['sha256'])) if previous and previous.get('kind')==kind else None
                outcome['diagnostics'] = delta(kind,current,baseline)
            raise StageError(outcome) from error
        write(receipt, dict(ok=True, stage=name, elapsed_ms=round((monotonic()-start)*1000), result=result))
        self.steps.append(reference(receipt))
        self.ensure_live()
        return result

    def render(self, saved, cameras, *, comparison=None):
        comp = comparison or {}
        folder = self.directory / ('render-' + uuid4().hex[:12])
        command = [sys.executable, '-B', str(SCRIPT), 'render', '--source', saved['source'],
                   '--cameras', str(cameras), '--output', str(folder)]
        if comparison:
            command += ['--width', str(comp['width']), '--height', str(comp['height'])]
            if 'quality' in comp:
                command += ['--quality', comp['quality']]
            if 'bundle' in comp:
                command += ['--camera-bundle', str(evidence(self.workspace, comp['bundle'])),
                            '--camera-bundle-sha256', comp['bundle']['sha256']]
        run = subprocess.run(command, cwd=self.workspace, capture_output=True, encoding='utf8', errors='replace',
                             env=dict(os.environ, PYTHONIOENCODING='utf-8'), timeout=180)
        logs = folder.with_suffix('.json')
        write(logs, dict(exit_code=run.returncode, stdout=run.stdout, stderr=run.stderr))
        if run.returncode:
            # The render command cannot report a semantic design failure.
            WorkingModel.open(self.workspace, **saved_binding(saved))._unchanged()
            detail=(run.stderr or run.stdout).strip().splitlines()
            raise RuntimeError(f'材质出图失败：{detail[-1][:240] if detail else run.returncode}。完整回执 {logs}')
        manifest = folder / 'render_manifest.json'
        return dict(render=reference(manifest), log=reference(logs))


def readback(workspace, saved, frozen, reference_constraints=None):
    model = WorkingModel.open(workspace, **saved_binding(saved))
    gates(frozen, model, reference_constraints)
    return dispatch(workspace, 'plan-check', saved_binding(saved)) if model.architecture else dict(validation=model.validate())


def prepare_review(run, saved, camera_spec, previous=None):
    workspace = run.workspace
    model = WorkingModel.open(workspace, **saved_binding(saved))
    review_dir = run.directory / ('review-' + uuid4().hex[:12])
    locations = []
    if model.architecture:
        params=dict(saved_binding(saved), output=str(review_dir))
        if camera_spec:
            params['view_overrides']=camera_spec
        review = run.step('review-prepare', lambda: dispatch(workspace, 'review-prepare',params),
                          design=True, diagnostic='model')
        review_dir = inside(workspace, review['pack']).parent

        def check_coverage():
            if not review['coverage']['coverage_passed']:
                raise ModelConflict('REVIEW_COVERAGE_FAILED', [])
            return dict(passed=True)

        run.step('coverage', check_coverage, design=True, diagnostic=review_dir/'review-pack.json', previous=previous)
        cameras = inside(workspace, review['cameras'])
        locations = [dict(id=row['id'],position=row['position'],purpose=row['purpose'],
                          views=[view['view'] for view in row['candidates'] if view['passed']])
                     for row in review['coverage']['review_locations']]
    else:
        from nbt_refine import prepare
        from nbt_composition.whole_validation import validation_mode
        cameras_data = camera_spec or model.context.get('cameras')

        def prepare_working():
            roles = {camera.get('role') for camera in cameras_data or []}
            if not {'whole','entry'} <= roles or not roles.intersection({'structure','detail','interior'}):
                raise ModelConflict('REVIEW_CAMERAS_REQUIRED', [dict(reason='请提供全景、入口及构造或细部机位')])
            prep = prepare(saved['source'], dict(cameras=cameras_data), review_dir)
            cameras = review_dir/'cameras.json'
            write(cameras, cameras_data)
            return dict(prep, cameras=str(cameras), pack=str(review_dir/'review.json'))

        review = run.step('review-prepare', prepare_working, design=True, diagnostic='model')
        cameras = inside(workspace, review['cameras'])
        review_dir = cameras.parent
    rendered = run.step('render', lambda: run.render(saved, cameras))
    from nbt_review.blind_review import _render
    verified = _render(workspace, dict(manifest=rendered['render']['path'], sha256=rendered['render']['sha256']))
    return dict(review_dir=str(review_dir), pack=reference(inside(workspace, review['pack'])),
                camera=reference(cameras), render=rendered['render'],
                awaiting_views=[row['id'] for row in verified['report']['views']],
                required_locations=locations,
                images=[dict(path=str(row['image']), sha256=row['image_sha256']) for row in verified['images']],
                architecture=bool(model.architecture),
                refinement_ready=False, approval_created=False)
