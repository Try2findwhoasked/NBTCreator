"""Compare unchanged half-block fitting with opt-in vanilla shape families.

Run from the software root through mise; outputs are isolated synthetic fixtures.
All scores use the same original mask at 1/32 block, not each fitter's own grid.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_fit_shapes import fine_options,project_shape,_half_shape
from nbt_model import state
from nbt_structure_agent import dispatch,build


COARSE=dict(slab='quartz_slab',stairs='quartz_stairs')
EXPANDED=dict(COARSE,trapdoor='spruce_trapdoor',wall='cobblestone_wall',pane='white_stained_glass_pane',
    bars='iron_bars',fence='oak_fence',snow='snow',carpet='white_carpet',
    pressure_plate='stone_pressure_plate',end_rod='end_rod',chain='chain')


def samples():
    result=[]
    for name,label,width in (('pane','玻璃板细线',2),('bars','铁栏杆细线',2),('fence','栅栏立柱',4),('wall','石墙立柱',8)):
        mask=np.zeros((16,16),bool);mask[:,(16-width)//2:(16+width)//2]=True
        result.append((name,label,mask))
    mask=np.zeros((16,16),bool);mask[:3,:]=True
    result.append(('trapdoor','活版门横条',mask))
    for name,label,height,lo,hi in (('snow','雪层浅台',2,0,16),('carpet','地毯薄层',1,0,16),('pressure_plate','压力板薄层',1,1,15)):
        mask=np.zeros((32,16),bool);mask[:16,:]=True;mask[16:16+height,lo:hi]=True
        result.append((name,label,mask))
    mask=np.zeros((32,16),bool);mask[:16,:]=True;mask[16,6:10]=True;mask[17:,7:9]=True
    result.append(('end_rod','末地烛细杆',mask))
    mask=np.zeros((64,64),bool)
    for x,y in ((0,0),(3,0),(0,3),(3,3)):mask[y*16:(y+1)*16,x*16:(x+1)*16]=True
    mask[:3,16:48]=True;mask[61:,16:48]=True
    for lo in (7,55):mask[16:48,lo:lo+2]=True
    result.append(('frame','细边框',mask))
    mask=np.zeros((32,48),bool)
    for x in range(3):
        mask[:,x*16+6:x*16+10]=True
    for y in (6,12,22,28):mask[y:y+3,:]=True
    result.append(('grid','栅栏网格',mask))
    result=[(*row,16) for row in result]
    mask=np.zeros((64,32),bool);mask[:32,:]=True;mask[32:,13:19]=True
    result.append(('chain','链条细杆',mask,32))
    library=ROOT/'.agents/skills/minecraft-nbt-modeler/assets/ornament-patterns'
    for name,label,size in (('micro-diamond','内置菱花二值试件',4),('micro-scroll','内置卷钩二值试件',6)):
        with Image.open(library/(name+'.png')) as source:
            mask=np.flipud(np.asarray(source.convert('L').resize((size*16,size*16),Image.Resampling.BOX)))>=128
        result.append((name,label,mask,16))
    return result


def compare(output,render):
    output=output.resolve();output.mkdir(parents=True,exist_ok=False)
    workspace=output/'workspace';workspace.mkdir()
    reports=[];previews={}
    for name,label,mask,resolution in samples():
        height,width=mask.shape
        image=workspace/(name+'.png');Image.fromarray(np.flipud(mask).astype('uint8')*255).save(image)
        reference=np.repeat(np.repeat(mask,32//resolution,axis=0),32//resolution,axis=1)
        row=dict(id=name,name=label,size_uv=[width//resolution,height//resolution],reference_resolution=32)
        selected=dict(COARSE,**{name:EXPANDED[name]}) if name in EXPANDED else EXPANDED
        if name.startswith('micro-'):
            selected={key:value for key,value in EXPANDED.items() if key in ('slab','stairs','trapdoor','wall','bars','fence')}
        for profile,shapes in (('coarse',COARSE),('expanded',selected)):
            started=time.perf_counter()
            try:
                result=dispatch(workspace,'pattern_microfit',dict(surface='wall',size_uv=row['size_uv'],
                    shapes=shapes,micro_alignment='fixed',sample=dict(path=image.name,sha256=sha256(image.read_bytes()).hexdigest(),noise_strength=0,fit='stretch')))
                data=build(workspace,result['spec']);pixels=np.zeros(reference.shape,bool)
                geometry=fine_options(state('quartz_block'),shapes,'wall')[0].geometry
                for x,y,z,index,_ in data['blocks']:
                    if z!=1:continue
                    value=data['palette'][index];shape=geometry.get(value) or _half_shape(value)
                    pixels[y*32:(y+1)*32,x*32:(x+1)*32]=np.asarray(project_shape(shape,'wall',32)).reshape(32,32)
                iou=float((pixels&reference).sum()/max(1,(pixels|reference).sum()))
                row[profile]=dict(ok=True,seconds=round(time.perf_counter()-started,3),ink_overlap=iou,
                    coverage_error=float((pixels!=reference).mean()),shape_counts=result['shape_counts'],
                    enabled_shapes=shapes,approximate_states=result['microfit'].get('approximate_states',[]),collision_validated=False)
            except ValueError as error:
                row[profile]=dict(ok=False,seconds=round(time.perf_counter()-started,3),error=str(error))
                continue
            if name in ('frame','grid','chain','pane','bars','end_rod','micro-diamond','micro-scroll'):
                from nbt_refine import save_master
                from nbt_assembly import Volume
                model=Volume(result['spec']['size']);walls=set()
                for x,y,z,index,wall in data['blocks']:
                    model.put((x,y,z),data['palette'][index])
                    if wall:walls.add((x,y,z))
                destination=output/(name+'-'+profile);destination.mkdir()
                source=destination/'candidate.snbt';save_master(source,model,walls)
                cameras=destination/'cameras.json'
                cameras.write_text(json.dumps([dict(id='comparison',role='overall',eye=[row['size_uv'][0]/2+1,row['size_uv'][1]/2+1,9],target=[row['size_uv'][0]/2,row['size_uv'][1]/2,1])]),encoding='utf8')
                if render:
                    subprocess.run(['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(workspace),'render','--source',str(source),'--cameras',str(cameras),'--output',str(destination/'render')],check=True,cwd=ROOT)
                previews[name+'-'+profile]=str(destination)
        reports.append(row)
        print(json.dumps(row,ensure_ascii=False),flush=True)
    report=dict(reference='same_original_mask_at_1/32_block',material_alpha_scored=False,game_tested=False,
        profiles=dict(coarse=COARSE,expanded=EXPANDED),cases=reports,previews=previews)
    (output/'benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(output=str(output),cases=len(reports)),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args();compare(args.output,args.render)
