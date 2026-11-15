"""Classical-order cues as connected voxels, not historical reconstruction."""
from copy import deepcopy
from math import atan2,cos,pi,sin
from nbt_model import state,AIR_NAMES
from nbt_collision import collision_cells

ORDERS={
    'tuscan':dict(name='托斯卡纳启发',capital='tuscan',height=3,flutes=False,neck='none'),
    'roman_doric':dict(name='罗马多立克启发',capital='doric',height=4,flutes=True,neck='bead_reel'),
    'ionic':dict(name='爱奥尼启发',capital='ionic',height=8,flutes=True,neck='egg_dart'),
    'corinthian':dict(name='科林斯启发',capital='corinthian',height=10,flutes=True,neck='bead_reel'),
    'composite':dict(name='复合柱式启发',capital='composite',height=12,flutes=True,neck='egg_dart'),
}
CAPITALS={'tuscan','doric','ionic','corinthian','composite'}


def resolve(form,size):
    result=deepcopy(form);order=result.get('order');w,h,d=size
    if order:
        preset=ORDERS[order]
        for key,value in dict(section='round',base_height=4,capital_height=preset['height'],base_profile='attic',
                              capital_profile=preset['capital'],flutes=preset['flutes'],taper=True,shaft_ratio=.78,entasis=.04).items():result.setdefault(key,value)
        result.setdefault('neck_pattern',preset['neck'])
    if result.get('section')!='round' and set(form)&{'shaft_ratio','flute_count','flute_depth','entasis'}:raise ValueError('圆柱身参数需要section=round')
    if not result.get('flutes',False) and set(form)&{'flute_count','flute_depth'}:raise ValueError('凹槽参数需要flutes=true')
    capital=result.get('capital_profile','plain')
    if set(form)&{'leaf_count','leaf_layers'} and capital not in ('corinthian','composite'):raise ValueError('莨苕叶参数需要科林斯或复合柱头')
    if set(form)&{'volute_scale','volute_turns'} and capital not in ('ionic','corinthian','composite'):raise ValueError('涡卷参数需要带涡卷的柱头')
    if set(form)&{'neck_pattern','detail_material'} and capital not in CAPITALS:raise ValueError('颈饰纹样需要古典柱头')
    if (capital in CAPITALS and 'capital_pattern' in result) or (result.get('base_profile')=='attic' and 'base_pattern' in result):raise ValueError('古典柱端使用立体叶饰、涡卷和颈饰；平面嵌纹请显式选通用base_profile/capital_profile')
    if capital not in CAPITALS and 'neck_pattern' not in form:result.pop('neck_pattern',None)
    if result.get('base_profile')=='attic' and result.get('base_height',1)<4:raise ValueError('阿提卡柱础至少4格高')
    if capital in CAPITALS:
        minimum=dict(tuscan=3,doric=4,ionic=7,corinthian=8,composite=10)[capital]
        if result.get('capital_height',1)<minimum or min(w,d)<(9 if capital in ('ionic','corinthian','composite') else 5):
            raise ValueError('当前尺寸不足以表达该柱式柱头，须增加宽深或柱头高度，不会降级为方帽')
    return result


def shaft_level(form,size,level,base,cap,box,material,accent):
    cells,reason=collision_cells(material)
    if reason or len(cells)!=8:raise ValueError('圆柱身主材须为已知完整方块')
    w,h,d=size;cx,cz=(w-1)/2,(d-1)/2
    t=(level-base)/max(1,h-base-cap-1);inset=form.get('inset',1)
    scale=form.get('shaft_ratio',1)*(1-.12*t if form.get('taper',False) else 1)*(1+form.get('entasis',0)*sin(pi*t))
    rx=(cx-inset)*scale;rz=(cz-inset)*scale
    if min(rx,rz)<.75:raise ValueError('圆柱身可用半径不足，须增加宽深或减少inset')
    count=form.get('flute_count',12);depth=form.get('flute_depth',.75)
    if rx>cx+1e-9 or rz>cz+1e-9:raise ValueError('柱身曲率导致半径超出原画布，请减少shaft_ratio或entasis')
    if form.get('flutes',False) and depth>=min(rx,rz):raise ValueError('凹槽深度达到柱身半径，请减小flute_depth')
    for x in range(w):
        for z in range(d):
            dx,dz=x-cx,z-cz;angle=atan2(dz/max(rz,.01),dx/max(rx,.01))
            envelope=1-depth/max(rx,rz)*((1+cos(count*angle))/2)**3 if form.get('flutes',False) else 1
            if (dx/rx)**2+(dz/rz)**2<=envelope**2 or abs(dx)<=.5 and abs(dz)<=.5:
                box([x,level,z],[x,level,z],material)


