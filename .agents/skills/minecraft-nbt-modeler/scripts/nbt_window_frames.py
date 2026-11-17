"""Architectural window families with real panes, reveals and moulding depth.

This module creates geometry only. Recipe data lives in the external asset
library. Sash movement, weatherproofing and real-world load design are omitted.
"""
from math import ceil
from nbt_model import state
from nbt_registry import effective
from nbt_architectural_bay import curve

PROFILES=('sash_window','classical_window','round_arch_window','pointed_arch_window')
FIELDS=('panes','head','dentils','cornice_material','bar_material','lights','tracery','glass_palette','detail_material')


def glass_palette(form):
    from nbt_structural_members import full
    if 'glass_palette' in form and 'glass_material' in form:raise ValueError('玻璃使用glass_material或glass_palette之一')
    values=form.get('glass_palette',[form.get('glass_material','glass')])
    result=[]
    for value in values:
        value=full(value);name,_=effective(value)
        if name not in ('minecraft:glass','minecraft:tinted_glass') and not name.endswith('_stained_glass'):
            raise ValueError('窗玻璃必须使用完整玻璃方块')
        result.append(value)
    if not 1<=len(result)<=8:raise ValueError('玻璃配色须为1到8项')
    return result


def slab(value,kind):
    value=state(value);name,props=effective(value)
    if not name.endswith('_slab') or props['type']!=kind or props['waterlogged']!='false':
        raise ValueError('窗台使用顶部半砖，檐口使用底部半砖，均须未含水')
    return value


def bars(length,count):
    if not 1<=count<=8:raise ValueError('窗格行列数须为1到8')
    positions=[round(i*(length+1)/count)-1 for i in range(1,count)]
    if any(b-a-1<2 for a,b in zip([-1,*positions],[*positions,length])):
        raise ValueError('每个玻璃窗格至少需要2格净宽高，请增大尺寸或减少分格')
    return set(positions)


