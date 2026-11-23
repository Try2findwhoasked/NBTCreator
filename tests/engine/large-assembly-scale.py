"""Opt-in synthetic large-source acceptance; retains evidence under build/."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_large_assembly import AssemblyVolume,read_assembly,save_assembly,verify_assembly_binding
from nbt_history import History
from nbt_working_model import WorkingModel
from nbt_working_model import ModelConflict
from nbt_composition.assembly_handoff import create_slice,merge_slices
from nbt_snbt import read_snbt,save_snbt


def main():
    build=ROOT/'build';build.mkdir(exist_ok=True)
    output=Path(tempfile.mkdtemp(prefix='large-assembly-scale-',dir=build));workspace=output/'workspace'
    workspace.mkdir();started=time.perf_counter();stages=[]
    def done(name):
        nonlocal started
        row=dict(stage=name,seconds=round(time.perf_counter()-started,3));stages.append(row)
        print(json.dumps(row),flush=True);started=time.perf_counter()
    model=AssemblyVolume((300,384,300));walls=set()
    for y in (0,48,96,144,192,240):
        for x in range(25,275):
            for z in range(25,255):
                model.blocks[(x,y,z)]='minecraft:stone_bricks'
                if x==25:walls.add((x,y,z))
    # Sparse, offset shell and a separately recognizable upper building.
    for y in range(1,294):
        inset=(y//72)*2
        x0,x1,z0,z1=25+inset,274-inset,25+inset,254-inset
        for x in range(x0,x1+1,8):
            for z in (z0,z1):model.blocks[(x,y,z)]='minecraft:deepslate_bricks';walls.add((x,y,z))
        for z in range(z0,z1+1,8):
            for x in (x0,x1):model.blocks[(x,y,z)]='minecraft:deepslate_bricks';walls.add((x,y,z))
    for y in range(250,270):
        for x in range(130,171):
            for z in (120,160):model.blocks[(x,y,z)]='minecraft:bricks';walls.add((x,y,z))
        for z in range(120,161):
            for x in (130,170):model.blocks[(x,y,z)]='minecraft:bricks';walls.add((x,y,z))
    for y in range(270,294):model.blocks[(150,y,140)]='minecraft:gold_block'
    for step,x in enumerate(range(145,153)):
        y=(step+1)//2
        material='minecraft:stone_slab[type=bottom,waterlogged=false]' if step%2 else 'minecraft:stone'
        for z in range(3):model.blocks[(x,y,z)]=material
    model.blocks[(149,293,149)]='minecraft:gold_block'
    expected=len(model.blocks)
    specs=[dict(offset=[x,y,z],size=[150,192,150]) for x in (0,150) for y in (0,192) for z in (0,150)]
    source=save_assembly(workspace/'nbt_models/standalone/规模测试/v01/master',model,walls,specs)
    done('partition_write_and_roundtrip')
    loaded,loaded_walls=read_assembly(source['source'])
    assert loaded.blocks==model.blocks and loaded_walls==walls and loaded.size==(300,384,300)
    assert verify_assembly_binding(loaded)
    done('read_and_verify')
    history=History(workspace);first=history.record(dict(source=source['source'],message='合成规模基线',set_current=True))
    assert first['version']['source_matches'] and first['version']['size']==[300,384,300]
    context=dict(mode='standalone',openings=[],require_routes=True,start=[145.5,1,1.5],targets={'end':[152.5,4.5,1.5]},
                 route_legs=[dict(name='返程',start=[152.5,4.5,1.5],targets={'entry':[145.5,1,1.5]})])
    working=WorkingModel.open(workspace,source['source'],context=context,source_sha256=source['source_sha256'])
    working.patch([dict(pos=[200,49,200],before=['minecraft:air',False],after=['minecraft:gold_block',False])])
    saved=working.save_draft(name_zh='规模测试')
    assert not saved['history_pending'] and not saved['nbt_exported']
    revised,revised_walls=read_assembly(saved['source'])
    assert len(revised.blocks)==expected+1 and revised.get((200,49,200))=='minecraft:gold_block' and revised_walls==walls
    assert verify_assembly_binding(loaded)
    done('history_patch_save_and_reopen')
    slices=[]
    for index,x in enumerate((145,147,149,151)):
        issued=create_slice(workspace,dict(source=saved['source'],source_sha256=saved['source_sha256'],context=context,
            region=dict(lo=[144,0,0],hi=[153,9,2]),write_bounds=dict(lo=[x,0,0],hi=[x+1,9,2]),
            output=f'nbt_models/_workspaces/assembly-handoffs/scale-{index}'))
        piece,mask=read_snbt(issued['baseline']);piece.put((x-144,8,0),'gold_block')
        if index==1:piece.put((4,3,1),'stone')
        candidate=workspace/f'scale-candidate-{index}.snbt';candidate_receipt=save_snbt(candidate,piece,mask)
        slices.append(dict(manifest=issued['manifest'],manifest_sha256=issued['manifest_sha256'],
                           candidate=str(candidate),candidate_sha256=candidate_receipt['source_sha256']))
    request=dict(source=saved['source'],source_sha256=saved['source_sha256'],context=context,slices=slices,name_zh='规模协作')
    try:merge_slices(workspace,request)
    except ModelConflict as error:
        if error.code!='SLICE_PROTECTED':raise
    else:raise AssertionError('楼梯净空冲突未被拒绝')
    piece,mask=read_snbt(slices[1]['candidate']);piece.put((4,3,1),'air')
    repaired=workspace/'scale-candidate-repaired.snbt';repaired_receipt=save_snbt(repaired,piece,mask)
    slices[1].update(candidate=str(repaired),candidate_sha256=repaired_receipt['source_sha256'])
    merged=merge_slices(workspace,request)
    assert merged['changed_positions']==4 and merged['routes']['passed'] and merged['routes']['legs'][0]['report']['passed']
    assert merge_slices(workspace,request)['saved']['source']==merged['saved']['source']
    done('four_slice_conflict_repair_and_retry')
    cameras=output/'cameras.json'
    view=dict(role='合成组装全景',eye=[450,330,-400],target=[150,120,150],fov=48)
    cameras.write_text(json.dumps([dict(id='overview',**view),dict(id='section',cuts=[dict(axis='y',position=100,removed_side='above')],**view)]),encoding='utf8')
    node=shutil.which('node')
    if not node:raise RuntimeError('Node 不可用，请通过 mise exec 运行')
    rendered=output/'render'
    run=subprocess.run([node,str(ROOT/'scripts/cli.mjs'),'--workspace',str(workspace),'render','--source',merged['saved']['source'],
                        '--cameras',str(cameras),'--output',str(rendered),'--width','320','--height','240'],
                       cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=180)
    if run.returncode:raise RuntimeError(run.stdout+'\n'+run.stderr)
    render_manifest=json.loads((rendered/'render_manifest.json').read_text(encoding='utf8'))
    assert render_manifest['status']=='complete' and render_manifest['source_kind']=='assembly'
    assert render_manifest['source_sha256']==merged['saved']['source_sha256'] and len(render_manifest['assembly_partitions'])==8
    assert len(render_manifest['images'])==2 and render_manifest['views'][0]['eye']==render_manifest['views'][1]['eye']
    assert render_manifest['views'][1]['cuts']==[dict(axis='y',position=100,removed_side='above')]
    assert render_manifest['images'][0]['sha256']!=render_manifest['images'][1]['sha256']
    for row in render_manifest['images']:
        assert hashlib.sha256((rendered/row['image']).read_bytes()).hexdigest()==row['sha256']
    done('actual_texture_render')
    report=dict(passed=True,size=[300,384,300],blocks=expected,walls=len(walls),partitions=8,
                original=source,saved=saved,merged=merged,render_manifest=str(rendered/'render_manifest.json'),stages=stages,
                scope='Synthetic geometry and static route only; no user approval or in-game validation')
    (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(passed=True,output=str(output),blocks=expected,stages=stages),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
