"""Bounded image-to-half-grid adaptation, without rewriting source patterns."""
from math import log
import json

import numpy as np
from PIL import Image,ImageOps

from nbt_model import state
from nbt_ornament_sample import sample_image,fit_sample,resize_sample


def symmetry(coverage):
    return [axis for axis,reflected in (('x',np.fliplr(coverage)),('y',np.flipud(coverage)))
            if np.allclose(coverage,reflected,atol=1e-9)]


def projected(unit,width,height,options,factor):
    masks={value:mask for value,mask in options};pixels=np.zeros((height*factor,width*factor),dtype=bool)
    for (x,y),value in unit.items():
        pixels[y*factor:(y+1)*factor,x*factor:(x+1)*factor]=np.array(masks[value]).reshape(factor,factor)
    return pixels


def overlap(pixels,coverage):
    return float(np.minimum(pixels,coverage).sum()/max(1e-9,float(np.maximum(pixels,coverage).sum())))


def aligned_colors(image,sample,width,height):
    """Sample colours through exactly the same mapping as the fitted mask."""
    palette=[(tuple(bytes.fromhex(entry['rgb'][1:])),state(entry['material'])) for entry in sample.get('colors',[])]
    if not palette:return lambda u,v:None
    # The reference's ink threshold excludes empty margins from colour means.
    mask=image.getchannel('A') if sample.get('channel')=='alpha' else image.convert('L')
    if sample.get('invert'):mask=ImageOps.invert(mask)
    ink=(np.asarray(mask)>=sample.get('threshold',50)*255/100)&(np.asarray(image.getchannel('A'))>0)
    rgb=np.flipud(np.asarray(image.convert('RGB'),dtype=float));ink=np.flipud(ink)
    if sample.get('mirror'):
        columns=np.minimum(np.arange(image.width),image.width-1-np.arange(image.width))
        rgb=rgb[:,columns];ink=ink[:,columns]
    step_x,step_y=image.width//width,image.height//height
    def material_at(u,v):
        colors=rgb[v*step_y:(v+1)*step_y,u*step_x:(u+1)*step_x]
        selected=ink[v*step_y:(v+1)*step_y,u*step_x:(u+1)*step_x]
        color=colors[selected].mean(axis=0) if selected.any() else colors.mean(axis=(0,1))
        return min(palette,key=lambda entry:sum((a-b)**2 for a,b in zip(color,entry[0])))[1]
    return material_at


