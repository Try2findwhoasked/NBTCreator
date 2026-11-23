"""Pure bounded implicit-field candidates with composable inverse deformations."""
import numpy as np
from nbt_geometry.deform import coordinates,validate_transforms


def graph_nodes(args):
    nodes={n['id']:n for n in args['nodes']}
    if len(nodes)!=len(args['nodes']) or args['root'] not in nodes:raise ValueError('体场ID重复或root缺失')
    pending=set();visited=set()
    fields={'box':{'min','max'},'ellipsoid':{'centre','radii'},'cylinder':{'centre','radius','height','axis'},'torus':{'centre','major_radius','minor_radius'},
        'superellipsoid':{'centre','radii','power'},'gyroid':{'wavelength','thickness','centre'},'union':{'children'},'intersection':{'children'},'difference':{'children'},'smooth_union':{'children','blend'}}
    required={'box':{'min','max'},'ellipsoid':{'centre','radii'},'cylinder':{'centre','radius','height'},'torus':{'centre','major_radius','minor_radius'},
        'superellipsoid':{'centre','radii','power'},'gyroid':{'wavelength','thickness'}}
    def visit(id,depth=0):
        if depth>16 or id in pending:raise ValueError('体场依赖循环或超过16层')
        if id not in nodes:raise ValueError('体场引用不存在：'+id)
        if id in visited:return
        n=nodes[id];kind=n['shape']
        validate_transforms(n.get('transforms',[]))
        if set(n)-({'id','shape','transforms'}|fields[kind]) or not required.get(kind,set())<=set(n):raise ValueError('体场参数与shape不匹配：'+id)
        if kind=='box' and any(a>=b for a,b in zip(n['min'],n['max'])):raise ValueError('box须min<max')
        if kind in ('ellipsoid','superellipsoid') and min(n['radii'])<=0:raise ValueError('radii须为正')
        if kind in ('union','intersection','difference','smooth_union'):
            children=n.get('children',[])
            if len(children)<2 or kind in ('difference','smooth_union') and len(children)!=2:raise ValueError('布尔/平滑组合子场数量无效')
            if kind=='smooth_union' and n.get('blend',0)<=0:raise ValueError('smooth_union须为正blend')
            pending.add(id)
            for child in children:visit(child,depth+1)
            pending.remove(id)
        visited.add(id)
    visit(args['root'])
    if visited!=set(nodes):raise ValueError('存在未使用的体场节点，请删除或接入root')
    # DAG reuse can still expand exponentially. Account actual evaluation work.
    from functools import lru_cache
    @lru_cache(maxsize=32)
    def cost(id):return 1+len(nodes[id].get('transforms',[]))+sum(cost(c) for c in nodes[id].get('children',[]))
    validate_transforms(args.get('transforms',[]))
    work=cost(args['root'])+len(args.get('transforms',[]))
    if work*np.prod(args['size'])>32_000_000:raise ValueError('体场采样工作量超过3200万，请减少节点或画布')
    return nodes,work