def classical_end(form,part,size,box,material):
    w,h,d=size;profile=form.get(part+'_profile','plain');height=form.get(part+'_height',1);bottom=0 if part=='base' else h-height
    cx,cz=(w-1)/2,(d-1)/2;occupied=set();detail=state(form.get('detail_material',material))
    if detail in AIR_NAMES:raise ValueError('柱式叶饰与涡卷材质不能是空气')
    for value in (material,detail):
        cells,reason=collision_cells(value)
        if reason or len(cells)!=8:raise ValueError('古典柱端及叶饰材质须为已知完整方块')
    def put(x,y,z,value=None):
        p=(int(x),int(y),int(z))
        if not (0<=p[0]<w and bottom<=p[1]<bottom+height and 0<=p[2]<d):raise ValueError('古典柱端参数导致越界')
        if p in occupied and value is not None:return
        occupied.add(p);box(list(p),list(p),material if value is None else value)
    def connect(a,b,value=None):
        p=list(a);put(*p,value)
        for axis in (1,0,2):
            while p[axis]!=b[axis]:p[axis]+=1 if b[axis]>p[axis] else -1;put(*p,value)
    def disk(level,ratio,square=False):
        for x in range(w):
            for z in range(d):
                dx,dz=abs(x-cx),abs(z-cz)
                if square or (dx/max(.5,cx*ratio))**2+(dz/max(.5,cz*ratio))**2<=1 or dx<=.5 and dz<=.5:put(x,bottom+level,z)
    def ring_decoration():
        motif=form.get('neck_pattern','none')
        if motif=='none':return
        count=max(8,min(24,round(pi*min(w,d)*.55)))
        for i in range(count):
            a=i*2*pi/count;inner=(round(cx+cx*.35*cos(a)),bottom+1,round(cz+cz*.35*sin(a)))
            tip=(round(cx+cx*.64*cos(a)),bottom+1,round(cz+cz*.64*sin(a)))
            connect(inner,tip,detail)
            if motif=='egg_dart' and i%2==0:put(tip[0],bottom+2,tip[2],detail)
            elif motif=='bead_reel' and i%2==0:put(tip[0],bottom,tip[2],detail)
    def volutes(small=False):
        radius=min(w,d)*form.get('volute_scale',.12 if small else .19)
        if 'volute_scale' not in form:radius=min(radius,(height-4)/2)
        radius=max(1.,radius);cy=bottom+height-2-radius
        if cy-radius<bottom+2:raise ValueError('涡卷尺寸超过柱头可用高度，请减少volute_scale或增加capital_height')
        turns=form.get('volute_turns',.9 if small else 1.25)
        for face in range(4):
            across=w if face%2==0 else d;middle=(across-1)/2
            for sign in (-1,1):
                center=middle+sign*(middle-radius)
                def point(u,y):
                    a,b=round(u),round(y)
                    return (a,b,0) if face==0 else (w-1,b,a) if face==1 else (a,b,d-1) if face==2 else (0,b,a)
                previous=None
                for step in range(129):
                    t=step/128;a=pi/2+turns*2*pi*t;r=radius*(1-.8*t)
                    p=point(center+sign*r*cos(a),cy+r*sin(a))
                    if previous:connect(previous,p,detail)
                    else:put(*p,detail)
                    previous=p
                # Each outer top of the scroll meets the solid abacus.
                # Do not fill across its visible centre to fake a connection.
    def leaves():
        count=form.get('leaf_count',8);layers=form.get('leaf_layers',2)
        if height<3+2*layers:raise ValueError('莨苕叶层数超过柱头高度')
        usable=height-(5 if profile=='composite' else 3);length=max(2,usable-(layers-1)*2)
        for tier in range(layers):
            start=bottom+1+tier*2
            for i in range(count):
                a=(i+.5*(tier%2))*2*pi/count;previous=None;centres=[]
                for step in range(length*8+1):
                    t=step/(length*8);r=.36+.53*sin(t*pi/2)-.09*t**6
                    y=start+round(length*t);p=(round(cx+cx*r*cos(a)),y,round(cz+cz*r*sin(a)))
                    if previous:connect(previous,p,detail)
                    else:connect((round(cx),y,round(cz)),p,detail)
                    previous=p;centres.append(p)
                for t in (.35,.58,.78):
                    root=centres[round(t*(len(centres)-1))]
                    for sign in (-1,1):
                        angle=a+sign*(pi/count)*.75;r=.36+.53*sin(t*pi/2)
                        tip=(round(cx+cx*r*cos(angle)),min(bottom+height-2,root[1]+1),round(cz+cz*r*sin(angle)))
                        connect(root,tip,detail)
    if profile=='attic':
        ratios=[1,.94,.61,.83,.53]
        for y in range(height):
            t=y/(height-1)*(len(ratios)-1);i=min(len(ratios)-2,int(t));ratio=ratios[i]+(ratios[i+1]-ratios[i])*(t-i)
            disk(y,ratio,square=y==0)
    else:
        for y in range(height):
            t=y/max(1,height-2)
            ratio=.43+.4*t if profile in ('tuscan','doric') else .4+.26*t
            if profile=='doric' and y<2:ratio=.5+.07*(y%2)
            disk(y,min(.9,ratio),square=y==height-1)
        ring_decoration()
        if profile in ('corinthian','composite'):leaves()
        if profile in ('ionic','composite','corinthian'):volutes(small=profile=='corinthian')
    # Sparse leaves and scrolls must actually join the generated bell/plinth.
    seen={next(iter(occupied))};pending=list(seen)
    while pending:
        x,y,z=pending.pop()
        for p in ((x-1,y,z),(x+1,y,z),(x,y-1,z),(x,y+1,z),(x,y,z-1),(x,y,z+1)):
            if p in occupied and p not in seen:seen.add(p);pending.append(p)
    if seen!=occupied:raise ValueError('古典柱端出现未连接细节，须调整尺寸或纹样参数')