def adaptive_fit(root,sample,width,height,options,factor,max_error,mode,*,quality_profile='balanced',min_quality_score=0,raster=None):
    from nbt_microfit import reference,fit_reference,contour_error

    if mode not in ('auto','fixed'):raise ValueError('micro_alignment须为auto或fixed')
    image=sample_image(root,sample) if raster is None else raster
    original=reference(root,sample,width,height,factor,raster=image)
    from nbt_pattern_quality import assess,source_bitmap
    target=(width*factor*8,height*factor*8)
    baseline_image=resize_sample(image,target,sample.get('fit','contain'))
    # Compare every palette at the same physical resolution and edge tolerance.
    # Upsampling the actual mask first prevents coarse blocks from receiving a
    # more forgiving contour tolerance than identical fine-block geometry.
    quality_image=resize_sample(image,(width*32,height*32),sample.get('fit','contain'))
    quality_reference=source_bitmap(quality_image,sample)
    def assess_unit(unit,minimum=0):
        pixels=projected(unit,width,height,options,factor)
        scale=32//factor
        pixels=np.repeat(np.repeat(pixels,scale,axis=0),scale,axis=1)
        report=assess(pixels,quality_reference,quality_profile,0)
        report.update(minimum_score=minimum,passed=report['score']+1e-9>=minimum,quality_protocol_version=3,
            evaluation_grid=dict(pixels_per_block=32,edge_tolerance_blocks=1/32),
            method='physical_32px_'+report['method'])
        if not report['passed']:raise ValueError('纹样量化质量未达标：'+json.dumps(report,ensure_ascii=False,separators=(',',':')))
        return report
    def refinement_accept(before,after):
        a,b=(assess_unit(unit) for unit in (before,after))
        accepted=(b['score']+1e-9>=a['score'] and b['metrics']['detail_retention']+1e-12>=a['metrics']['detail_retention'])
        return dict(accepted=accepted,reference='original_mapped_image',previous_score=a['score'],candidate_score=b['score'],
            previous_detail_retention=a['metrics']['detail_retention'],candidate_detail_retention=b['metrics']['detail_retention'])
    def solve(data,joint=True):
        return fit_reference(data,sample,width,height,options,factor,max_error,joint=joint,strict=False,refinement_accept=refinement_accept)
    baseline_failure=None
    try:base_unit,base_quality=solve(original)
    except ValueError as error:
        if mode=='fixed':raise
        baseline_failure=str(error);base_unit={}
        base_quality=dict(topology_preserved=False,raw_coverage_error=1.,ink_overlap=0.)
    valid=lambda q:q['topology_preserved'] and q['raw_coverage_error']<=max_error
    original_symmetry=symmetry(original[0])
    identity=dict(ratio_mode=sample.get('fit','contain'),scale=1.,offset_pixels=[0,0],
                  offset_blocks_uv=[0.,0.],aspect_adjustment=(target[0]/target[1])/(image.width/image.height) if sample.get('fit')=='stretch' else 1.,
                  content_size_pixels=None,paste_origin_pixels=None)
    def score(unit,quality,change):
        pixels=projected(unit,width,height,options,factor)
        original_overlap=overlap(pixels,original[0])
        # Fit improvement must pay for movement/distortion; retain the identity
        # on ties. The old-reference score remains visible in the receipt.
        distortion=abs(log(change['aspect_adjustment']))+2*abs(log(change['scale']))
        movement=sum(abs(n) for n in change['offset_blocks_uv'])
        value=quality['ink_overlap']-.06*distortion-.02*movement
        return value,original_overlap,contour_error(pixels,original[0])
    base_score=score(base_unit,base_quality,identity)
    candidates=[(base_unit,base_quality,baseline_image,identity,base_score)]
    failures=0;probed=0;dedup={baseline_image.tobytes()};shortlist=[]
    if mode=='auto' and not (valid(base_quality) and base_quality['ink_overlap']==1):
        contained=ImageOps.contain(image,target,Image.Resampling.BOX).size
        ratio=max(target[0]/contained[0],target[1]/contained[1])
        # Explicit contain/cover remains authoritative. No automatic crop or
        # extreme stretching of a square flower into a very long border.
        amounts=(0.,.5,1.) if 'fit' not in sample and 1<ratio<=2 else (0.,)
        phases_x=(0,) if 'x' in original_symmetry else (0,-2,2)
        phases_y=(0,) if 'y' in original_symmetry else (0,-2,2)
        for amount in amounts:
            for scale in (1.,.97,1.03):
                if sample.get('fit') in ('cover','stretch'):
                    source=baseline_image
                    content_size=tuple(max(1,round(n*scale)) for n in target)
                else:
                    source=image
                    content_size=tuple(max(1,round((a+(b-a)*amount)*scale)) for a,b in zip(contained,target))
                content=source.resize(content_size,Image.Resampling.BOX)
                luminance=content.getchannel('A') if sample.get('channel')=='alpha' else content.convert('L')
                if sample.get('invert'):luminance=ImageOps.invert(luminance)
                ink=(np.asarray(luminance)>=sample.get('threshold',50)*255/100)&(np.asarray(content.getchannel('A'))>0)
                for dx in phases_x:
                    for dy in phases_y:
                        if amount==0 and scale==1 and dx==dy==0:continue
                        x=round((target[0]-content_size[0])/2)+dx;y=round((target[1]-content_size[1])/2)+dy
                        yy,xx=np.nonzero(ink)
                        if len(xx) and (xx.min()+x<0 or xx.max()+x>=target[0] or yy.min()+y<0 or yy.max()+y>=target[1]):continue
                        raster=Image.new('RGBA',target);raster.paste(content,(x,y))
                        key=raster.tobytes()
                        if key in dedup:continue
                        dedup.add(key);probed+=1
                        try:data=reference(root,sample,width,height,factor,raster=raster)
                        except ValueError:
                            failures+=1;continue
                        if any(data[3][k]!=original[3][k] for k in ('components','holes')):continue
                        if not set(original_symmetry)<=set(symmetry(data[0])):continue
                        change=dict(ratio_mode='adapt' if amount else sample.get('fit','contain'),
                                    scale=scale,offset_pixels=[dx,dy],
                                    offset_blocks_uv=[dx/(factor*8),-dy/(factor*8)],
                                    content_size_pixels=list(content_size),paste_origin_pixels=[x,y],
                                    aspect_adjustment=(content_size[0]/content_size[1])/(image.width/image.height)
                                    if sample.get('fit')!='cover' else 1.)
                        try:unit,quality=solve(data,joint=False)
                        except ValueError:
                            failures+=1;continue
                        estimate=score(unit,quality,change)
                        topology_gap=sum(abs(quality['source_topology'][k]-quality['result_topology'][k]) for k in ('components','holes'))
                        shortlist.append((topology_gap,not valid(quality),-estimate[0],data,raster,change))
        # Probe cheaply, then perform complete legal-shape search on a bounded
        # shortlist. Include failed probes: joint search can repair topology.
        shortlist.sort(key=lambda item:item[:3])
        for _,_,_,data,raster,change in shortlist[:6]:
            try:unit,quality=solve(data)
            except ValueError:
                failures+=1;continue
            candidates.append((unit,quality,raster,change,score(unit,quality,change)))
    available=[item for item in candidates if valid(item[1])]
    if not available:
        # Preserve the normal public diagnostic rather than returning an
        # apparently successful image transformation with invalid geometry.
        try:fit_reference(original,sample,width,height,options,factor,max_error)
        except ValueError as error:
            if mode=='fixed':raise
            raise ValueError(f'自动比例/半格对齐已探测{probed}个候选，仍未找到保留主拓扑的方案；{error}') from error
        raise ValueError('自动对齐未找到保留主拓扑的微型单元')
    # Keep the existing bounded geometric ranking. A failed visual gate must
    # try the remaining admissible fits before declaring the image impossible.
    # All candidates are measured against the same original mapped image.
    ranked=sorted(available,key=lambda item:item[4][0],reverse=True)
    assessed=[]
    for index,item in enumerate(ranked):
        report=assess_unit(item[0])
        assessed.append(dict(rank=index+1,score=report['score'],passed=report['score']+1e-9>=min_quality_score))
        if assessed[-1]['passed']:
            best=item;report=dict(report,minimum_score=min_quality_score,passed=True);break
    else:
        # Raise the usual public report for the best measured failure. Do not
        # lower the requested threshold, rewrite the source or invent a fit.
        failure=max(range(len(assessed)),key=lambda i:assessed[i]['score'])
        assess_unit(ranked[failure][0],min_quality_score)
        raise ValueError('纹样量化质量未达标')
    unit,quality,raster,change,metrics=best
    quality=dict(quality,alignment=dict(mode=mode,algorithm_revision=2,applied=best is not candidates[0],
        **change,source_size=list(image.size),target_sample_size=list(target),
        preserved_source_topology={k:original[3][k] for k in ('components','holes')},
        original_reference_ink_overlap=metrics[1],original_reference_contour_error=metrics[2],
        baseline_accepted=valid(base_quality),baseline_topology_preserved=base_quality['topology_preserved'],
        baseline_ink_overlap=base_quality['ink_overlap'] if baseline_failure is None else None,
        baseline_raw_coverage_error=base_quality['raw_coverage_error'] if baseline_failure is None else None,
        baseline_failure=baseline_failure,
        candidates_probed=probed,candidates_solved=len(candidates),constraint_failures=failures,
        search='bounded_ratio_scale_phase',source_modified=False))
    if not sample.get('colors'):color_at=lambda u,v:None
    elif mode=='fixed' or best is candidates[0]:
        _,color_at=fit_sample(root,dict(sample,noise_strength=0),width,height,0,sample.get('mirror',False),subcells=factor)
    else:color_at=aligned_colors(raster,sample,width,height)
    quality['quality_selection']=dict(strategy='geometric_rank_then_original_reference_quality_gate',
        selected_candidate_rank=index+1,candidates_evaluated=len(assessed),candidates_available=len(ranked),
        assessments=assessed,threshold_relaxed=False,reference='original_mapped_image')
    quality['visual_quality']=report
    quality['quality_sampling_resolution']=32
    return unit,quality,color_at
