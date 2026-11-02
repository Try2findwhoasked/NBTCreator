"""Implicit voxel geometry without a predefined room layout. Requires numpy.

Fields are negative inside and positive outside. Ellipsoids, variable-radius
tubes and warped fields are sign-correct implicit fields, NOT exact signed
distance functions. Boolean CSG is valid; smooth blending needs visual review.
All samples are taken at block centres. Box bounds here are continuous surfaces,
unlike Model.box's inclusive integer bounds.
"""
import math
import numpy as np


def union(*fields):
    if not fields:
        raise ValueError('union requires at least one field')
    return np.minimum.reduce(np.broadcast_arrays(*fields))


def intersection(*fields):
    if not fields:
        raise ValueError('intersection requires at least one field')
    return np.maximum.reduce(np.broadcast_arrays(*fields))


def difference(a, b):
    return np.maximum(a, -b)


def smooth_union(a, b, radius):
    if radius <= 0:
        raise ValueError('Blend radius must be positive')
    t = np.clip(.5 + .5 * (b-a)/radius, 0, 1)
    return b*(1-t)+a*t-radius*t*(1-t)


def bezier(controls, samples=64):
    points=np.asarray(controls,dtype=float)
    if points.ndim!=2 or points.shape[1]!=3 or len(points)<2 or samples<2:
        raise ValueError('Bezier needs >=2 XYZ controls and >=2 samples')
    t=np.linspace(0,1,samples)[:,None]
    degree=len(points)-1
    result=sum(math.comb(degree,i)*(1-t)**(degree-i)*t**i*p for i,p in enumerate(points))
    return result.tolist()


class Grid:
    def __init__(self, size, coordinates=None):
        self.size=tuple(size)
        if len(size)!=3 or any(type(n) is not int or n<=0 for n in size):
            raise ValueError('size must be three positive integers')
        if coordinates is None:
            self.x=np.arange(size[0],dtype=float)[:,None,None]+.5
            self.y=np.arange(size[1],dtype=float)[None,:,None]+.5
            self.z=np.arange(size[2],dtype=float)[None,None,:]+.5
        else:
            self.x,self.y,self.z=coordinates

    def warped(self, amplitude=1.0, wavelength=16.0, seed=0):
        """Low-frequency coordinate warp, deterministic; does not add holes.

        Amplitude should remain well below intended shell thickness. A flood
        and route check remain necessary after any warp or voxel sampling.
        """
        if amplitude<0 or wavelength<=0:
            raise ValueError('Invalid warp parameters')
        rng=np.random.default_rng(seed)
        phases=rng.uniform(0,math.tau,6)
        k=math.tau/wavelength
        x,y,z=self.x,self.y,self.z
        dx=amplitude*np.sin(k*y+phases[0])*np.cos(k*z*.7+phases[1])
        dy=amplitude*np.sin(k*z*.8+phases[2])*np.cos(k*x*.6+phases[3])
        dz=amplitude*np.sin(k*x*.75+phases[4])*np.cos(k*y*.55+phases[5])
        return Grid(self.size,(x+dx,y+dy,z+dz))

    def ellipsoid(self, centre, radii, rotation=None):
        c=np.asarray(centre,dtype=float);r=np.asarray(radii,dtype=float)
        if c.shape!=(3,) or r.shape!=(3,) or np.any(r<=0):
            raise ValueError('Ellipsoid needs XYZ centre and positive XYZ radii')
        delta=[self.x-c[0],self.y-c[1],self.z-c[2]]
        if rotation is not None:
            matrix=np.asarray(rotation,dtype=float)
            if matrix.shape!=(3,3) or not np.allclose(matrix.T@matrix,np.eye(3),atol=1e-6):
                raise ValueError('rotation must be an orthonormal 3x3 matrix')
            delta=[sum(matrix[j,i]*delta[j] for j in range(3)) for i in range(3)]
        return (np.sqrt(sum((delta[i]/r[i])**2 for i in range(3)))-1)*r.min()

    def box(self, lo, hi):
        lo=np.asarray(lo,dtype=float);hi=np.asarray(hi,dtype=float)
        if lo.shape!=(3,) or hi.shape!=(3,) or np.any(hi<=lo):
            raise ValueError('Box uses continuous lo<hi surfaces')
        return intersection(*(np.maximum(lo[i]-v,v-hi[i]) for i,v in enumerate((self.x,self.y,self.z))))

    def tube(self, points, radii):
        """Piecewise linear 3D sweep, radius is scalar or one value per point.

        Use enough samples for the voxel resolution; radii interpolate along
        each segment. This deliberately avoids presupposing straight corridors.
        """
        points=np.asarray(points,dtype=float)
        if points.ndim!=2 or points.shape[1]!=3 or len(points)<2:
            raise ValueError('Tube needs >=2 XYZ points')
        radii=np.broadcast_to(np.asarray(radii,dtype=float),(len(points),))
        if np.any(radii<=0):
            raise ValueError('Tube radii must be positive')
        result=np.full(self.size,np.inf)
        for i,(a,b) in enumerate(zip(points,points[1:])):
            v=b-a;den=float(v@v)
            if den<1e-12:
                raise ValueError('Tube has coincident adjacent points')
            delta=[self.x-a[0],self.y-a[1],self.z-a[2]]
            t=np.clip(sum(delta[j]*v[j] for j in range(3))/den,0,1)
            distance=np.sqrt(sum((delta[j]-t*v[j])**2 for j in range(3)))
            result=np.minimum(result,distance-((1-t)*radii[i]+t*radii[i+1]))
        return result

    def torus(self, centre, major_radius, minor_radius):
        if major_radius<=0 or minor_radius<=0:
            raise ValueError('Torus radii must be positive')
        x,y,z=self.x-centre[0],self.y-centre[1],self.z-centre[2]
        return np.sqrt((np.sqrt(x*x+z*z)-major_radius)**2+y*y)-minor_radius

    def extruded_polygon(self, vertices, bottom, top):
        """Irregular simple XZ polygon extruded vertically. Field sign only."""
        if len(vertices)<3 or top<=bottom:
            raise ValueError('Need >=3 XZ vertices and bottom<top')
        # Evaluate on this grid (warp may expand coordinate array dimensions).
        inside=np.zeros(np.broadcast_shapes(np.shape(self.x),np.shape(self.z)),dtype=bool)
        previous=vertices[-1]
        for current in vertices:
            ax,az=previous;bx,bz=current
            if abs(bz-az)>1e-12:
                inside ^= ((az>self.z)!=(bz>self.z)) & (self.x<(bx-ax)*(self.z-az)/(bz-az)+ax)
            previous=current
        horizontal=np.where(inside,-1.,1.)
        return intersection(horizontal,np.maximum(bottom-self.y,self.y-top))

    def mask(self, field, boundary_margin=0):
        result=np.array(np.broadcast_to(field,self.size)<=0,copy=True)
        if boundary_margin:
            if type(boundary_margin) is not int or boundary_margin<0 or 2*boundary_margin>=min(self.size):
                raise ValueError('Invalid boundary margin')
            n=boundary_margin
            result[:n,:,:]=False;result[-n:,:,:]=False
            result[:,:n,:]=False;result[:,-n:,:]=False
            result[:,:,:n]=False;result[:,:,-n:]=False
        return result


