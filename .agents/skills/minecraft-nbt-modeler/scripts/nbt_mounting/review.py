"""Before/after route evidence and same-camera review for a mounting candidate."""
import hashlib
import json
from math import floor
from pathlib import Path
import subprocess
import sys
import uuid

from nbt_assembly import Volume
from nbt_collision import check_routes
from nbt_refine import save_master
from nbt_selection_edit import sha


def compare_routes(before, after, config, written, *, required=False):
    declarations = []
    if config.get('start') and config.get('targets'):
        declarations.append(dict(name='整体路线', start=config['start'], targets=config['targets']))
    declarations.extend(config.get('route_legs', []))
    if required and not declarations:
        raise ValueError('路线硬约束需要坐标资料声明起点和目标')
    # Bound a review without reporting omitted legs as checked.
    if len(declarations)>16:
        raise ValueError('单次路线比较最多16项声明')
    comparisons = []
    for declaration in declarations:
        if not declaration.get('start') or not declaration.get('targets'):
            raise ValueError('每条路线须声明起点和目标：'+declaration['name'])
        reports = []
        for model in (before, after):
            if declaration.get('validation_only_barriers'):
                copy = Volume(model.size)
                copy.blocks = dict(model.blocks)
                for bounds in declaration['validation_only_barriers']:
                    copy.box(bounds['lo'], bounds['hi'], 'stone')
                model = copy
            reports.append(check_routes(model, declaration['start'], declaration['targets'], max_poses=250000))
        left, right = reports
        impacts = []
        for old, new in zip(left['targets'], right['targets']):
            # Inspect the original witness corridor, not every possible route.
            path = old.get('path', [])
            nearby = set()
            for x,y,z in path:
                for a in range(floor(x-.3),floor(x+.3)+1):
                    for b in range(floor(y),floor(y+1.8)+1):
                        for c in range(floor(z-.3),floor(z+.3)+1):
                            if (a,b,c) in written:
                                nearby.add((a,b,c))
            impacts.append(dict(name=old['name'], before_reachable=old['reachable'],
                                after_reachable=new['reachable'], after_reason=new.get('reason'),
                                before_path_poses=len(path), after_path_poses=len(new.get('path', [])),
                                writes_along_previous_path=[list(p) for p in sorted(nearby)[:32]],
                                writes_along_previous_path_count=len(nearby)))
        comparisons.append(dict(name=declaration['name'], before_passed=left['passed'],
                                after_passed=right['passed'], targets=impacts,
                                before_search_limit=left.get('search_limit_reached',False),
                                after_search_limit=right.get('search_limit_reached',False),
                                after_unknown_shapes=right.get('unknown_shapes',[])))
    failed = [item['name'] for item in comparisons if not item['after_passed']]
    if required and failed:
        raise ValueError('候选未通过声明的玩家路线检查：'+', '.join(failed))
    return dict(passed=not failed if comparisons else None, comparisons=comparisons,
                note='旧路径附近的写入用于定位，路径点数变化不等同于净宽测量')


def write_review(workspace, surface, candidate, walls, result, settings):
    from nbt_task import write_snapshot
    from nbt_mounting.surface_mount import _unchanged

    camera_file = (Path(workspace)/settings['cameras']).resolve()
    cameras_bytes = camera_file.read_bytes()
    cameras = json.loads(cameras_bytes.decode('utf-8-sig'))
    if not isinstance(cameras,list) or not 1<=len(cameras)<=8:
        raise ValueError('整栋审阅需要1至8个共同机位')
    root = Path(workspace).resolve()/'nbt_models/_workspaces/mount_review'/uuid.uuid4().hex
    root.mkdir(parents=True)
    report = dict(status='preparing',plan_sha256=result['plan_sha256'])
    report_path = root/'review.json'

    def write_report():
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')

    write_report()
    try:
        camera_path=root/'cameras.json'
        camera_path.write_bytes(cameras_bytes)
        sides={}
        for side,model,wall_mask in (('before',surface['model'],surface['walls']),('after',candidate,walls)):
            source=root/(side+'.snbt')
            snapshot=root/(side+'.json')
            save_master(source,model,wall_mask)
            write_snapshot(source,snapshot,cameras=cameras)
            item=dict(source=str(source),source_sha256=sha(source),snapshot=str(snapshot),
                      snapshot_sha256=sha(snapshot),geometry_sha256=model.fingerprint())
            if settings.get('render'):
                output=root/(side+'-images')
                log=root/(side+'-render.log')
                with log.open('wb') as stream:
                    proc=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve().parents[1]/'nbt_task.py'),
                        'render','--source',str(source),'--cameras',str(camera_path),'--output',str(output)],
                        stdout=stream,stderr=subprocess.STDOUT,timeout=480)
                if proc.returncode:
                    raise ValueError('整栋出图失败，日志位于 '+str(log))
                images=sorted(str(p) for p in output.glob('*.png'))
                if len(images)!=len(cameras):
                    raise ValueError('整栋出图未覆盖全部机位')
                item['images']=images
                item['image_sha256']={Path(image).name:sha(image) for image in images}
            sides[side]=item
        _unchanged(surface)
        if sha(camera_file)!=hashlib.sha256(cameras_bytes).hexdigest():
            raise ValueError('审阅期间机位文件已变化')
        report.update(status='complete',sides=sides,cameras=str(camera_path),cameras_sha256=sha(camera_path),
                      routes=result['verification']['routes'],changed_blocks=result['changed_blocks'],
                      placements=result['placements'],skipped=result['skipped'],
                      source_sha256=result['source_sha256'],context_sha256=result['context_sha256'])
        write_report()
        return dict(report=str(report_path),**report)
    except (ValueError,OSError,TypeError,KeyError,subprocess.SubprocessError) as error:
        report.update(status='failed',error=str(error))
        write_report()
        raise ValueError(f'{error}。审阅记录 {report_path}') from error
