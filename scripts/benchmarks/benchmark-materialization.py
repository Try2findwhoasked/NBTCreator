"""Compare CPU materialization pipelines without changing their public inputs."""
import argparse,hashlib,importlib.util,json,statistics,sys,time
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--engine',type=Path,default=ROOT/'.agents/skills/minecraft-nbt-modeler');parser.add_argument('--output',type=Path);parser.add_argument('--compare',type=Path);args=parser.parse_args()
    output=args.output or ROOT/'build'/('materialization-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'));output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(args.engine.resolve()/'scripts'))
    from nbt_agent.structure import dispatch,build
    from nbt_assets.components import validate,paste_plan
    from nbt_assembly import Volume
    module=importlib.util.spec_from_file_location('compute_bench',Path(__file__).with_name('benchmark-compute.py'));bench=importlib.util.module_from_spec(module);module.loader.exec_module(bench)
    dense=dict(name='64000方块校验',size=[40]*3,operations=[dict(kind='paste_component',label='实体',classification='wall',lo=[0]*3,hi=[39]*3,palette=['stone_bricks'],voxels=[[x,y,z,0] for x in range(40) for y in range(40) for z in range(40)])])
    mixed=dict(name='混材稀疏构件',size=[48]*3,operations=[dict(kind='paste_component',label='实体',classification='body',lo=[0]*3,hi=[47]*3,palette=['quartz_block','stone_brick_slab[type=top]','stone_brick_stairs[facing=east]'],voxels=[[x,y,z,(x+y+z)%3] for x in range(48) for y in range(32) for z in range(48) if (x+z)%2])])
    component=build(output,mixed)
    jobs=[('column_cpu',lambda:dispatch(output,'field_compile',bench.column_request('cpu'))),('column_gpu',lambda:dispatch(output,'field_compile',bench.column_request('gpu'))),
        ('dense_build_64000',lambda:build(output,dense)),('mixed_build_36864',lambda:build(output,mixed)),('component_validate_36864',lambda:validate(component)),
        ('paste_plan_64000',lambda:paste_plan(Volume([40]*3),dense['operations'][0],set()))]
    rows=[];previous=json.loads(args.compare.read_text(encoding='utf8')) if args.compare else None
    for name,call in jobs:
        start=time.perf_counter();result=call();first=time.perf_counter()-start;times=[]
        for _ in range(7):
            start=time.perf_counter();result=call();times.append(time.perf_counter()-start)
        digest=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        row=dict(name=name,first_seconds=first,warm_median_seconds=statistics.median(times),samples_seconds=times,result_sha256=digest)
        if previous:
            old=next(r for r in previous['cases'] if r['name']==name);assert digest==old['result_sha256'],name+' changed result'
            row.update(previous_seconds=old['warm_median_seconds'],speedup=old['warm_median_seconds']/row['warm_median_seconds'],identical_result=True)
        rows.append(row);print(json.dumps(row),flush=True)
    data=dict(engine=str(args.engine),measurement='7 warm serial calls per case; all GPU readback synchronized',cases=rows)
    (output/'results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(passed=True,output=str(output))))

if __name__=='__main__':main()
