"""Coupled architectural bays, recessed vault skins and real open tracery.

Pure candidates only. Geometry is generated in one shared coordinate system;
no script, saved model or author approval is accepted from tool arguments.
"""
from collections import deque
from copy import deepcopy
from math import ceil,cos,floor,hypot,pi,sin,sqrt

from nbt_collision import collision_cells
from nbt_model import state,AIR_NAMES

SIX=((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))


def curve(t,profile='pointed'):
    t=min(1.,abs(t))
    return sqrt(max(0.,1-t*t)) if profile=='round' else sqrt(max(0.,2.25-(t+.5)**2))/sqrt(2.)


def full(value):
    value=state(value);cells,reason=collision_cells(value)
    if reason or len(cells)!=8:raise ValueError('建筑构造材质须为已知完整方块')
    return value


class Writer:
    def __init__(self,size):self.size=list(size);self.blocks={};self.parts={};self.walls=set()
    def put(self,p,value,part,wall=False):
        p=tuple(p)
        if not all(type(n) is int and 0<=n<limit for n,limit in zip(p,self.size)):raise ValueError('建筑构造超出原画布')
        if value in AIR_NAMES:raise ValueError('建筑候选不接受空气写入')
        self.blocks[p]=value;self.parts.setdefault(part,set()).add(p)
        if wall:self.walls.add(p)
        else:self.walls.discard(p)
    def box(self,lo,hi,value,part,wall=False):
        for x in range(lo[0],hi[0]+1):
            for y in range(lo[1],hi[1]+1):
                for z in range(lo[2],hi[2]+1):self.put((x,y,z),value,part,wall)
    def path(self,points,value,part,wall=False):
        # Dense sampling followed by face-connected quantization. A diagonal
        # centreline alone is insufficient support for a one-block moulding.
        previous=None
        for point in points:
            p=[round(v) for v in point]
            if previous is not None:
                q=list(previous)
                for axis in (1,0,2):
                    while q[axis]!=p[axis]:q[axis]+=1 if p[axis]>q[axis] else -1;self.put(q,value,part,wall)
            self.put(p,value,part,wall);previous=p
    def insert(self,data,origin,part):
        for x,y,z,index,wall in data['blocks']:self.put((x+origin[0],y+origin[1],z+origin[2]),data['palette'][index],part,wall)


def component_count(points):
    remaining=set(points);count=0
    while remaining:
        count+=1;pending=[remaining.pop()]
        while pending:
            x,y,z=pending.pop()
            for q in ((x-1,y,z),(x+1,y,z),(x,y-1,z),(x,y+1,z),(x,y,z-1),(x,y,z+1)):
                if q in remaining:remaining.remove(q);pending.append(q)
    return count


def contacts(writer,a,b):
    # Inspect actual final half-cubes at the authored memberships. Later trim
    # may replace material but cannot manufacture a contact certificate.
    def cells(part):
        result=set()
        for p in writer.parts[part]:
            occupied,reason=collision_cells(writer.blocks[p])
            if reason:raise ValueError('建筑接触检查遇到未知碰撞形状')
            result.update(tuple(2*p[i]+cell[i] for i in range(3)) for cell in occupied)
        return result
    first,second=cells(a),cells(b)
    return bool(first&second) or any(tuple(p[i]+delta[i] for i in range(3)) in second for p in first for delta in SIX)


