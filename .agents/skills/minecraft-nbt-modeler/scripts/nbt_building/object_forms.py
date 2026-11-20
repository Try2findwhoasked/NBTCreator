"""Optional forms for parameterized objects. Legacy requests retain their geometry."""
from nbt_model import state, AIR_NAMES
from nbt_registry import effective
import random


THEMES={
    'stone_hall':dict(material='stone_bricks',accent='chiseled_stone_bricks',spacing=4),
    'timber_room':dict(material='spruce_planks',accent='dark_oak_planks',spacing=3),
    'deepslate_workshop':dict(material='deepslate_bricks',accent='polished_blackstone',spacing=4),
}
FORM_FIELDS={
    'pillar':('base_height','capital_height','inset','base_material','capital_material','section','taper','flutes','base_profile','capital_profile','base_curve','capital_curve','base_pattern','capital_pattern','order','shaft_ratio','flute_count','flute_depth','entasis','neck_pattern','leaf_count','leaf_layers','volute_scale','volute_turns','detail_material'),
    'wall':('base_height','dado_height','cornice_height','panel_pitch','relief_depth'),
    'ceiling':('profile','drop','pitch','border','light_strip'),
    'plant':('profile','pot_height','crown_height','radius','density','seed'),
    'planter':('profile','pot_height','crown_height','radius','density','seed'),
    'stairs':('profile','run_width','rise','landing','tread','rail','handrail'),
}
from nbt_building.modular_objects import FIELDS as MODULAR_FIELDS, PROFILES as MODULAR_PROFILES
FORM_FIELDS.update(MODULAR_FIELDS)
FORM_FIELDS['pillar'] += ('band_spacing','shaft_inset')
PROFILES={'ceiling':('grid','parallel'),'plant':('upright','trailing','climbing'),
          'planter':('upright','trailing','climbing'),'stairs':('straight','quarter_turn','switchback','spiral')}
PROFILES.update(MODULAR_PROFILES)


