"""Create a shareable synthetic eccentric loft and mixed relief request."""
import hashlib
import json
from pathlib import Path

from PIL import Image
from nbt_review.reference_views import register_reference,save_fit
from nbt_composition.working_model import WorkingModel


def create_curve_fixture(workspace):
    workspace=Path(workspace).resolve();inputs=workspace/'inputs';inputs.mkdir(parents=True,exist_ok=True)
    views={}
    for name,u,v in [('front','x','-y'),('side','z','-y'),('top','x','z')]:
        file=inputs/(name+'.png');Image.new('RGB',(128,128),'white').save(file)
        views[name]=dict(image='inputs/'+file.name,sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
            origin=[4,100] if name!='top' else [4,4],pixels_per_block=2,u_axis=u,v_axis=v,
            origin_type='original',basis='合成锚点，非真实参考')
    anchors=[];rows=[]
    for y,x0,x1,z0,z1 in [(0,10,38,10,30),(8,8,40,9,31),(16,12,38,11,29)]:
        row={}
        for edge,world in [('x_min',[x0,y,20]),('x_max',[x1,y,20]),('z_min',[24,y,z0]),('z_max',[24,y,z1])]:
            name=f'{edge}_{y}';row[edge]=name;x,yy,z=world
            anchors.append(dict(id=name,part='tower',world=world,basis='合成锚点',confidence='measured',uncertainty=0,
                views=dict(front=[4+2*x,100-2*y],side=[4+2*z,100-2*y],top=[4+2*x,4+2*z])))
        rows.append(row)
    rows[1]['corner']=True
    reference=register_reference(workspace,dict(output='nbt_models/_workspaces/reference-views/synthetic',
                                                views=views,anchors=anchors,assumptions=[]))
    fitted=save_fit(workspace,dict(reference=reference['manifest'],reference_sha256=reference['manifest_sha256'],
        part='tower',rows=rows,sample_step=1,vertices=64),'nbt_models/_workspaces/reference-fits/synthetic.json')
    geometry=json.loads(Path(fitted['output']).read_text(encoding='utf8'))['geometry']
    working=WorkingModel(workspace,[48,20,40])
    working.apply_operations([dict(kind='geometry',label='合成偏心宿主',classification='wall',
        lo=[0,0,0],hi=[47,16,39],state='stone_bricks',geometry=geometry)])
    source=working.save_draft(name_zh='合成偏心宿主')
    palette={'R':dict(kind='raise',state='polished_andesite',height=1,wall=False,role='diagonal_band'),
        'C':dict(kind='cut',depth=1,backing=1,role='groove'),
        'W':dict(kind='inlay',depth=1,backing=1,state='blackstone',wall=True,role='dark_window'),
        'I':dict(kind='raise',height=1,state='gold_block',wall=True,role='scroll')}
    mask_rows=[]
    for y in range(8):
        row=['.']*32
        for col in (2+y//3,3+y//3):row[col]='R'
        row[10]='C';row[16]='W'
        for col in ((23,24),(22,23),(22,),(22,23,24),(24,25),(25,),(24,25),(23,24))[y]:row[col]='I'
        mask_rows.append(''.join(row))
    mask=inputs/'mask.json'
    mask.write_text(json.dumps(dict(schema_version=1,name='合成斜带暗窗切槽纹样',rows=mask_rows,palette=palette),ensure_ascii=False),encoding='utf8')
    cameras=[dict(id='front',eye=[24,10,65],target=[24,8,20]),
        dict(id='oblique',eye=[-20,30,60],target=[24,8,20]),
        dict(id='section',eye=[-20,30,60],target=[24,8,20],cuts=[dict(axis='y',position=8,removed_side='above')]),
        dict(id='far',eye=[-50,48,95],target=[24,8,20])]
    return dict(source=source['source'],source_sha256=source['source_sha256'],profile=fitted['output'],profile_sha256=fitted['sha256'],
        mask=str(mask),mask_sha256=hashlib.sha256(mask.read_bytes()).hexdigest(),
        mapping=dict(u_start=0,u_span=.25,y_start=4,max_distance=2,u_subsamples=2,connect_raised=dict(max_new_blocks=64)),
        cameras=cameras,output='nbt_models/_workspaces/curve-samples/representative')
