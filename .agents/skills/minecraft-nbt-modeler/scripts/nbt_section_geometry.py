"""Polygon-section sweep, vertical loft and Y-axis lathe voxel masks."""
import math
import numpy as np


def polygon(vertices):
    a=np.asarray(vertices,dtype=float)
    if a.ndim!=2 or a.shape[1]!=2 or not 3<=len(a)<=64 or not np.all(np.isfinite(a)):raise ValueError('Section needs 3..64 finite 2D vertices')
    def cross(a,b,c):
        u,v=b-a,c-a
        return float(u[0]*v[1]-u[1]*v[0])
    def on(a,b,c):return abs(cross(a,b,c))<1e-9 and np.all(c>=np.minimum(a,b)-1e-9) and np.all(c<=np.maximum(a,b)+1e-9)
    for i in range(len(a)):
        b,c=a[i],a[(i+1)%len(a)]
        if np.linalg.norm(c-b)<1e-9:raise ValueError('Section has duplicate adjacent vertices')
        for j in range(i+1,len(a)):
            if j==i+1 or i==0 and j==len(a)-1:continue
            d,e=a[j],a[(j+1)%len(a)]
            if cross(b,c,d)*cross(b,c,e)<0 and cross(d,e,b)*cross(d,e,c)<0 or any((on(b,c,d),on(b,c,e),on(d,e,b),on(d,e,c))):raise ValueError('Section polygon is self-intersecting')
    area=sum(a[i,0]*a[(i+1)%len(a),1]-a[(i+1)%len(a),0]*a[i,1] for i in range(len(a)))
    if abs(area)<1e-9:raise ValueError('Section has zero area')
    return a


def contains(u,v,vertices):
    inside=np.zeros(np.broadcast_shapes(np.shape(u),np.shape(v)),dtype=bool);boundary=inside.copy()
    for a,b in zip(vertices,np.roll(vertices,-1,axis=0)):
        du,dv=b-a
        boundary|=(abs((u-a[0])*dv-(v-a[1])*du)<1e-8)&(u>=min(a[0],b[0])-1e-8)&(u<=max(a[0],b[0])+1e-8)&(v>=min(a[1],b[1])-1e-8)&(v<=max(a[1],b[1])+1e-8)
        if abs(dv)>1e-12:inside^=((a[1]>v)!=(b[1]>v))&(u<(b[0]-a[0])*(v-a[1])/dv+a[0])
    return inside|boundary


def section_mask(grid,spec):
    from nbt_tools import xyz
    kind=spec['shape'];result=np.zeros(grid.size,dtype=bool)
    if kind=='section_sweep':
        vertices=polygon(spec['vertices']);points=np.asarray([xyz(p) for p in spec['points']],dtype=float)
        if not 2<=len(points)<=128 or math.prod(grid.size)*(len(points)-1)*len(vertices)>128_000_000:raise ValueError('Sweep sampling budget exceeded')
        up=np.asarray(xyz(spec.get('up',[0,1,0])),dtype=float)
        if np.linalg.norm(up)<1e-9:raise ValueError('Sweep up vector is zero')
        for a,b in zip(points,points[1:]):
            tangent=b-a;length=np.linalg.norm(tangent)
            if length<1e-9:raise ValueError('Sweep has coincident points')
            tangent/=length;u=np.cross(up,tangent)
            if np.linalg.norm(u)<1e-8:raise ValueError('Sweep up vector parallel to path; choose another up')
            u/=np.linalg.norm(u);v=np.cross(tangent,u)
            delta=[c-a[i] for i,c in enumerate((grid.x,grid.y,grid.z))]
            along=sum(delta[i]*tangent[i] for i in range(3));horizontal=sum(delta[i]*u[i] for i in range(3));vertical=sum(delta[i]*v[i] for i in range(3))
            result|=(along>=0)&(along<=length)&contains(horizontal,vertical,vertices)
    elif kind=='loft':
        sections=spec['sections']
        if not 2<=len(sections)<=64:raise ValueError('Loft needs 2..64 sections')
        ys=[section['y'] for section in sections]
        if any(type(y) not in (int,float) or not math.isfinite(y) for y in ys) or any(b<=a for a,b in zip(ys,ys[1:])):raise ValueError('Loft heights must strictly increase')
        polygons=[polygon(section['vertices']) for section in sections]
        if len({len(p) for p in polygons})!=1:raise ValueError('Loft sections need matching vertex counts and order')
        for j in range(grid.size[1]):
            # Modelling grid coordinates may have global offsets.
            y=float(grid.y[0,j,0])
            if not ys[0]<=y<=ys[-1]:continue
            i=min(next((k for k in range(len(ys)-1) if y<=ys[k+1]),len(ys)-2),len(ys)-2)
            t=(y-ys[i])/(ys[i+1]-ys[i]);vertices=polygon(polygons[i]*(1-t)+polygons[i+1]*t)
            result[:,j,:]=np.broadcast_to(contains(grid.x[:,0,:],grid.z[0,:,:],vertices),(grid.size[0],grid.size[2]))
    elif kind=='revolve':
        vertices=polygon(spec['profile'])
        if np.any(vertices[:,0]<0):raise ValueError('Revolve radii must be nonnegative')
        centre=xyz(spec.get('centre',[0,0,0]));radial=np.sqrt((grid.x-centre[0])**2+(grid.z-centre[2])**2)
        result=np.broadcast_to(contains(radial,grid.y-centre[1],vertices),grid.size).copy()
        angle=spec.get('start_angle',0);sweep=spec.get('sweep_angle',360)
        if any(type(a) not in (int,float) or not math.isfinite(a) for a in (angle,sweep)) or not 0<sweep<=360:raise ValueError('Revolve sweep must be (0,360] degrees')
        if sweep<360:
            theta=(np.degrees(np.arctan2(grid.x-centre[0],-(grid.z-centre[2])))-angle)%360
            result&=theta<=sweep
    else:raise ValueError('Unknown section geometry')
    return result