def evaluate(points,nodes,root,xp):
    n=nodes[root];q=coordinates(points,n.get('transforms',[]),xp);kind=n['shape']
    if 'children' in n:
        values=[evaluate(q,nodes,c,xp) for c in n['children']]
        if kind=='difference':return xp.maximum(values[0],-values[1])
        if kind=='smooth_union':
            a,b=values;r=n['blend'];t=xp.clip(.5+.5*(b-a)/r,0,1)
            return b*(1-t)+a*t-r*t*(1-t)
        result=values[0]
        for v in values[1:]:result=(xp.minimum if kind=='union' else xp.maximum)(result,v)
        return result
    c=n.get('centre',[0,0,0]);v=[q[i]-c[i] for i in range(3)]
    if kind=='box':
        return xp.maximum(xp.maximum(n['min'][0]-q[0],q[0]-n['max'][0]),xp.maximum(xp.maximum(n['min'][1]-q[1],q[1]-n['max'][1]),xp.maximum(n['min'][2]-q[2],q[2]-n['max'][2])))
    if kind in ('ellipsoid','superellipsoid'):
        r=n['radii'];power=n.get('power',2)
        return ((sum(xp.abs(v[i]/r[i])**power for i in range(3)))**(1/power)-1)*min(r)
    if kind=='cylinder':
        axis='xyz'.index(n.get('axis','y'))
        return xp.maximum(xp.sqrt(sum(v[i]**2 for i in range(3) if i!=axis))-n['radius'],xp.abs(v[axis])-n['height']/2)
    if kind=='torus':return xp.sqrt((xp.sqrt(v[0]**2+v[2]**2)-n['major_radius'])**2+v[1]**2)-n['minor_radius']
    if kind=='gyroid':
        from math import tau
        x,y,z=[a*tau/n['wavelength'] for a in v]
        return xp.abs(xp.sin(x)*xp.cos(y)+xp.sin(y)*xp.cos(z)+xp.sin(z)*xp.cos(x))-n['thickness']
    raise ValueError('未知体场形状')


def sample(args):
    from nbt_compute import execute
    nodes,work=graph_nodes(args);size=args['size'];transforms=args.get('transforms',[])
    def calculate(xp):
        points=[xp.arange(size[0],dtype=xp.float64)[:,None,None]+.5,xp.arange(size[1],dtype=xp.float64)[None,:,None]+.5,xp.arange(size[2],dtype=xp.float64)[None,None,:]+.5]
        return xp.broadcast_to(evaluate(coordinates(points,transforms,xp),nodes,args['root'],xp),size)
    values,compute=execute(args.get('backend','auto'),np.prod(size)*work>=1_000_000,calculate,estimated_bytes=int(np.prod(size))*512)
    # GPU arithmetic may fuse operations. Resolve boundary decisions with the
    # CPU definition so tiny numeric differences cannot add/delete voxels.
    near=np.argwhere(np.abs(values)<1e-7)
    if compute['actual']=='gpu' and len(near):
        points=[near[:,i].astype(float)+.5 for i in range(3)]
        resolved=evaluate(coordinates(points,transforms,np),nodes,args['root'],np)
        values[tuple(near.T)]=resolved
    compute['cpu_boundary_samples']=len(near) if compute['actual']=='gpu' else 0
    return values<=0,compute


def compile_field(workspace,args):
    from nbt_structure_agent import build
    from nbt_collision import collision_cells
    from nbt_model import state
    material=state(args.get('material','stone_bricks'));occupied,reason=collision_cells(material)
    if reason or len(occupied)!=8:raise ValueError('体场生成材质须为已知完整方块；不任意扭曲楼梯/半砖状态')
    mask,compute=sample(args);points=np.argwhere(mask)
    if not len(points):raise ValueError('体场采样结果为空，请检查画布和变换')
    budget=args.get('max_changed_blocks',65536)
    if len(points)>budget:raise ValueError('体场超过方块预算')
    size=args['size'];spec=dict(name=args.get('name','变换体场构件'),size=size,anchor=[size[0]//2,0,0],max_changed_blocks=budget,
        operations=[dict(kind='paste_component',label='体场采样',classification=args.get('classification','body'),lo=[0,0,0],hi=[v-1 for v in size],palette=[material],voxels=[p+[0] for p in points.tolist()])])
    data=build(workspace,spec)
    return dict(spec=spec,block_count=len(points),content_sha256=data['content_sha256'],compute=compute,recipe=dict(tool='field_compile',arguments=args),model_modified=False,approval_created=False,
        verification=dict(bounds=True,block_states=True,budget=True,design='pending_visual_review',connectivity='not_checked',structural_load='not_checked',game='not_checked'),
        sampling=dict(position='voxel_centres',domain='explicit_canvas',distance='sign_correct_fields_not_general_exact_sdf',transform_order='forward_list_inverse_sampling'))
