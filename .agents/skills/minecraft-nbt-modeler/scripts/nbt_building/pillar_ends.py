"""Bounded pillar mouldings and independently bound end-band patterns."""
from copy import deepcopy
from math import pi,sin

PROFILES=('plain','stepped','beveled','torus','bell','bezier')


def pattern_height(setting):
    pattern=setting['pattern'];rows=pattern.get('tile_counts',[1,1])[1]
    return pattern['size_uv'][1]*rows+pattern.get('gap_uv',[1,1])[1]*(rows-1)


def end_layers(form,part,size,box,material):
    w,h,d=size;key='base' if part=='base' else 'capital'
    height=form.get(key+'_height',1);start=0 if key=='base' else h-height
    profile=form.get(key+'_profile','plain');curve=form.get(key+'_curve')
    if (curve is not None)!=(profile=='bezier'):raise ValueError('柱端bezier轮廓须成对提供4个半径控制值，其他轮廓不接受curve')
    if profile in ('attic','tuscan','doric','ionic','corinthian','composite'):
        from nbt_building.classical_column import classical_end
        classical_end(form,part,size,box,material);return
    if profile not in PROFILES:raise ValueError('未知柱端轮廓')
    if profile!='plain' and height<3:raise ValueError('柱端造型至少需要3格高度')
    setting=form.get(key+'_pattern');band=None
    if setting:
        height_uv=pattern_height(setting)
        if height_uv+2>height:raise ValueError('柱端纹样高度加上下收边超过部件高度')
        band=((height-height_uv)//2,(height-height_uv)//2+height_uv-1)
    for level in range(height):
        t=level/(height-1) if height>1 else 0
        # The capital runs the same default section upside down. Explicit
        # Bezier values always run from the part's own bottom to top.
        u=t if key=='base' else 1-t
        if profile=='plain':ratio=1.
        elif profile=='stepped':ratio=1-.38*(int(u*3)/3)
        elif profile=='beveled':ratio=1-.4*u
        elif profile=='torus':ratio=.66+.34*sin(pi*u)
        elif profile=='bell':ratio=.58+.42*(1-u)**2
        else:ratio=(1-t)**3*curve[0]+3*(1-t)**2*t*curve[1]+3*(1-t)*t*t*curve[2]+t**3*curve[3]
        full_band=band is not None and band[0]<=level<=band[1]
        # Terminal abaci and the central core make every layer a supported,
        # solid cross-section; no floating corner beads are introduced.
        if full_band or level in (0,height-1) or profile=='plain':
            box([0,start+level,0],[w-1,start+level,d-1],material);continue
        rx=max(.5,(w-1)*ratio/2);rz=max(.5,(d-1)*ratio/2)
        for x in range(w):
            for z in range(d):
                dx=abs(x-(w-1)/2);dz=abs(z-(d-1)/2)
                inside=(dx/rx)**2+(dz/rz)**2<=1.001 if profile in ('torus','bell','bezier') else dx<=rx and dz<=rz
                if inside or dx<=.5 and dz<=.5:box([x,start+level,z],[x,start+level,z],material)


def decorate_ends(workspace,spec,data,args,parts):
    form=args.get('form',{});settings={part:form[part+'_pattern'] for part in ('base','capital') if part+'_pattern' in form}
    if not settings:return spec,data,{}
    from nbt_pattern.panel import compile_panel
    from nbt_mounting.batch import decorate
    from nbt_structure_agent import build
    w,h,d=spec['size'];entries=[];groups={}
    for part,setting in settings.items():
        pattern=deepcopy(setting['pattern']);pattern.setdefault('surface','wall')
        if pattern.get('surface') not in ('wall','column') or pattern.get('fit_mode','micro')!='micro':raise ValueError('柱端纹样须为wall/column微型拟合')
        pattern['fit_mode']='micro';compiled=compile_panel(workspace,pattern)
        width,height=compiled['spec']['size'][:2];bounds=parts[part];bottom=bounds['lo'][1];span=bounds['hi'][1]-bottom+1
        if width+2>min(w,d) or height+2>span:raise ValueError('柱端纹样须在四角和上下各保留至少1格收边')
        faces=setting.get('faces',['north','east','south','west'])
        if len(set(faces))!=len(faces):raise ValueError('柱端纹样安装面不能重复')
        groups[part]=[]
        for normal in faces:
            surface=dict(north=dict(lo=[0,bottom,0],hi=[w-1,bottom+span-1,0]),south=dict(lo=[0,bottom,d-1],hi=[w-1,bottom+span-1,d-1]),
                         west=dict(lo=[0,bottom,0],hi=[0,bottom+span-1,d-1]),east=dict(lo=[w-1,bottom,0],hi=[w-1,bottom+span-1,d-1]))[normal]
            across=w if normal in ('north','south') else d
            anchor=compiled['spec']['anchor'][0]
            if normal in ('north','east'):anchor=width-1-anchor
            identifier=part+'_'+normal;groups[part].append(identifier)
            entries.append(dict(id=identifier,tool='pattern_mount',surface=dict(surface,normal=normal,opening_margin=0),object=pattern,
                anchor_uv=[(across-width)//2+anchor,(span-height)//2],embed_depth=1))
    # A private air border lets the existing mount planner inspect the outward
    # cell of a face at local zero. All final voxels must remain in the original
    # canvas; installation checks are not bypassed at its boundary.
    padding=[1,0,1];padded_size=[n+2*p for n,p in zip(spec['size'],padding)]
    host=dict(name=spec['name'],size=padded_size,anchor=[0,0,0],max_changed_blocks=65536,
        operations=[dict(kind='paste_component',label='柱端宿主',classification='body',lo=[0,0,0],hi=[n-1 for n in padded_size],
            palette=data['palette'],voxels=[[x+1,y,z+1,index] for x,y,z,index,_ in data['blocks']])])
    for entry in entries:
        for key in ('lo','hi'):entry['surface'][key]=[n+p for n,p in zip(entry['surface'][key],padding)]
    result=decorate(workspace,dict(host=dict(tool='structure',arguments=host),installations=entries,max_changed_blocks=args.get('max_changed_blocks',65536)))
    padded=build(workspace,result['spec']);voxels=[]
    for x,y,z,index,_ in padded['blocks']:
        point=[x-1,y,z-1]
        if not all(0<=n<limit for n,limit in zip(point,spec['size'])):raise ValueError('柱端装饰超出原始画布')
        voxels.append([*point,index])
    final=deepcopy(spec);final['operations']=[dict(kind='paste_component',label='柱子与上下端装饰',classification='body',
        lo=[0,0,0],hi=[n-1 for n in spec['size']],palette=padded['palette'],voxels=voxels)]
    receipts={part:[] for part in groups}
    for row in result['installations']:
        part=row['id'].split('_')[0];placements=deepcopy(row['placements'])
        for placement in placements:
            for key in ('lo','hi'):placement[key]=[n-p for n,p in zip(placement[key],padding)]
            placement['connector_positions']=[[n-offset for n,offset in zip(p,padding)] for p in placement['connector_positions']]
        receipts[part].append(dict(id=row['id'],face=row['id'].split('_')[1],placements=placements,
            pattern=row['pattern'],changed_blocks=row['changed_blocks'],verification=row['verification']))
    return final,build(workspace,final),receipts
