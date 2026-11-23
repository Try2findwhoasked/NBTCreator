"""Array-only pattern quality metrics; no image decoding or workspace access."""
from collections import deque
import json
from math import log2, pi

import numpy as np

from nbt_pattern.bitmap_topology import component_sizes


def groups(mask, diagonal=True):
    remaining=set(zip(*np.nonzero(mask)));result=[]
    steps=((-1,0),(1,0),(0,-1),(0,1))
    if diagonal:steps+=((-1,-1),(-1,1),(1,-1),(1,1))
    while remaining:
        first=remaining.pop();pending=deque([first]);region=[]
        while pending:
            p=pending.popleft();region.append(p)
            for dy,dx in steps:
                q=(p[0]+dy,p[1]+dx)
                if q in remaining:remaining.remove(q);pending.append(q)
        result.append(region)
    return result


def thin(mask):
    """Zhang-Suen thinning, bounded by the finite bitmap dimensions."""
    ink=np.pad(mask.astype(bool),1)
    for _ in range(2*max(mask.shape)):
        changed=False
        for second in (False,True):
            p=[ink[:-2,1:-1],ink[:-2,2:],ink[1:-1,2:],ink[2:,2:],
               ink[2:,1:-1],ink[2:,:-2],ink[1:-1,:-2],ink[:-2,:-2]]
            count=sum(n.astype(np.uint8) for n in p)
            transitions=sum((~p[i]&p[(i+1)%8]).astype(np.uint8) for i in range(8))
            if second:keep_a=p[0]&p[2]&p[6];keep_b=p[0]&p[4]&p[6]
            else:keep_a=p[0]&p[2]&p[4];keep_b=p[2]&p[4]&p[6]
            remove=ink[1:-1,1:-1]&(count>=2)&(count<=6)&(transitions==1)&~keep_a&~keep_b
            if remove.any():ink[1:-1,1:-1][remove]=False;changed=True
        if not changed:break
    return ink[1:-1,1:-1]


def skeleton_neighbours(skeleton):
    p=np.pad(skeleton.astype(np.uint8),1)
    neighbours=[p[1+dy:1+dy+skeleton.shape[0],1+dx:1+dx+skeleton.shape[1]]
                for dy,dx in ((-1,0),(-1,1),(0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1))]
    return sum(neighbours),sum(((neighbours[i]==0)&(neighbours[(i+1)%8]>0)).astype(np.uint8) for i in range(8))


def pruned_skeleton(mask):
    skeleton=thin(mask);inside=mask.copy();radius=np.zeros(mask.shape,dtype=np.uint16)
    while inside.any():
        radius+=inside
        p=np.pad(inside,1)
        inside=np.logical_and.reduce([p[dy:dy+mask.shape[0],dx:dx+mask.shape[1]] for dy in range(3) for dx in range(3)])
    steps=((-1,0),(-1,1),(0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1))
    search_limit=2*int(radius.max())
    for _ in range(max(mask.shape)):
        count,arms=skeleton_neighbours(skeleton);junctions=skeleton&(arms>=3);remove=set()
        for endpoint in zip(*np.nonzero(skeleton&(count==1))):
            pending=deque([endpoint]);parents={endpoint:None};distances={endpoint:0};target=None
            while pending:
                point=pending.popleft()
                if junctions[point]:target=point;break
                if distances[point]>=search_limit:continue
                for dy,dx in steps:
                    q=(point[0]+dy,point[1]+dx)
                    if 0<=q[0]<mask.shape[0] and 0<=q[1]<mask.shape[1] and skeleton[q] and q not in parents:
                        parents[q]=point;distances[q]=distances[point]+1;pending.append(q)
            # Medial axes of thick corners produce short terminal spurs. Their
            # length must exceed the local stroke width to count as decoration.
            if target is not None and distances[target]<=2*int(radius[target]):
                point=parents[target]
                while point is not None:remove.add(point);point=parents[point]
        if not remove:break
        for point in remove:skeleton[point]=False
    return skeleton


def features(mask):
    mask=mask.astype(bool);skeleton=pruned_skeleton(mask)
    count,arms=skeleton_neighbours(skeleton)
    # Count separate outgoing arms, not merely adjacent pixels at a stair-step
    # corner. A square ring's four corners are not four branch junctions.
    branches=len(component_sizes(skeleton&(arms>=3)))
    endpoints=int((skeleton&(count==1)).sum())
    holes=component_sizes(~mask,False,True)
    padded=np.pad(mask.astype(np.int8),1)
    perimeter=sum(float(np.abs(np.diff(padded,axis=axis)).sum()) for axis in (0,1))
    area=int(mask.sum());compactness=perimeter**2/max(1.,4*pi*area)
    units=2*len(holes)+branches+.5*endpoints+1.5*max(0.,log2(max(1.,compactness)))
    return dict(components=len(component_sizes(mask)),holes=len(holes),branch_junctions=branches,endpoints=endpoints,
                perimeter=perimeter,ink_area=area,compactness=compactness,detail_units=units)


def edge(mask):
    p=np.pad(mask,1)
    inside=p[1:-1,1:-1]
    return inside&(~p[:-2,1:-1]|~p[2:,1:-1]|~p[1:-1,:-2]|~p[1:-1,2:])


