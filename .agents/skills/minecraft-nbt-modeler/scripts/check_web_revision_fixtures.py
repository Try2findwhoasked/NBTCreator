"""New-version conversion tests, exclusively synthetic authoring assets."""
from pathlib import Path
import argparse,copy,json
from nbt_assembly import Volume
from nbt_refine import save_master,read_master
from nbt_detail_control import default_settings,write_json,read_json,preview_effect,digest
from nbt_web_revision import convert_web_json
from nbt_delivery import verify_delivery

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);out=parser.parse_args().output.resolve();out.mkdir(parents=True,exist_ok=False)
    project=out/'r001_test';version=project/'v01';(version/'master').mkdir(parents=True)
    model=Volume((96,16,96));walls=set();cells=[[0,0],[1,0],[0,1]]
    for cx,cz in cells:
        x,z=cx*48,cz*48;model.box((x,0,z),(x+47,15,z+47),'stone_bricks');model.box((x+1,2,z+1),(x+46,13,z+46),'air')
        walls.update(p for p in model.blocks if x<=p[0]<=x+47 and z<=p[2]<=z+47 and 2<=p[1]<=13 and (p[0] in (x,x+47) or p[2] in (z,z+47)))
    source=version/'master/master_geometry.json.gz';save_master(source,model,walls);original=digest(source)
    context=version/'coordinates.json';write_json(context,dict(cells=cells,start=[3.5,2,3.5],targets={'exit':[10.5,2,3.5]},interior_probes=[[24,8,24],[72,8,24],[24,8,72]],ports=[]))
    settings=default_settings();settings['pattern'].update(enabled=True,fraction=.01)
    request=dict(schema_version=1,source=str(source),source_sha256=original,context=str(context),cameras='',settings=settings)
    file=out/'settings.json';write_json(file,request)
    result=convert_web_json(file);target=Path(result['output']);checks={}
    checks['sibling_next_version']=target==project/'v02'
    checks['source_not_modified']=digest(source)==original
    checks['three_runtime_slices_no_missing_cell']=len(list((target/'runtime/parts').glob('*.nbt')))==3 and not list((target/'runtime/parts').glob('*p11.nbt'))
    delivery=verify_delivery(target/'delivery');checks['exact_layered_delivery']=delivery['actual_nbt_files']==6 and delivery['exact_solid_reconstruction']
    checks['complete_master_and_metadata']=(target/'master/master_geometry.json.gz').is_file() and all((target/name).is_file() for name in ['coordinates.json','settings.json','cameras.json','changes.json','conversion.json','validation/whole_model.json','runtime/parts.json'])
    job=out/'job';job.mkdir();write_json(job/'request.json',request);preview=preview_effect(request,job/'result')
    next_result=convert_web_json(preview['snapshot']);checks['after_json_goes_to_v03']=Path(next_result['output'])==project/'v03'
    tampered=read_json(preview['snapshot']);tampered['blocks'][0][1]='minecraft:dirt';write_json(job/'result/after.json',tampered)
    try:convert_web_json(job/'result/after.json');checks['tampered_preview_refused']=False
    except ValueError:checks['tampered_preview_refused']=not (project/'v04').exists()
    isolated=out/'after.json';write_json(isolated,tampered)
    try:convert_web_json(isolated);checks['isolated_snapshot_refused']=False
    except ValueError:checks['isolated_snapshot_refused']=True
    bad=copy.deepcopy(request);bad['settings']['max_changed_blocks']=1;write_json(out/'limited.json',bad)
    try:convert_web_json(out/'limited.json');checks['budget_refusal_does_not_allocate_version']=False
    except ValueError:checks['budget_refusal_does_not_allocate_version']=not (project/'v04').exists()
    checks['no_fake_approval_or_runtime_acceptance']=not list(project.rglob('approval.json')) and not result['runtime_verified']
    assert all(checks.values()),checks;write_json(out/'results.json',dict(passed=True,checks=checks));print(json.dumps(dict(passed=True,checks=len(checks))))
if __name__=='__main__':main()
