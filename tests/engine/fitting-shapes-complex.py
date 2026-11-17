"""Bounded, reproducible complex-ornament comparison using original library images."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
SCRIPTS=ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'
sys.path.insert(0,str(SCRIPTS))

CASES=[('gothic-rose',[8,8]),('gothic-rose',[12,12]),('acanthus-frieze',[12,6]),
       ('baroque-pilaster',[8,12]),('ottoman-eight-point-star',[12,12]),('chinese-window-lattice',[12,12])]
BASE=dict(slab='stone_brick_slab',stairs='stone_brick_stairs')
PALETTES=dict(original=BASE,stone=dict(BASE,wall='stone_brick_wall'),
              mixed=dict(BASE,wall='stone_brick_wall',trapdoor='spruce_trapdoor',bars='iron_bars',fence='oak_fence'))


def worker(request):
    from nbt_structure_agent import dispatch,build
    from nbt_pattern_panel import sample_input
    from nbt_ornament_sample import sample_image,resize_sample
    from nbt_pattern_quality import source_bitmap,assess
    from nbt_fit_shapes import fine_options,project_shape,_half_shape
    from nbt_model import state
    from nbt_refine import save_master
    from nbt_assembly import Volume
    data=json.loads(request.read_text(encoding='utf8'));output=request.parent
    started=time.perf_counter()
    try:
        result=dispatch(Path(data['workspace']),'pattern_microfit',data['arguments'])
        args=data['arguments'];width,height=args['size_uv'];built=build(Path(data['workspace']),result['spec'])
        root,sample=sample_input(Path(data['workspace']),args)
        image=sample_image(root,sample)
        reference=source_bitmap(resize_sample(image,(width*32,height*32),sample.get('fit','contain')),sample)
        pixels=np.zeros(reference.shape,bool)
        geometry=fine_options(state(args['material']),args['shapes'],'wall')[0].geometry
        model=Volume(result['spec']['size']);walls=set()
        for x,y,z,index,wall in built['blocks']:
            value=built['palette'][index];model.put((x,y,z),value)
            if wall:walls.add((x,y,z))
            if z==1:
                shape=geometry.get(value) or _half_shape(value)
                pixels[y*32:(y+1)*32,x*32:(x+1)*32]=np.asarray(project_shape(shape,'wall',32)).reshape(32,32)
        common=assess(pixels,reference,'ornate',0)
        save_master(output/'candidate.snbt',model,walls)
        (output/'cameras.json').write_text(json.dumps([dict(id='front',role='overall',eye=[width/2,height/2,height*1.35+4],target=[width/2,height/2,1]),
            dict(id='oblique',role='detail',eye=[width+3,height+3,height*1.4+4],target=[width/2,height/2,1])]),encoding='utf8')
        q=result['microfit']
        receipt=dict(ok=common['score']>=80,compiled=True,seconds=round(time.perf_counter()-started,3),
            common_score=common['score'],common_iou=common['metrics']['ink_iou'],common_detail=common['metrics']['detail_retention'],
            quality=common,engine_quality=q['visual_quality'],topology=dict(source=q['source_topology'],result=q['result_topology']),
            shape_counts=result['shape_counts'],approximate_states=q.get('approximate_states',[]),
            source_sha256=result['sample_sha256'],model_sha256=result['content_sha256'],
            source=str(output/'candidate.snbt'),cameras=str(output/'cameras.json'))
    except ValueError as error:
        receipt=dict(ok=False,compiled=False,seconds=round(time.perf_counter()-started,3),error=str(error))
    (output/'result.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


def compare(output,render,timeout):
    output=output.resolve();output.mkdir(parents=True,exist_ok=False)
    workspace=output/'workspace';workspace.mkdir()
    rows=[]
    report=dict(reference_resolution=32,quality_profile='ornate',minimum_quality_score=80,
        alignment='fixed',original_images_unchanged=True,texture_alpha_scored=False,game_tested=False,cases=rows)
    for preset,size in CASES:
        for palette,shapes in PALETTES.items():
            name=preset+'-'+str(size[0])+'x'+str(size[1])+'-'+palette
            destination=output/name;destination.mkdir();request=destination/'request.json'
            arguments=dict(surface='wall',preset=preset,size_uv=size,micro_alignment='fixed',
                quality_profile='ornate',min_quality_score=80,material='stone_bricks',base='deepslate_tiles',shapes=shapes)
            request.write_text(json.dumps(dict(workspace=str(workspace),arguments=arguments)),encoding='utf8')
            print(json.dumps(dict(start=name),ensure_ascii=False),flush=True)
            started=time.perf_counter()
            try:
                run=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--request',str(request)],
                    capture_output=True,text=True,encoding='utf8',timeout=timeout,cwd=ROOT)
                if run.returncode:raise RuntimeError(run.stderr or run.stdout)
                receipt=json.loads((destination/'result.json').read_text(encoding='utf8'))
            except subprocess.TimeoutExpired:
                receipt=dict(ok=False,compiled=False,timeout=True,seconds=round(time.perf_counter()-started,3),error='超过单项测试时间上限')
            except RuntimeError as error:
                receipt=dict(ok=False,compiled=False,error=str(error))
            row=dict(preset=preset,size_uv=size,palette=palette,shapes=shapes,**receipt);rows.append(row)
            if render and receipt.get('compiled'):
                subprocess.run(['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(workspace),'render',
                    '--source',receipt['source'],'--cameras',receipt['cameras'],'--output',str(destination/'render')],check=True,cwd=ROOT)
            (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
            print(json.dumps({k:v for k,v in row.items() if k not in ('quality','engine_quality','shapes')},ensure_ascii=False),flush=True)
    report['completed']=True
    report['passed']=sum(row['ok'] for row in rows)
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(output=str(output),cases=len(rows),passed=sum(row['ok'] for row in rows)),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--request',type=Path)
    parser.add_argument('--render',action='store_true')
    parser.add_argument('--timeout',type=int,default=60)
    args=parser.parse_args()
    if args.request:worker(args.request)
    elif args.output:compare(args.output,args.render,args.timeout)
    else:parser.error('需要 --output 或 --request')
