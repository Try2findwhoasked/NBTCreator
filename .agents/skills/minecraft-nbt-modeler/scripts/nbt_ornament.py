"""Bounded voxel ornament; historical cues are simplified, not reconstructions."""
import hashlib
import math
from nbt_model import state, AIR_NAMES

PROFILES = {
 'none':dict(name='无附加装饰',motifs=[],source=None),
 'classical':dict(name='古典语汇',motifs=['dentil','fluting'],features='连续檐带、齿饰、竖向分槽；不复原完整柱式比例',source='https://www.metmuseum.org/ko/essays/architecture-in-ancient-greece'),
 'gothic':dict(name='哥特语汇',motifs=['pointed_arch','tracery'],features='尖拱轮廓、竖向细分和几何窗饰',source='https://www.vam.ac.uk/articles/the-gothic-style-an-introduction'),
 'art_deco':dict(name='装饰艺术语汇',motifs=['chevron','sunburst'],features='阶梯几何、折线与放射节奏',source='https://www.vam.ac.uk/articles/an-introduction-to-art-deco'),
 'art_nouveau':dict(name='新艺术语汇',motifs=['vine','leaf'],features='植物枝叶与曲线的体素化近似',source='https://www.vam.ac.uk/articles/art-nouveau-an-international-style'),
 'geometric':dict(name='几何格纹',motifs=['lattice','diamond'],features='通用格栅与菱形；不标注为某一地域传统工艺',source=None),
}