def build_window(form,size,primary,accent):
    from nbt_structural_members import full,grain
    profile=form['profile'];w,h,d=size;x,y,z=w-1,h-1,d-1;b=form.get('border',1)
    common={'profile','border','recess','glazing','glass_material','glass_palette','sill_material','bar_material'}
    extras={'sash_window':{'panes'},'classical_window':{'panes','head','dentils','cornice_material','detail_material'},
            'round_arch_window':{'lights','detail_material'},'pointed_arch_window':{'lights','tracery'}}
    if set(form)-common-extras[profile]:raise ValueError('花式窗型含不适用的form参数')
    primary,accent=full(primary),full(accent)
    if any('glass' in effective(v)[0] for v in (primary,accent)):raise ValueError('窗框主体不能使用玻璃')
    palette=glass_palette(form);bar=full(form.get('bar_material',accent))
    if 'glass' in effective(bar)[0]:raise ValueError('窗棂和线脚不能使用玻璃材质')
    sill=slab(form.get('sill_material','smooth_quartz_slab[type=top,waterlogged=false]'),'top')
    recess=form.get('recess',min(2,z));glazing=form.get('glazing',True)
    if not 1<=recess<d:raise ValueError('玻璃退进必须位于1到画布深度-1')
    if 2*b>=min(w,h):raise ValueError('框边厚没有留下窗孔')
    blocks={};parts={};candidates={};opening=set();shape='rectangular'
    def box(lo,hi,value):
        if any(a>b for a,b in zip(lo,hi)):return
        if any(a<0 or q>=n for a,q,n in zip(lo,hi,size)):raise ValueError('花式窗构造超出尺寸')
        value=state(value)
        for xx in range(lo[0],hi[0]+1):
            for yy in range(lo[1],hi[1]+1):
                for zz in range(lo[2],hi[2]+1):blocks[(xx,yy,zz)]=value
    def part(name,lo,hi):parts[name]=dict(lo=lo,hi=hi)
    def paint_glass(xx,yy,plane):
        # Broad symmetric zones, not independently randomized coloured pixels.
        tone=(abs(2*xx-x)//max(2,w//4)+(yy//max(2,h//5)))%len(palette)
        candidates[(xx,yy,plane)]=palette[tone];opening.add((xx,yy))
    def rectangular_frame(margin,top):
        for low in (0,w-margin):box([low,0,1],[low+margin-1,top,z],grain(primary,'y'))
        box([margin,0,1],[x-margin,margin-1,z],grain(accent,'x'))
        box([margin,top-margin+1,1],[x-margin,top,z],grain(accent,'x'))
        part('jamb_left',[0,1,1],[margin-1,top-margin,z])
        part('jamb_right',[w-margin,1,1],[x,top-margin,z])
    def divided_panel(left,bottom,right,top,counts,sashes=False):
        cols,rows=counts
        xb={left+v for v in bars(right-left+1,cols)}
        yb={bottom+v for v in bars(top-bottom+1,rows)}
        if sashes:
            if rows<2 or rows%2:raise ValueError('上下对称木窗需要偶数行窗格')
            if recess+1>=d:raise ValueError('上下窗扇需要两层玻璃退进空间')
            meeting=sorted(yb)[rows//2-1]
        else:meeting=None
        for yy in range(bottom,top+1):
            plane=recess+1 if sashes and yy>meeting else recess
            for xx in range(left,right+1):
                opening.add((xx,yy))
                if yy==meeting:
                    box([xx,yy,recess],[xx,yy,recess+1],grain(bar,'x'))
                elif xx in xb or yy in yb:
                    box([xx,yy,plane],[xx,yy,plane],grain(bar,'x' if yy in yb else 'y'))
                else:paint_glass(xx,yy,plane)
        part('glazing',[left,bottom,recess],[right,top,recess+1 if sashes else recess])

    if profile=='sash_window':
        rectangular_frame(b,y)
        divided_panel(b,b,x-b,y-b,form.get('panes',[3,4]),True)
        part('lintel',[0,h-b,1],[x,y,z])
    elif profile=='classical_window':
        head=form.get('head','cornice')
        if head not in ('cornice','triangular'):raise ValueError('古典窗头须为cornice或triangular')
        if head=='triangular' and 'cornice_material' in form:
            raise ValueError('triangular窗头使用框体与线脚材质，不使用cornice_material半砖')
        rise=max(2,ceil(w/5)) if head=='triangular' else 0
        top=h-3-rise;margin=b+1
        if top<2*margin+2 or w<2*margin+2:raise ValueError('线脚窗套须留出内框、玻璃和窗头空间')
        rectangular_frame(margin,top)
        # One forward outer casing and one recessed inner lining.
        for low in (0,w-b):box([low,1,0],[low+b-1,top-1,0],accent)
        box([0,top-b,0],[x,top-1,0],accent)
        if form.get('dentils',True):
            for xx in range(b,w-b,2):box([xx,top,0],[xx,top,0],accent)
        box([0,top+1,0],[x,top+1,z],accent)
        detail=full(form.get('detail_material',accent))
        box([x//2,top-1,0],[x//2,top,0],detail)
        if head=='cornice':
            name,_=effective(sill)
            cap=slab(form.get('cornice_material',name+'[type=bottom,waterlogged=false]'),'bottom')
            box([0,y,0],[x,y,z],cap)
        else:
            start=top+2
            roof=[start+round(rise*(1-abs(2*xx/x-1))) for xx in range(w)]
            for xx,level in enumerate(roof):
                box([xx,start,1],[xx,level,z],primary)
                low=min(roof[max(0,xx-1):min(w,xx+2)])
                box([xx,low,0],[xx,level,0],accent)
            box([x//2,start,0],[x//2,start,0],detail)
        part('cornice',[0,top,0],[x,y,z])
        divided_panel(margin,margin,x-margin,top-margin,form.get('panes',[1,1]))
    elif profile=='pointed_arch_window' and form.get('tracery',True):
        if b!=1 or form.get('lights',2)!=2:raise ValueError('复合尖拱窗棂使用border=1、lights=2；简窗可设置tracery=false')
        from nbt_architectural_bay import compile_tracery
        delta=recess-1
        built=compile_tracery(None,dict(size_uv=[w,h],depth=d-delta,profile='pointed',
                             material=primary,trim=bar,glass_palette=palette,glazing=True))
        glass_names={effective(v)[0] for v in palette}
        cx=x/2;a=cx-1;spring=round(y*.53);rise=h-2-spring
        opening.update((xx,yy) for xx in range(1,w-1) for yy in range(1,h-1)
                       if yy<=spring+rise*curve((xx-cx)/a,'pointed'))
        for op in built['spec']['operations']:
            for xx,yy,zz,index in op['voxels']:
                value=op['palette'][index]
                if effective(value)[0] in glass_names:
                    candidates[(xx,yy,zz+delta)]=value;opening.add((xx,yy))
                elif zz==0:box([xx,yy,0],[xx,yy,delta],value)
                else:box([xx,yy,zz+delta],[xx,yy,zz+delta],value)
        part('tracery',[1,1,0],[x-1,y-1,recess-1])
        part('glazing',[1,1,recess],[x-1,y-1,recess])
        shape='pointed'
    else:
        pointed=profile=='pointed_arch_window';shape='pointed' if pointed else 'round'
        radius=x/2;rise=ceil(w*.7) if pointed else ceil(radius)
        spring=y-rise
        if spring<b+2 or radius-b<2:raise ValueError('拱窗尺寸不足以表达竖框、拱和玻璃')
        outer=[spring+round(rise*curve((xx-radius)/radius,shape)) for xx in range(w)]
        inner={xx:spring+int((rise-b)*curve((xx-radius)/(radius-b),shape)) for xx in range(b,w-b)}
        for xx in range(w):
            for yy in range(outer[xx]+1):
                if xx in inner and b<=yy<=inner[xx]:
                    paint_glass(xx,yy,recess)
                else:box([xx,yy,0],[xx,yy,z],primary if yy>b else accent)
        lights=form.get('lights',1 if not pointed else 2)
        splits={b+v for v in bars(w-2*b,lights)}
        for xx in splits:
            for yy in range(b,inner[xx]+1):
                box([xx,yy,recess],[xx,yy,recess],grain(bar,'y'))
                candidates.pop((xx,yy,recess),None)
        if profile=='round_arch_window':
            detail=full(form.get('detail_material',accent));cx=x//2
            box([cx,outer[cx]-b,0],[cx,outer[cx],0],detail)
        part('arch',[0,spring,0],[x,max(outer),z])
        part('glazing',[b,b,recess],[x-b,max(inner.values()),recess])

    box([0,0,0],[x,0,0],sill)
    part('sill',[0,0,0],[x,0,z])
    if glazing:
        for p,value in candidates.items():
            if p not in blocks:blocks[p]=value
    transparent=set(candidates) if glazing else set()
    actual_glass={p for p in transparent if blocks.get(p)==candidates[p]}
    clear={(xx,yy) for xx,yy in opening if not any((xx,yy,zz) in blocks for zz in range(d))}
    opaque=[p for p,v in blocks.items() if 'glass' not in effective(v)[0]]
    top=max(opaque,key=lambda p:(p[1],p[2],-abs(2*p[0]-x)))
    interfaces=[dict(id='left_seat',face='down',lo=[0,0,z],hi=[0,0,z]),
                dict(id='right_seat',face='down',lo=[x,0,z],hi=[x,0,z]),
                dict(id='head_top',face='up',lo=list(top),hi=list(top))]
    info=dict(profile=profile,interfaces=interfaces,apertures=[dict(id='opening',shape=shape,
              glazed=glazing,passage_candidate=False,cells_xy=[list(p) for p in sorted(opening)],
              clear_cells_xy=[list(p) for p in sorted(clear)])],glass_blocks=len(actual_glass),
              front='north_-z',support='not_checked',routes='not_checked',game='not_checked',sash_motion='not_simulated')
    return blocks,parts,info


def generate(form,size,box,primary,accent):
    blocks,parts,_=build_window(form,size,primary,accent)
    for p,value in sorted(blocks.items()):box(list(p),list(p),value)
    return parts


def describe(form,size):
    return build_window(form,size,'stone','polished_andesite')[2]