def dilate(mask,radius):
    result=mask.copy()
    for _ in range(radius):
        p=np.pad(result,1)
        result=np.logical_or.reduce([p[dy:dy+mask.shape[0],dx:dx+mask.shape[1]] for dy in range(3) for dx in range(3)])
    return result


def assess(actual,reference,profile='balanced',minimum=0):
    if profile not in ('balanced','ornate','border'):raise ValueError('未知纹样质量配置')
    if type(minimum) not in (int,float) or not 0<=minimum<=100:raise ValueError('min_quality_score须为0～100')
    actual=actual.astype(bool);reference=reference.astype(bool)
    if reference.shape[0]%actual.shape[0] or reference.shape[1]%actual.shape[1]:raise ValueError('质量评估采样网格不对齐')
    sy,sx=reference.shape[0]//actual.shape[0],reference.shape[1]//actual.shape[1]
    rendered=np.repeat(np.repeat(actual,sy,axis=0),sx,axis=1)
    src=features(reference);dst=features(rendered)
    union=int((reference|rendered).sum());iou=float((reference&rendered).sum())/max(1,union)
    a,b=edge(rendered),edge(reference);tolerance=max(1,min(sx,sy)//2)
    precision=float((a&dilate(b,tolerance)).sum())/max(1,int(a.sum()))
    recall=float((b&dilate(a,tolerance)).sum())/max(1,int(b.sum()))
    contour=2*precision*recall/max(1e-9,precision+recall)
    retention=min(1.,dst['detail_units']/max(1.,src['detail_units']))
    invented=max(0.,dst['detail_units']-src['detail_units'])/max(4.,src['detail_units'])
    regularity=1/(1+invented)
    axes=[axis for axis,other in (('x',np.fliplr(reference)),('y',np.flipud(reference))) if np.array_equal(reference,other)]
    symmetry=1.
    for axis in axes:
        other=np.fliplr(actual) if axis=='x' else np.flipud(actual)
        symmetry=min(symmetry,1-float(np.count_nonzero(actual^other))/max(1,int((actual|other).sum())))
    if reference.any() and rendered.any():
        src_c=np.mean(np.argwhere(reference),axis=0)/np.array(reference.shape)
        dst_c=np.mean(np.argwhere(rendered),axis=0)/np.array(rendered.shape)
        balance=max(0.,1-float(np.linalg.norm(src_c-dst_c))/.25)
    else:balance=0.
    rhythm=1.
    for axis in (0,1):
        src_hist=reference.sum(axis=axis)/max(1,int(reference.sum()))
        dst_hist=rendered.sum(axis=axis)/max(1,int(rendered.sum()))
        rhythm-=float(np.abs(src_hist-dst_hist).sum())/4
    rhythm=max(0.,rhythm)
    regions=component_sizes(actual,False)
    fragments=sum(size for size in regions if size==1)/max(1,int(actual.sum()))
    coherence=1/(1+max(0,len(regions)-8)/8)
    density=float(actual.mean());density_score=min(1.,density/.15,(1-density)/.15)
    readability=max(0.,(density_score+1-fragments)/2)
    fidelity=.65*iou+.35*contour
    regularity=(regularity+symmetry+balance+rhythm)/4
    richness=min(1.,dst['detail_units']/12)
    if profile=='ornate':
        score=100*(.3*fidelity+.25*retention+.15*readability+.1*regularity+.2*richness)
        # A simple faithful ring/blob cannot qualify as ornate solely through IoU.
        score=min(score,40+60*richness)
    elif profile=='border':score=100*(.3*fidelity+.2*retention+.3*readability+.1*regularity+.1*rhythm)
    else:score=100*(.4*fidelity+.25*retention+.2*readability+.15*regularity)
    score=min(score,100*(1-fragments),40+60*coherence) if actual.any() else 0.
    warnings=[]
    if retention<.7:warnings.append('source_detail_lost')
    if richness<.5 and profile=='ornate':warnings.append('insufficient_ornate_detail')
    if fragments>.1 or coherence<.8:warnings.append('fragmented_or_visually_cluttered')
    if density>.85:warnings.append('negative_space_collapsed')
    if contour<.7:warnings.append('contour_degraded')
    score=round(float(score),3)
    report=dict(schema_version=1,profile=profile,score=score,minimum_score=minimum,
                passed=score+1e-9>=minimum,source_features=src,fitted_features=dst,
                metrics=dict(ink_iou=iou,contour_f1=contour,detail_retention=retention,feature_richness=richness,
                             density=density,readability=readability,regularity=regularity,
                             source_symmetry_axes=axes,symmetry_retention=symmetry,balance_retention=balance,
                             rhythm_retention=rhythm,
                             fragment_fraction=fragments,face_component_count=len(regions)),
                warnings=warnings,scope='Single transformed unit silhouette proxy; not material, lighting, architectural harmony or subjective beauty certification',
                method='source_contour_pruned_skeleton_negative_space_symmetry_and_fragmentation_v2')
    if not report['passed']:
        raise ValueError('纹样量化质量未达标：'+json.dumps(report,ensure_ascii=False,separators=(',',':')))
    return report