def apply_mask(model, mask, material):
    """Write only mask=true cells; never silently clip coordinates or protect paths."""
    mask=np.asarray(mask,dtype=bool)
    if mask.shape!=model.size:
        raise ValueError('Mask shape and model size differ')
    for p in np.argwhere(mask):
        model.put(tuple(int(v) for v in p),material)
    return int(mask.sum())


def connectivity(mask, probes):
    """6-neighbour interior connectivity; does NOT certify a player route."""
    from collections import deque
    mask=np.asarray(mask,dtype=bool)
    probes=[tuple(p) for p in probes]
    if not probes or any(len(p)!=3 or any(type(v) is not int for v in p) or
        not all(0<=p[i]<mask.shape[i] for i in range(3)) or not mask[p] for p in probes):
        raise ValueError('Probes must be integer cells inside the mask')
    seen={probes[0]};queue=deque(seen)
    while queue:
        x,y,z=queue.popleft()
        for p in ((x-1,y,z),(x+1,y,z),(x,y-1,z),(x,y+1,z),(x,y,z-1),(x,y,z+1)):
            if p not in seen and all(0<=p[i]<mask.shape[i] for i in range(3)) and mask[p]:
                seen.add(p);queue.append(p)
    return dict(passed=all(p in seen for p in probes), connected_cells=len(seen),
                selected_cells=int(mask.sum()), all_selected_cells_connected=len(seen)==int(mask.sum()))


def air_components(model, probes):
    """Describe all actual air components, including exterior and tiny pockets.

    Run before opening, or on a diagnostic copy with declared ports restored.
    Does not mutate the model, auto-fill pockets, or certify walking routes.
    """
    from collections import deque
    from nbt_model import AIR_NAMES
    probes=[tuple(p) for p in probes]
    if any(len(p)!=3 or any(type(v) is not int for v in p) or not model.in_bounds(p) or
           model.get(p) not in AIR_NAMES for p in probes):
        raise ValueError('Probes must be integer air cells')
    sx,sy,sz=model.size
    remaining={(x,y,z) for x in range(sx) for y in range(sy) for z in range(sz)
               if model.get((x,y,z)) in AIR_NAMES}
    components=[]
    while remaining:
        origin=min(remaining);remaining.remove(origin)
        cells={origin};queue=deque([origin]);exterior=False
        while queue:
            x,y,z=queue.popleft()
            if x in (0,sx-1) or y in (0,sy-1) or z in (0,sz-1):exterior=True
            for p in ((x-1,y,z),(x+1,y,z),(x,y-1,z),(x,y+1,z),(x,y,z-1),(x,y,z+1)):
                if p in remaining:
                    remaining.remove(p);cells.add(p);queue.append(p)
        attached=[list(p) for p in probes if p in cells]
        components.append(dict(cells=len(cells),sample=list(origin),
            minimum=[min(p[i] for p in cells) for i in range(3)],
            maximum=[max(p[i] for p in cells) for i in range(3)],
            touches_exterior=exterior,design_probes=attached))
    return dict(geometry_sha256=model.fingerprint(),components=components,
                undeclared_enclosed_components=[c for c in components if not c['touches_exterior'] and not c['design_probes']],
                leaking_design_probes=[p for c in components if c['touches_exterior'] for p in c['design_probes']],
                note='Air topology only. Exterior air can be split inside the bounding box but connects outside it.')