def decorate(spec, data, arguments, workspace=None):
    settings=arguments.get('ornament',{});profile=settings.get('profile','none')
    if profile=='none':
        if any(k!='profile' for k in settings):raise ValueError('无装饰时不能配置纹样参数，请先选择ornament.profile')
        return dict(profile='none',added_or_recolored_blocks=0)
    chosen=PROFILES[profile];motif=settings.get('motif','auto')
    if motif=='auto':motif=chosen['motifs'][0]
    if motif not in chosen['motifs']:raise ValueError('纹样不属于所选装饰风格')
    kind=arguments['kind'];w,h,d=spec['size'];depth=settings.get('depth',1);scale=settings.get('scale',4)
    border=settings.get('border_layers',1);density=settings.get('density',65);symmetry=settings.get('symmetry',True);seed=settings.get('seed',0)
    material=state(settings.get('material',arguments.get('accent','chiseled_stone_bricks')))
    if material in AIR_NAMES:raise ValueError('装饰材质不能是空气')
    # Plane coordinates preserve the mount convention and never reach outside size.
    if kind=='ceiling':
        width,height=w,d
        def point(u,v,k):return (u,h-2-k,v)
    elif kind=='stairs':
        width,height=d,h
        def point(u,v,k):return (k,v,u)
    else:
        width,height=w,h
        def point(u,v,k):return (u,v,k+1 if kind=='wall' else d-1-k)
    if min(width,height)<2*border+3:raise ValueError('当前装饰面过小，至少需要2*border_layers+3格；请扩大尺寸或减少边框层数')
    if depth>(h-1 if kind=='ceiling' else w if kind=='stairs' else d-1 if kind=='wall' else d):raise ValueError('装饰深度超出可用厚度')
    layout=settings.get('layout','continuous')
    if 'center_clear' in settings and layout=='centerpiece':
        raise ValueError('中心徽章与中心留白不可同时启用')
    clear=settings.get('center_clear',0)
    sample_settings=settings.get('sample')
    sample=None
    sample_color=None
    shape_fit=settings.get('sample_shape_fit')
    if shape_fit is not None and (not sample_settings or not shape_fit or kind!='wall' or depth!=1 or 'edge_trim' in settings):
        raise ValueError('轮廓拟合需要墙饰样本、depth=1、至少一种半砖或楼梯，且不叠加 edge_trim')
    shape_options=[]
    if shape_fit:
        from nbt_ornament_sample import silhouette_options,match_silhouette
        from nbt_collision import collision_cells
        cells,reason=collision_cells(material)
        if reason or len(cells)!=8:
            raise ValueError('轮廓拟合的主材必须是已知完整方块')
        from nbt_model import state as normalize_state
        for entry in sample_settings.get('colors',[]):
            cells,reason=collision_cells(normalize_state(entry['material']))
            if reason or len(cells)!=8:
                raise ValueError('轮廓拟合的样本配色须使用已知完整方块')
        shape_options=silhouette_options(material,shape_fit)
    fitted_counts={}
    fit_errors=dict(matched=0,missing=0,extra=0)
    if sample_settings:
        from nbt_ornament_sample import fit_sample
        sample,sample_color,sample_coverage=fit_sample(workspace,sample_settings,width,height,seed,sample_settings.get('mirror',False),settings.get('sample_repeat',(1,1)),subcells=bool(shape_fit),return_coverage=True)
    if 'sample_repeat' in settings and not sample_settings:
        raise ValueError('纹样平铺需要样本图片')
    trim=settings.get('edge_trim')
    trim_blocks={}
    if trim is not None:
        from nbt_registry import effective
        if not trim or kind not in ('wall','ceiling'):
            raise ValueError('半砖和楼梯收边适用于墙饰和吊顶')
        for key,suffix in [('slab','_slab'),('stairs','_stairs')]:
            if key in trim:
                name,properties=effective(trim[key])
                if not name.endswith(suffix) or properties.get('waterlogged')!='false':
                    raise ValueError('收边须使用未含水的对应原版半砖或楼梯')
                trim_blocks[key]=name
    richness=settings.get('richness',0)
    highlight=state(settings.get('highlight',material))
    if highlight in AIR_NAMES:raise ValueError('高光材质不能是空气')
    occupied={tuple(b[:3]):data['palette'][b[3]] for b in data['blocks']}
    voxels={}
    def keep(u,v):
        a=min(u,width-1-u) if symmetry else u
        # Keep density choices identical across mirrored pairs and all platforms.
        n=int.from_bytes(hashlib.sha256(f'{seed}:{a//scale}:{v//scale}'.encode()).digest()[:4],'big')
        return n%100<density
    def pattern(u,v):
        a=min(u,width-1-u) if symmetry else u
        u=a
        U=(a-border)%scale;V=(v-border)%scale
        if motif=='dentil':return v>=height-border-2 and U==0
        if motif=='fluting':return U==0
        if motif=='chevron':return V==min(U,scale-1-U)
        if motif=='sunburst':
            dx=u-(width-1)/2;dy=v-border
            angle=math.atan2(dy,dx);return abs(math.sin(angle*scale))<.22
        if motif=='lattice':return U==0 or V==0
        if motif=='diamond':return abs(U-(scale-1)/2)+abs(V-(scale-1)/2)<=(scale-1)/2 and (U+V)%2==0
        if motif in ('pointed_arch','tracery'):
            middle=(width-1)/2;top=height-border-1-abs(u-middle)*.8
            return abs(v-top)<.65 or (u in (border,width-border-1) and v<=top) or (motif=='tracery' and V==0 and abs(u-middle)<scale)
        curve=(width-1)/2+math.sin(v/max(1,scale)*math.pi)*max(1,(width-2*border-2)/3)
        return abs(u-curve)<.7 or (motif=='leaf' and V==0 and abs(u-curve)<2)
    radius=min(width,height)/4
    for u in range(width):
        for v in range(height):
            edge=min(u,v,width-1-u,height-1-v)<border
            du=abs(2*u-width+1)
            dv=abs(2*v-height+1)
            if clear and du<clear and dv<clear:continue
            ring=abs(math.hypot(du/2,dv/2)-radius)<.65
            filigree=richness>=2 and (du//2+dv//2)%scale==0 and min(du,dv)>radius
            bead=richness>=1 and min(u,v,width-1-u,height-1-v)==border and (du+dv)%max(2,scale)==0
            ornate=(richness>=3 and ring) or filigree or bead
            if not edge:
                if layout=='centerpiece' and (du>width//2 or dv>height//2):continue
                if layout=='corners' and (du<width//2 or dv<height//2):continue
                if not ornate and not keep(u,v):continue
                if not ornate and not shape_fit and not (sample(u,v) if sample else pattern(u,v)):continue
            fitted=None
            if shape_fit and not edge and not ornate:
                mask=sample(u,v)
                fitted,projected=match_silhouette(mask,shape_options,sample_coverage(u,v))
                for a,b in zip(mask,projected):
                    fit_errors['matched']+=a==b
                    fit_errors['missing']+=a and not b
                    fit_errors['extra']+=b and not a
                if fitted is None:continue
            for k in range(depth):
                p=point(u,v,k)
                if kind=='stairs':
                    # Decoration only below existing treads; never fill headroom.
                    underlying=occupied.get(p)
                    if underlying is None or underlying.split('[')[0].endswith('_stairs'):continue
                    if 'form' in arguments:
                        if (p[0],p[1]+1,p[2]) not in occupied:continue
                    elif v>=min(h-1,u*h//d):continue
                elif kind in ('plant','planter'):
                    if v>1 or p not in occupied:continue
                elif kind not in ('wall','ceiling') and p not in occupied:continue
                color=sample_color(u,v) if sample_color and not edge and not ornate else None
                selected=highlight if ornate and k==depth-1 else color or material
                if fitted is not None:
                    if p in occupied:continue
                    selected=(color or material) if fitted==material else fitted
                    family='slab' if '_slab[' in fitted else 'stairs' if '_stairs[' in fitted else 'full'
                    fitted_counts[family]=fitted_counts.get(family,0)+1
                if occupied.get(p)!=selected:voxels[p]=selected
    trimmed=0
    if trim_blocks:
        # Keep the backing solid. Shape only exposed perimeter cells of the relief.
        face={(u,v):point(u,v,depth-1) for u in range(width) for v in range(height)
              if point(u,v,depth-1) in voxels}
        for (u,v),p in face.items():
            missing=[direction for du,dv,direction in ((-1,0,'east'),(1,0,'west'),(0,-1,'south'),(0,1,'north'))
                     if (u+du,v+dv) not in face]
            if not missing or p in occupied:
                continue
            if 'stairs' in trim_blocks and (kind=='ceiling' or any(d in ('east','west') for d in missing)):
                facing=next(d for d in missing if kind=='ceiling' or d in ('east','west'))
                half='top' if kind=='ceiling' or (u,v-1) not in face else 'bottom'
                voxels[p]=state(f"{trim_blocks['stairs']}[facing={facing},half={half},shape=straight,waterlogged=false]")
            elif 'slab' in trim_blocks:
                half='top' if kind=='ceiling' or (u,v-1) not in face else 'bottom'
                voxels[p]=state(f"{trim_blocks['slab']}[type={half},waterlogged=false]")
            else:
                continue
            trimmed+=1
    if voxels:
        palette=list(dict.fromkeys(voxels.values()))
        spec['operations'].append(dict(kind='paste_component',label=chosen['name']+' · '+motif,classification='wall' if kind=='wall' else 'body',
            lo=[0,0,0],hi=[w-1,h-1,d-1],palette=palette,voxels=[[*p,palette.index(voxels[p])] for p in sorted(voxels)],overwrite=True))
    extra={}
    if sample_settings:
        extra.update(sample_sha256=sample_settings['sha256'],pattern_source='sample_mask',sample_color_count=len(sample_settings.get('colors',[])))
        if 'reference_id' in sample_settings:
            from nbt_ornament_sample import ARCHITECTURAL_SAMPLES
            reference_id=sample_settings['reference_id']
            extra['sample_reference']={'id':reference_id,**ARCHITECTURAL_SAMPLES[reference_id]}
    if shape_fit:extra.update(sample_shape_counts=fitted_counts,sample_subcell_comparison=fit_errors)
    if trim:extra['trimmed_blocks']=trimmed
    if 'sample_repeat' in settings:extra['sample_repeat']=settings['sample_repeat']
    if richness:extra.update(richness=richness,highlight=highlight)
    return dict(**extra,profile=profile,motif=motif,layout=layout,center_clear=clear,density=density,scale=scale,depth=depth,border_layers=border,symmetry=symmetry,seed=seed,
                material=material,added_or_recolored_blocks=len(voxels),reference=chosen['source'],
                limitations='方块化装饰；小尺寸细节可能不可辨；不自动认证安装支撑、通路或游戏效果')