def finish(workspace,writer,args,name,**receipt):
    from nbt_agent.structure import build
    from nbt_pattern.panel import sample_input
    from nbt_pattern.ornament_sample import sample_image
    for request in receipt.pop('_bound_patterns',[]):
        root,sample=sample_input(workspace,request);sample_image(root,sample)
    if len(writer.blocks)>args.get('max_changed_blocks',65536):raise ValueError('建筑构造超过方块预算')
    palette=sorted(set(writer.blocks.values()));indices={v:i for i,v in enumerate(palette)};operations=[]
    for wall in (False,True):
        voxels=[[*p,indices[v]] for p,v in sorted(writer.blocks.items()) if (p in writer.walls)==wall]
        if voxels:operations.append(dict(kind='paste_component',label=name,classification='wall' if wall else 'body',lo=[0,0,0],hi=[n-1 for n in writer.size],palette=palette,voxels=voxels))
    spec=dict(name=args.get('name',name),size=writer.size,anchor=[writer.size[0]//2,0,0],max_changed_blocks=args.get('max_changed_blocks',65536),operations=operations,tags=['architectural',receipt.get('kind','bay')])
    data=build(workspace,spec)
    bounds={part:dict(lo=[min(p[i] for p in points) for i in range(3)],hi=[max(p[i] for p in points) for i in range(3)]) for part,points in writer.parts.items() if points}
    return dict(spec=spec,parts=bounds,content_sha256=data['content_sha256'],block_count=len(writer.blocks),model_modified=False,approval_created=False,
        verification=dict(block_states=True,bounds=True,budget=True,design='pending_visual_review',structural_load='not_checked',game='not_checked'),**receipt)


def compile_tracery(workspace,args):
    w,h=args['size_uv'];depth=args.get('depth',3)
    if w<11 or h<15:raise ValueError('真实窗棂至少11×15格，较小纹样请使用平面微型拟合')
    material=full(args.get('material','stone_bricks'));trim=full(args.get('trim','polished_andesite'));profile=args.get('profile','pointed')
    glass=[full(v) for v in args.get('glass_palette',['blue_stained_glass','cyan_stained_glass','yellow_stained_glass'])]
    if any('glass' not in v for v in glass):raise ValueError('窗棂玻璃配色须为已知完整玻璃方块')
    writer=Writer([w,h,depth]);cx=(w-1)/2;a=cx-1;spring=round((h-1)*.53);rise=h-2-spring
    height=lambda x:spring+rise*curve((x-cx)/a,profile)
    aperture={(x,y) for x in range(1,w-1) for y in range(1,h-1) if y<=height(x)}
    for z in range(depth):
        # The two side jambs and sill are real members, not an opaque plate.
        for x in (0,1,w-2,w-1):writer.box([x,0,z],[x,spring,z],material,'frame')
        writer.box([0,0,z],[w-1,0,z],trim,'frame')
        points=[(cx-a+2*a*t/128,spring+rise*curve(-1+2*t/128,profile),z) for t in range(129)]
        writer.path(points,material if z else trim,'frame')
    plane=0;root=1
    # Pair of lancets, a central stem and a rose with four connecting spokes.
    lancet_spring=max(4,round(h*.34));lancet_rise=max(3,round(h*.23));radius=max(1.5,min((w-5)/5,(h-6)/7))
    rose_y=min(h-4-radius,lancet_spring+lancet_rise+radius*.65)
    for centre in (cx-a/2,cx+a/2):
        half=a/2
        for x in (centre-half,centre+half):writer.path([(x,root,plane),(x,lancet_spring,plane)],trim,'mullions')
        writer.path([(centre-half+2*half*t/96,lancet_spring+lancet_rise*curve(-1+2*t/96,profile),plane) for t in range(97)],trim,'mullions')
    writer.path([(cx,1,plane),(cx,rose_y-radius,plane)],trim,'mullions')
    writer.path([(cx+radius*cos(t*2*pi/128),rose_y+radius*sin(t*2*pi/128),plane) for t in range(129)],trim,'rose')
    for sign in (-1,1):
        x=cx+sign*radius
        writer.path([(x,rose_y,plane),(cx+sign*(a-.5),min(height(cx+sign*(a-.5)),rose_y),plane)],trim,'rose_links')
    writer.path([(cx,rose_y+radius,plane),(cx,height(cx),plane)],trim,'rose_links')
    before=len(writer.blocks);glazing=args.get('glazing',True);glass_cells=0
    for x,y in aperture:
        # Only cells inside the pointed opening receive glass. All other air
        # remains air; no solid backing is made even in the glazed variant.
        if glazing and (x,y,min(1,depth-1)) not in writer.blocks:
            # Colour zones follow the paired lancets and central rose; do not
            # introduce unrelated stripes through the architectural members.
            sector=(2 if hypot(x-cx,y-rose_y)<=radius-.5 else (0 if x<=cx else 1))%len(glass)
            writer.put((x,y,min(1,depth-1)),glass[sector],'glazing');glass_cells+=1
    open_cells=sum(not any((x,y,z) in writer.blocks for z in range(depth)) for x,y in aperture)
    frame_points={p for part,points in writer.parts.items() if part!='glazing' for p in points}
    if component_count(frame_points)!=1:raise ValueError('窗棂存在未连接构件，请增加尺寸或调整比例')
    result=finish(workspace,writer,args,'拱窗透空窗棂',kind='tracery',tracery=dict(aperture_cells=len(aperture),open_cells=open_cells,glass_cells=glass_cells,opaque_backing=False,frame_face_connected=True,glazing=glazing),resolved_form=dict(spring_y=spring,rise=rise,rose_radius=radius,profile=profile))
    return result


def facade_materials(args):
    material = full(args.get('material', 'bricks'))
    trim = full(args.get('trim', 'smooth_sandstone'))
    glass = full(args.get('glass', 'glass'))
    if 'glass' not in glass:
        raise ValueError('窗墙玻璃须为已知完整玻璃方块')
    sill = state(args.get('sill_material', 'sandstone_slab[type=bottom]'))
    occupied, reason = collision_cells(sill)
    if reason or set(occupied) != {(x, 0, z) for x in (0, 1) for z in (0, 1)}:
        raise ValueError('窗台材质须为受支持的下半砖')
    return material, trim, glass, sill


def compile_facade(workspace, args):
    """Compile the fixed count facade or resolve a contextual width first."""
    if 'contextual' in args:
        from nbt_building.contextual_facade import compile_contextual_facade
        return compile_contextual_facade(workspace, args)
    bays, storeys = args.get('bays', 3), args.get('storeys', 2)
    opening_width, opening_height = args.get('opening', [3, 4])
    pier = args.get('pier_width', 2)
    sill_height = args.get('sill_height', 2)
    lintel_height = args.get('lintel_height', 1)
    recess = args.get('recess', 1)
    pitch = sill_height + opening_height + lintel_height
    width = bays * opening_width + (bays + 1) * pier
    height = storeys * pitch
    depth = recess + 2
    if max(width, height) > 64:
        raise ValueError('单个窗墙构件宽高最多64格，请按实际跨间组合')
    material, trim, glass, sill = facade_materials(args)
    writer = Writer([width, height, depth])
    openings = []
    for storey in range(storeys):
        base = storey * pitch
        for bay in range(bays):
            left = pier + bay * (opening_width + pier)
            bottom = base + sill_height
            openings.append(dict(
                id=f'window_{storey}_{bay}',
                lo=[left, bottom, 0],
                hi=[left + opening_width - 1, bottom + opening_height - 1, depth - 1],
            ))
        for x in range(width):
            inside_window = x >= pier and (x - pier) // (opening_width + pier) < bays
            inside_window = inside_window and (x - pier) % (opening_width + pier) < opening_width
            for y in range(base, base + pitch):
                if inside_window and base + sill_height <= y < base + sill_height + opening_height:
                    continue
                writer.box([x, y, 1], [x, y, depth - 1], material, 'wall', True)
        writer.box([0, base, 0], [width - 1, base, 0], trim, 'storey_bands', True)
    for opening in openings:
        left, bottom, _ = opening['lo']
        right, top, _ = opening['hi']
        for x in (left - 1, right + 1):
            writer.box([x, bottom, 0], [x, top, 0], trim, 'jambs', True)
        writer.box([left - 1, top + 1, 0], [right + 1, top + 1, 0], trim, 'lintels', True)
        writer.box([left - 1, bottom - 1, 0], [right + 1, bottom - 1, 0], sill, 'sills', True)
        if args.get('glazing', True):
            writer.box([left, bottom, recess], [right, top, recess], glass, 'glazing', True)
    return finish(workspace, writer, args, '凹窗与层带立面', kind='facade',
                  openings=openings, front='north_-z', glazing=args.get('glazing', True),
                  resolved_form=dict(bays=bays, storeys=storeys, opening=[opening_width, opening_height],
                                     pier_width=pier, storey_pitch=pitch, recess=recess))


def vault_field(w,d,spring,rise,profile):
    return {(x,z):spring+rise*max(curve(2*x/(w-1)-1,profile),curve(2*z/(d-1)-1,profile)) for x in range(w) for z in range(d)}


def compile_vault(workspace,args):
    from nbt_agent.structure import dispatch,build
    w,d=args['size_xz'];spring=args['spring_y'];rise=args['rise'];thickness=args.get('thickness',2);recess=args.get('recess_depth',2)
    counts=args.get('coffer_counts',[3,3]);columns,rows=counts
    if min(w//columns,d//rows)<4:raise ValueError('凹格单元至少4格；应减小分格数量或增大跨间')
    profile=args.get('profile','pointed');material=full(args.get('material','smooth_quartz'));rib=full(args.get('rib_material','stone_bricks'))
    recess_material=full(args.get('recess_material','polished_andesite'))
    slab=state(args.get('slab_material','smooth_quartz_slab[type=top,waterlogged=false]'))
    cells,reason=collision_cells(slab)
    if reason or set(cells)!={(x,1,z) for x in (0,1) for z in (0,1)}:raise ValueError('券顶半格量化须使用已知顶半砖')
    recess_slab=state(args.get('recess_slab_material','polished_andesite_slab[type=top,waterlogged=false]'))
    cells,reason=collision_cells(recess_slab)
    if reason or set(cells)!={(x,1,z) for x in (0,1) for z in (0,1)}:raise ValueError('凹格半格量化须使用已知顶半砖')
    field=vault_field(w,d,spring,rise,profile);size=[w,ceil(spring+rise+recess+thickness)+3,d]
    if max(size)>64:raise ValueError('券顶画布每轴最多64格')
    writer=Writer(size);coffer=args.get('coffer_pattern',dict(preset='roman-coffer'));source=dict(coffer,surface='ceiling',size_uv=[8,8],material='quartz_block')
    compiled=dispatch(workspace,'pattern_compile',source);data=build(workspace,compiled['spec']);motif={(x,z) for x,y,z,_,_ in data['blocks'] if y==0}
    depths={};half_quantized=0
    for x in range(w):
        for z in range(d):
            # Parameter-space cells follow the curved skin. The outer solid
            # cover is independent of the recess, retaining structural depth.
            u=x*columns/w;v=z*rows/d;fu=u%1;fv=v%1
            edge=min(fu,1-fu,fv,1-fv);step=min(recess,int(edge*2*(recess+1)))
            sample=(min(7,int(fu*8)),min(7,int(fv*8)))
            if sample in motif:step=max(0,step-1)
            if x in (0,w-1) or z in (0,d-1):step=0
            depths[x,z]=step
            level=round(2*(field[x,z]+step))/2;low=floor(level)
            top=ceil(max(field.get((x+dx,z+dz),field[x,z]) for dx,dz in ((0,0),(-1,0),(1,0),(0,-1),(0,1)))+recess+thickness)
            for y in range(low,top+1):
                value=(recess_slab if step else slab) if y==low and level!=low else recess_material if y==low and step else material
                writer.put((x,y,z),value,'vault_shell')
            half_quantized+=level!=low
    if args.get('ribs',True):
        for sx,sz in ((0,0),(w-1,0),(0,d-1),(w-1,d-1)):
            points=[]
            for i in range(129):
                t=i/128;x=sx+(w-1-2*sx)*t/2;z=sz+(d-1-2*sz)*t/2
                y=spring+rise*curve(2*x/(w-1)-1,profile)-.5
                points.append((x,y,z))
            writer.path(points,rib,'diagonal_ribs')
            writer.path([(x,y+1,z) for x,y,z in points],rib,'diagonal_ribs')
        if not contacts(writer,'diagonal_ribs','vault_shell'):raise ValueError('券顶肋架未连接实际壳体')
    return finish(workspace,writer,args,'曲面凹格交叉券顶',kind='vault',resolved_form=dict(spring_y=spring,rise=rise,profile=profile,coffer_counts=counts,recess_depth=recess),
        vault=dict(coffer_depth_range=[min(depths.values()),max(depths.values())],half_slab_surface_cells=half_quantized,skin_mapping='shared_arch_parameter_field',cover_thickness=thickness,ribs_attached=args.get('ribs',True),pattern_sha256=compiled['sample_sha256']),_bound_patterns=[source])


def arch_moulding(writer,axis,constant,low,high,spring,rise,profile,material,trim,part):
    # Ordered stepped sections follow one shared normal field; all samples
    # keep their phase through the crown. Caps coincide with pier springing.
    for offset,depth in ((0,3),(1,2),(2,1)):
        points=[]
        for i in range(257):
            u=low+(high-low)*i/256;t=-1+2*i/256
            delta=1e-4;df=(curve(min(1,t+delta),profile)-curve(max(-1,t-delta),profile))/(min(1,t+delta)-max(-1,t-delta))
            dx=(high-low)/2;dy=rise*df;length=hypot(dx,dy);nx,ny=-dy/length,dx/length
            a=u+offset*nx;y=spring+rise*curve(t,profile)+offset*ny
            points.append((a,y,constant) if axis=='x' else (constant,y,a))
        for layer in range(depth):
            shifted=[(x,y,z-layer) if axis=='x' else (x-layer,y,z) for x,y,z in points]
            writer.path(shifted,trim if offset==1 else material,part)


def compile_bay(workspace,args):
    from nbt_agent.structure import dispatch,build
    span=args.get('span',20);depth=args.get('depth',20);p=args.get('pier_width',5);spring=2+args.get('spring_height',12);rise=args.get('rise',12);profile=args.get('profile','pointed')
    materials=args.get('materials',{});stone=full(materials.get('stone','stone_bricks'));trim=full(materials.get('trim','polished_andesite'));accent=full(materials.get('accent','quartz_block'));wall=full(materials.get('wall','calcite'));floor_base=full(materials.get('floor','polished_deepslate'))
    left=2+p-1;right=left+span+1;front=4;back=front+depth+1
    vault_args=dict(size_xz=[span+2,depth+2],spring_y=spring,rise=rise,profile=profile,thickness=args.get('vault_thickness',2),recess_depth=args.get('recess_depth',2),coffer_counts=args.get('coffer_counts',[3,3]),coffer_pattern=args.get('coffer_pattern',dict(preset='roman-coffer')),material=materials.get('vault','smooth_quartz'),rib_material=stone)
    vault=dispatch(workspace,'vault_compile',vault_args);vdata=build(workspace,vault['spec'])
    writer=Writer([span+2*p+4,vault['spec']['size'][1],back+4]);writer.box([0,0,0],[writer.size[0]-1,1,writer.size[2]-1],floor_base,'floor')
    palette=[full(v) for v in args.get('inlay_palette',['quartz_block','red_terracotta','yellow_terracotta'])]
    source=dict(args.get('floor_pattern',dict(preset='byzantine-cross-mosaic')),surface='floor',size_uv=[span,depth],material=palette[0],base=floor_base)
    floor_pattern=dispatch(workspace,'pattern_compile',source);fdata=build(workspace,floor_pattern['spec'])
    for x,y,z,index,_ in fdata['blocks']:
        value=fdata['palette'][index]
        if value!=floor_base:
            # Explicit geometric colour roles, never random dithering. Keep
            # all floor states full and flush with the walking surface.
            r=hypot((x-(span-1)/2)/span,(z-(depth-1)/2)/depth)
            value=palette[min(len(palette)-1,int(r*len(palette)*2))]
        writer.put((left+1+x,1,front+1+z),value,'floor_inlay')
    for x0 in (2,2+p+span):
        for z0 in (front,back-p+1):
            part=f'pier_{x0}_{z0}'
            writer.box([x0,2,z0],[x0+p-1,3,z0+p-1],trim,part)
            writer.box([x0+1,4,z0+1],[x0+p-2,spring-3,z0+p-2],stone,part)
            for x,z in ((x0,z0+1),(x0+1,z0),(x0+p-1,z0+1),(x0+p-2,z0),(x0,z0+p-2),(x0+1,z0+p-1),(x0+p-1,z0+p-2),(x0+p-2,z0+p-1)):
                writer.box([x,4,z],[x,spring-3,z],accent,part)
            writer.box([x0+1,spring-2,z0+1],[x0+p-2,spring-2,z0+p-2],accent,part)
            writer.box([x0,spring-1,z0],[x0+p-1,spring,z0+p-1],trim,part)
    writer.insert(vdata,[left,0,front],'vault')
    for axis,constant,lo,hi,part in [('x',front,left,right,'front_arch'),('x',back+2,left,right,'back_arch'),('z',left,front,back,'left_arch'),('z',right+2,front,back,'right_arch')]:
        arch_moulding(writer,axis,constant,lo,hi,spring,rise,profile,stone,accent,part)
    # Low wall panels retain the piers' divisions and leave side arches open.
    for x in (left-1,right+1):
        writer.box([x,2,front+p],[x,5,back-p],wall,'dado',True)
        writer.box([x,6,front+p],[x,6,back-p],trim,'dado_trim')
    ww=min(21,span-3);ww-=1-ww%2;wh=min(31,spring+rise-4);x0=(writer.size[0]-ww)//2;y0=4
    tracery_args=dict(size_uv=[ww,wh],depth=3,profile=profile,material=stone,trim=accent,glazing=args.get('glazing',True),glass_palette=args.get('glass_palette',['blue_stained_glass','cyan_stained_glass','yellow_stained_glass']))
    window=dispatch(workspace,'tracery_compile',tracery_args);window_data=build(workspace,window['spec'])
    wspring=window['resolved_form']['spring_y'];wrise=window['resolved_form']['rise'];cx=(ww-1)/2;half=cx-1
    for x in range(left,right+1):
        top=floor(spring+rise*curve(2*(x-left)/(right-left)-1,profile))
        for y in range(2,top+1):
            local_x=x-x0;local_y=y-y0
            aperture=(0<=local_x<ww and 0<=local_y<wh and (local_y<=wspring or local_y<=wspring+wrise*curve((local_x-cx)/half,profile)))
            if not aperture:writer.box([x,y,back],[x,y,back+2],wall,'back_wall',True)
    writer.insert(window_data,[x0,y0,back],'window')
    # The front/back moulding bands share actual springing with the piers.
    pairs=[('floor',part) for part in writer.parts if part.startswith('pier_')]
    pairs += [('vault','front_arch'),('vault','back_arch'),('vault','left_arch'),('vault','right_arch'),('back_wall','window')]
    pairs += [('vault',part) for part in writer.parts if part.startswith('pier_')]
    joints=[dict(first=a,second=b,face_contact=contacts(writer,a,b)) for a,b in pairs]
    if not all(row['face_contact'] for row in joints):raise ValueError('跨间构造节点未连接：'+str([row for row in joints if not row['face_contact']]))
    if component_count(writer.blocks)!=1:raise ValueError('单跨存在未连接的实体构件')
    return finish(workspace,writer,args,'苍金四叶纹回廊·单跨',kind='bay',resolved_form=dict(span=span,depth=depth,pier_width=p,spring_y=spring,rise=rise,profile=profile,window_size=[ww,wh]),
        construction_graph=dict(driver_fields=['span','depth','spring_height','rise','pier_width'],joints=joints,connectivity='actual_final_halfcube_faces'),
        vault=vault['vault'],tracery=window['tracery'],floor=dict(pattern_sha256=floor_pattern['sample_sha256'],palette=palette,flush=True),
        recipes=dict(vault=vault_args,window=tracery_args,floor=source),_bound_patterns=[source,dict(vault_args.get('coffer_pattern',{}),surface='ceiling',size_uv=[8,8])])