def generate(kind, spec, size, box, primary, accent, foliage, style='classic'):
    if kind not in FORM_FIELDS or set(spec)-set(FORM_FIELDS[kind]):
        raise ValueError('form 含不适用于该构件的参数')
    if 'profile' in spec and spec['profile'] not in PROFILES.get(kind,()):
        raise ValueError('form.profile 不适用于该构件')
    if kind in MODULAR_FIELDS:
        from nbt_building.modular_objects import generate as modular_generate
        return modular_generate(kind,spec,size,box,primary,accent,style)
    w,h,d=size
    x,y,z=w-1,h-1,d-1
    cx,cz=x//2,z//2
    parts={}
    if kind=='pillar':
        base,cap=spec.get('base_height',1),spec.get('capital_height',1)
        inset=spec.get('inset',1)
        if base+cap>=h or 2*inset>=min(w,d):
            raise ValueError('柱础、柱头或柱身收分超过构件尺寸')
        shaft_inset=spec.get('shaft_inset',1)
        if 'shaft_inset' in spec and spec.get('section')=='round':
            raise ValueError('圆柱用inset控制半径；shaft_inset用于方形等非圆截面')
        if 2*shaft_inset>=min(w,d):raise ValueError('柱身留边没有留下有效截面')
        from nbt_building.pillar_ends import end_layers
        end_layers(spec,'base',size,box,state(spec.get('base_material',accent)))
        end_layers(spec,'capital',size,box,state(spec.get('capital_material',accent)))
        for level in range(base,h-cap):
            if spec.get('section')=='round':
                from nbt_building.classical_column import shaft_level
                band=spec.get('band_spacing') and (level-base)%spec['band_spacing']==0
                shaft_level(spec,size,level,base,cap,box,accent if band else primary,accent);continue
            offset=inset if spec.get('taper',False) and level>=base+(h-base-cap)//2 else 0
            if 2*(shaft_inset+offset)>=min(w,d):
                raise ValueError('柱身收分后没有可用截面')
            lo=[shaft_inset+offset,level,shaft_inset+offset];hi=[x-shaft_inset-offset,level,z-shaft_inset-offset]
            section=spec.get('section','square')
            shaft_material=accent if spec.get('band_spacing') and (level-base)%spec['band_spacing']==0 else primary
            if section in ('octagonal','bundled'):
                rx,rz=(hi[0]-lo[0])/2,(hi[2]-lo[2])/2
                mx,mz=(lo[0]+hi[0])/2,(lo[2]+hi[2])/2
                if min(rx,rz)<1:raise ValueError('八角或束柱截面至少需要5格宽深')
                for a in range(lo[0],hi[0]+1):
                    for b in range(lo[2],hi[2]+1):
                        dx,dz=abs(a-mx)/rx,abs(b-mz)/rz
                        keep=dx+dz<=1.5 if section=='octagonal' else dx<=.4 or dz<=.4 or (dx<=.8 and dz<=.8)
                        if keep:box([a,level,b],[a,level,b],shaft_material)
            elif section=='cross':
                box([cx,level,lo[2]],[cx,level,hi[2]],shaft_material)
                box([lo[0],level,cz],[hi[0],level,cz],shaft_material)
            else:
                box(lo,hi,shaft_material)
            if spec.get('flutes',False):
                box([cx,level,lo[2]],[cx,level,lo[2]],accent)
                box([cx,level,hi[2]],[cx,level,hi[2]],accent)
        parts={'base':([0,0,0],[x,base-1,z]),'shaft':([0,base,0],[x,h-cap-1,z]),'capital':([0,h-cap,0],[x,y,z])}
    elif kind=='wall':
        base=spec.get('base_height',1)
        dado=spec.get('dado_height',h//2)
        cornice=spec.get('cornice_height',1)
        depth=spec.get('relief_depth',2)
        pitch=spec.get('panel_pitch',4)
        if not base<=dado<h-cornice or depth>d:
            raise ValueError('墙裙、檐口或浮雕深度超出构件尺寸')
        box([0,0,0],[x,y,0],primary)
        box([0,0,0],[x,base-1,depth-1],accent)
        box([0,dado,0],[x,dado,depth-1],accent)
        box([0,h-cornice,0],[x,y,depth-1],accent)
        for column in sorted({x,*range(0,w,pitch)}):
            box([column,base,0],[column,dado-1,depth-1],accent)
        parts={'wainscot':([0,0,0],[x,dado,z]),'cornice':([0,h-cornice,0],[x,y,z])}
    elif kind=='ceiling':
        drop=spec.get('drop',2)
        if drop>h:raise ValueError('下吊高度超过构件高度')
        pitch=spec.get('pitch',4);level=h-drop
        border=spec.get('border',1)
        if 2*border>=min(w,d):raise ValueError('吊顶边框过宽')
        for a in range(w):
            for b in range(d):
                edge=min(a,b,x-a,z-b)<border
                beam=a%pitch==0 or (spec.get('profile','grid')=='grid' and b%pitch==0)
                if edge or beam:
                    light=spec.get('light_strip',False) and a==cx and edge
                    box([a,level,b],[a,y,b], 'sea_lantern' if light else accent if edge else primary)
        parts={'trim':([0,level,0],[x,level,z])}
    elif kind in ('plant','planter'):
        pot=spec.get('pot_height',2);leaf=spec.get('crown_height',3);radius=spec.get('radius',2)
        if pot+leaf>h:raise ValueError('盆器与叶冠超过高度')
        shape=spec.get('profile','upright');randomness=random.Random(spec.get('seed',0))
        box([0,0,0],[x,0,z],accent)
        for a,b,c,e in [(0,0,x,0),(0,z,x,z),(0,1,0,z-1),(x,1,x,z-1)]:
            box([a,1,b],[c,pot-1,e],accent)
        box([1,pot-1,1],[x-1,pot-1,z-1],'dirt')
        centers=[cx] if kind=='plant' else list(range(1,x,max(2,2*radius+1)))
        crown_y=h-leaf
        for center in centers:
            trunk_z=1 if shape=='climbing' else cz
            box([center,pot,trunk_z],[center,y,trunk_z],primary)
            for k in range(crown_y,h):
                span=max(1,radius-(k-crown_y)) if shape=='upright' else radius
                for a in range(max(0,center-span),min(x,center+span)+1):
                    for b in range(max(0,trunk_z-span),min(z,trunk_z+span)+1):
                        if shape=='climbing' and b!=trunk_z:continue
                        if (a,b)==(center,trunk_z) or abs(a-center)+abs(b-trunk_z)>span:continue
                        if randomness.randrange(100)<spec.get('density',80):box([a,k,b],[a,k,b],foliage)
            if shape=='trailing' and crown_y>pot and center!=0:
                box([center-1,pot,cz],[center-1,crown_y,cz],foliage)
        parts={'container':([0,0,0],[x,pot-1,z]),'crown':([0,crown_y,0],[x,y,z])}
    elif kind=='stairs':
        if 'handrail' in spec:
            from nbt_building.modular_objects import stairs
            stairs(spec,size,box,primary,accent)
        else:_stairs(spec,size,box,accent)
    else:
        raise ValueError('此类构件没有专用form参数')
    return {name:dict(lo=lo,hi=hi) for name,(lo,hi) in parts.items()}


def _stairs(form,size,box,accent):
    w,h,d=size
    width=form.get('run_width',2);rise=form.get('rise',4);landing=form.get('landing',2)
    shape=form.get('profile','straight')
    block,props=effective(form.get('tread','stone_brick_stairs'))
    if not block.endswith('_stairs'):raise ValueError('踏步须使用原版楼梯方块')
    if h<rise+2:raise ValueError('楼梯高度不足，须留出栏杆格')
    segments=[]
    def segment(x,z,dx,dz,count,direction,level):
        segments.append((x,z,dx,dz,count,direction,level))
    a=(rise+1)//2;b=rise-a
    if shape=='straight':
        segment(0,0,0,1,rise,'south',0)
    elif shape=='quarter_turn':
        segment(0,0,0,1,a,'south',0)
        box([0,0,a],[width-1,a-1,a+max(width,landing)-1],accent)
        segment(width,a,1,0,b,'east',a)
    elif shape=='switchback':
        segment(0,0,0,1,a,'south',0)
        box([0,0,a],[2*width-1,a-1,a+landing-1],accent)
        segment(width,a-1,0,-1,b,'north',a)
    else:
        # Square spiral with a full-width corner landing between each flight.
        run=max(1,(rise+3)//4);side=run+2*width
        flights=[(0,width,0,1,'south'),(width,side-width,1,0,'east'),(side-width,side-width-1,0,-1,'north'),(side-width-1,0,-1,0,'west')]
        corners=[(0,side-width),(side-width,side-width),(side-width,0),(0,0)]
        level=0
        for i,(a0,b0,dx,dz,direction) in enumerate(flights):
            count=min(run,rise-level)
            if count<=0:break
            segment(a0,b0,dx,dz,count,direction,level);level+=count
            if level<rise:
                cc,dd=corners[i];box([cc,0,dd],[cc+width-1,level-1,dd+width-1],accent)
    for x,z,dx,dz,count,direction,level in segments:
        for step in range(count):
            a=x+dx*step;b=z+dz*step;y=level+step
            end_x=a+(width-1 if not dx else 0);end_z=b+(width-1 if not dz else 0)
            box([a,0,b],[end_x,y-1,end_z],accent)
            box([a,y,b],[end_x,y,end_z],f'{block}[facing={direction},half=bottom,shape=straight,waterlogged=false]')
            if form.get('rail',False):
                if width<2:raise ValueError('带栏杆的楼梯至少两格宽')
                box([a,y+1,b],[a,y+1,b],accent)
