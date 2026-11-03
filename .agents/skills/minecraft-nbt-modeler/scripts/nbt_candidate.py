"""Read-only validation of the exact displayed candidate against its source and parameter request."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tempfile


def validate_candidate(request, snapshot, output):
    from nbt_assembly import Volume
    from nbt_detail_control import digest, canonical, compile_plan, normalize_context, preview_effect, reserve_output, write_json
    from nbt_refine import read_master, protections
    from nbt_task import checked_preview_snapshot
    from nbt_whole_validation import validate_whole
    from nbt_change_policy import change_sets,enforce_changes

    output=reserve_output(output)
    report=dict(schema_version=1,status='candidate_failed',passed=False,checks={},
                source=str(Path(request['source']).resolve()),snapshot=str(Path(snapshot).resolve()),
                asset_written=False,approval_created=False,runtime_verified=False,design='pending_visual_review')
    def check(name, function):
        try:
            details=function()
            report['checks'][name]=dict(passed=True,details=details)
            return details
        except (ValueError,AssertionError,KeyError,TypeError,IndexError,OSError) as error:
            report['checks'][name]=dict(passed=False,error=str(error) or type(error).__name__)
            return None
    try:
        source=Path(request['source']).resolve();source_hash=digest(source)
        context=Path(request['context']).resolve();context_hash=digest(context)
        cameras=Path(request['cameras']).resolve() if request.get('cameras') else None
        camera_hash=digest(cameras) if cameras else None
        snapshot=Path(snapshot).resolve();snapshot_hash=digest(snapshot)
        report.update(source_sha256=source_hash,snapshot_sha256=snapshot_hash,context=str(context),context_sha256=context_hash,
                      settings_sha256=canonical(request['settings']))
        if request.get('source_sha256') and request['source_sha256']!=source_hash:
            raise ValueError('原建筑已变化，请重新打开并计算候选')
        checked_source,raw=checked_preview_snapshot(snapshot)
        data=json.loads(raw)
        if checked_source!=source:
            raise ValueError('候选快照属于其他源文件，请在当前建筑重新计算预览')
        baseline,base_walls=read_master(source)
        config=normalize_context(baseline,str(context),str(cameras) if cameras else '',request['settings'])
        compile_plan(request['settings'],baseline.size)
        if 'wall_positions' in config:
            base_walls={tuple(p) for p in config['wall_positions']}
        base_walls={p for p in base_walls if p in baseline.blocks}
        candidate=Volume(data['size'])
        for p,state in data['master_blocks']:candidate.put(tuple(p),state)
        walls={tuple(p) for p in data['wall_positions']}
        changed,layer_changed=change_sets(baseline.blocks,candidate.blocks,base_walls,walls)
        report.update(geometry_sha256=candidate.fingerprint(),baseline_geometry_sha256=baseline.fingerprint(),
                      changed_blocks=len(changed),wall_membership_changes=len(layer_changed))
        report['checks']['inputs']=dict(passed=True)

        def matching_preview():
            with tempfile.TemporaryDirectory(prefix='nbt-candidate-check-') as temporary:
                expected=preview_effect(request,Path(temporary)/'expected')
                expected_data=json.loads(Path(expected['snapshot']).read_text(encoding='utf8'))
                for key in ('source_sha256','geometry_sha256','size','master_blocks','blocks','wall_positions'):
                    if data.get(key)!=expected_data.get(key):
                        raise ValueError('快照与当前参数重新计算的效果不一致：'+key+'；请更新预览')
            return dict(exact_recalculation_match=True)
        check('preview_matches_request',matching_preview)

        def budget():
            maximum=request['settings'].get('max_changed_blocks',4096)
            difference=enforce_changes(baseline.blocks,candidate.blocks,base_walls,walls,maximum=maximum)
            return dict(difference,maximum=maximum)
        check('change_budget',budget)

        def protection():
            protected=protections(baseline,config)
            enforce_changes(baseline.blocks,candidate.blocks,base_walls,walls,protected)
            return dict(protected_positions=len(protected),touched=0)
        check('protected_geometry',protection)

        def mask():
            declared='wall_positions' in config
            if source.suffix.lower()!='.nbt':
                declared|='wall_positions' in json.loads(gzip.decompress(source.read_bytes()))
            if not declared:
                raise ValueError('缺少显式墙层归属；请提供主模型 wall_positions 或坐标配置，不按材质猜墙')
            if len(walls)!=len(data['wall_positions']) or any(not candidate.in_bounds(p) or p not in candidate.blocks for p in walls):
                raise ValueError('墙层坐标重复、越界或指向空气')
            if config.get('mode')=='standalone' and not walls and config.get('allow_empty_wall_mask') is not True:
                raise ValueError('独立素材的空墙层需要显式 allow_empty_wall_mask=true')
            if config.get('mode','saodg')!='standalone':
                for cell in config['cells']:
                    if not any((p[0]//48,p[2]//48)==tuple(cell) for p in walls):
                        raise ValueError('有效分片缺少明确墙层：'+str(cell))
            return dict(explicit=True,wall_blocks=len(walls))
        check('wall_ownership',mask)
        check('baseline_geometry',lambda:validate_whole(baseline,config))
        check('candidate_geometry',lambda:validate_whole(candidate,config))

        def unchanged():
            if digest(source)!=source_hash or digest(context)!=context_hash or digest(snapshot)!=snapshot_hash or (cameras and digest(cameras)!=camera_hash):
                raise ValueError('检查期间源、坐标配置、相机或候选发生变化，请重新检查')
            return dict(source=True,context=True,snapshot=True,cameras=True)
        check('inputs_unchanged',unchanged)
    except (ValueError,AssertionError,KeyError,TypeError,IndexError,OSError) as error:
        report['checks']['inputs']=dict(passed=False,error=str(error) or type(error).__name__)
    report['passed']=bool(report['checks']) and all(item['passed'] for item in report['checks'].values())
    report['status']='candidate_validated' if report['passed'] else 'candidate_failed'
    report['scope']='Exact candidate/settings binding, changes, protection, wall ownership and static whole-model checks only; no visual/game/approval claim.'
    write_json(output/'validation.json',report)
    checks={name:{k:value for k,value in item.items() if k!='details'} for name,item in report['checks'].items()}
    return dict(status=report['status'],passed=report['passed'],checks=checks,
                changed_blocks=report.get('changed_blocks'),wall_membership_changes=report.get('wall_membership_changes'),geometry_sha256=report.get('geometry_sha256'),
                source_sha256=report.get('source_sha256'),settings_sha256=report.get('settings_sha256'),
                validation=str(output/'validation.json'),output=str(output),asset_written=False,approval_created=False,
                note='候选检查通过仍需看图；检查不生成正式建筑或批准。')


def main():
    from nbt_request_paths import read_request
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',type=Path,required=True)
    parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=validate_candidate(read_request(args.request),args.snapshot,args.output)
    print(json.dumps(dict(ok=True,result=result),ensure_ascii=False))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
