"""Inverse coordinate maps for bounded architectural fields and image patterns."""
from math import pi
import numpy as np


def validate_transforms(transforms,image=False):
    if image:
        fields={'affine':({'matrix'},{'matrix'}),'swirl':({'centre','radius','degrees'},{'radius','degrees'}),
            'wave':({'axis','amplitude','wavelength','phase'},{'amplitude','wavelength'}),
            'polar_repeat':({'centre','sectors','rotation','mirror'},{'sectors'})}
    else:
        fields={'affine':({'matrix','centre','offset'},{'matrix'}),'bend':({'plane','radius','centre'},{'radius'}),
            'twist':({'axis','centre','degrees','length'},{'degrees','length'}),'taper':({'axis','centre','amount','length'},{'amount','length'}),
            'shear':({'axis','driver','centre','amount'},{'driver','amount'}),'wave':({'axis','driver','centre','amplitude','wavelength','phase'},{'driver','amplitude','wavelength'})}
    for t in transforms:
        if t['kind'] not in fields:raise ValueError('未知变换类型')
        allowed,required=fields[t['kind']]
        if set(t)-allowed-{'kind'} or not required<=set(t):raise ValueError('变换参数与kind不匹配：'+t['kind'])


def coordinates(points,transforms,xp):
    """Transforms are listed in forward design order; sample in reverse order."""
    q=list(points)
    for t in reversed(transforms):
        kind=t['kind'];c=t.get('centre',[0,0,0]);v=[q[i]-c[i] for i in range(3)]
        if kind=='affine':
            matrix=np.asarray(t['matrix'],dtype=float)
            if matrix.shape!=(3,3) or not np.isfinite(matrix).all() or abs(np.linalg.det(matrix))<1e-6:raise ValueError('affine矩阵须可逆')
            inverse=np.linalg.inv(matrix);offset=t.get('offset',[0,0,0]);v=[v[i]-offset[i] for i in range(3)]
            v=[sum(inverse[i,j]*v[j] for j in range(3)) for i in range(3)]
        elif kind=='bend':
            a,b={'xy':(0,1),'yz':(1,2),'xz':(0,2)}[t.get('plane','xy')];radius=t['radius']
            if radius<=0:raise ValueError('bend半径须为正')
            va,vb=v[a],v[b]+radius
            # Reject a singular inverse rather than inventing a centreline.
            if bool(xp.any(va*va+vb*vb<1e-12)):raise ValueError('bend采样域经过弯曲奇点，请调整半径或中心')
            v[a]=radius*xp.arctan2(va,vb);v[b]=xp.sqrt(va*va+vb*vb)-radius
        else:
            axis='xyz'.index(t.get('axis','y'));other=[i for i in range(3) if i!=axis]
            if kind=='twist':
                length=t['length']
                if length<=0:raise ValueError('twist长度须为正')
                angle=-t['degrees']*pi/180*v[axis]/length;co=xp.cos(angle);si=xp.sin(angle);a,b=other
                va,vb=v[a],v[b];v[a]=co*va-si*vb;v[b]=si*va+co*vb
            elif kind=='taper':
                if t['length']<=0:raise ValueError('taper长度须为正')
                factor=1+t['amount']*v[axis]/t['length']
                if bool(xp.any(factor<=.05)):raise ValueError('taper缩放接近零或翻转，请调整参数')
                for i in other:v[i]=v[i]/factor
            elif kind in ('shear','wave'):
                driver='xyz'.index(t['driver'])
                if axis==driver:raise ValueError('位移轴与驱动轴须不同')
                if kind=='shear':v[axis]=v[axis]-t['amount']*v[driver]
                else:
                    if t['wavelength']<=0:raise ValueError('wave波长须为正')
                    v[axis]=v[axis]-t['amplitude']*xp.sin(2*pi*v[driver]/t['wavelength']+t.get('phase',0)*pi/180)
            else:raise ValueError('未知体积变换')
        q=[v[i]+c[i] for i in range(3)]
    return q


def image_coordinates(u,v,transforms,xp):
    for t in reversed(transforms):
        kind=t['kind'];cx,cy=t.get('centre',[.5,.5]);x=u-cx;y=v-cy
        if kind=='affine':
            matrix=np.asarray(t['matrix'],dtype=float)
            if matrix.shape!=(3,3) or not np.isfinite(matrix).all() or abs(np.linalg.det(matrix))<1e-6:raise ValueError('纹样透视矩阵须可逆')
            m=np.linalg.inv(matrix);den=m[2,0]*u+m[2,1]*v+m[2,2]
            if float(xp.min(den))<=1e-6 and float(xp.max(den))>=-1e-6:raise ValueError('透视采样域经过无穷远，请调整矩阵')
            u,v=(m[0,0]*u+m[0,1]*v+m[0,2])/den,(m[1,0]*u+m[1,1]*v+m[1,2])/den
        elif kind=='swirl':
            radius=t['radius']
            if radius<=0:raise ValueError('swirl半径须为正')
            r=xp.sqrt(x*x+y*y);falloff=xp.maximum(0,1-r/radius)**2
            angle=-t['degrees']*pi/180*falloff;co=xp.cos(angle);si=xp.sin(angle)
            u=cx+co*x-si*y;v=cy+si*x+co*y
        elif kind=='wave':
            if t['wavelength']<=0:raise ValueError('纹样wave波长须为正')
            if t.get('axis','x')=='x':u=u-t['amplitude']*xp.sin(2*pi*v/t['wavelength']+t.get('phase',0)*pi/180)
            else:v=v-t['amplitude']*xp.sin(2*pi*u/t['wavelength']+t.get('phase',0)*pi/180)
        elif kind=='polar_repeat':
            sectors=t['sectors'];angle=xp.arctan2(y,x)-t.get('rotation',0)*pi/180
            period=2*pi/sectors;angle=(angle+period/2)%period-period/2
            if t.get('mirror',False):angle=xp.abs(angle)
            r=xp.sqrt(x*x+y*y);u=cx+r*xp.cos(angle);v=cy+r*xp.sin(angle)
        else:raise ValueError('未知纹样变换')
    return u,v


def warp_pixels(pixels,args,quantize=True):
    from nbt_compute import execute
    pixels=np.asarray(pixels,dtype=float);height,width=pixels.shape[:2];w,h=args.get('resolution',[width,height]);transforms=args['transforms']
    validate_transforms(transforms,image=True)
    def calculate(xp):
        u=xp.arange(w,dtype=xp.float64)[None,:]/max(1,w-1);v=xp.arange(h,dtype=xp.float64)[:,None]/max(1,h-1)
        u,v=image_coordinates(u,v,transforms,xp);u,v=xp.broadcast_arrays(u,v)
        boundary=args.get('boundary','zero');valid=(u>=0)&(u<=1)&(v>=0)&(v<=1)
        if boundary=='wrap':u=u%1;v=v%1
        elif boundary not in ('zero','clamp'):raise ValueError('未知纹样边界')
        u=xp.clip(u,0,1)*(width-1);v=xp.clip(v,0,1)*(height-1)
        x=xp.floor(u).astype(xp.int32);y=xp.floor(v).astype(xp.int32);xx=xp.minimum(x+1,width-1);yy=xp.minimum(y+1,height-1)
        fx=u-x;fy=v-y;data=xp.asarray(pixels)
        if pixels.ndim==3:fx=fx[...,None];fy=fy[...,None];valid=valid[...,None]
        result=(data[y,x]*(1-fx)+data[y,xx]*fx)*(1-fy)+(data[yy,x]*(1-fx)+data[yy,xx]*fx)*fy
        return xp.where(valid,result,0) if boundary=='zero' else result
    values,report=execute(args.get('backend','auto'),w*h*len(transforms)>=250_000,calculate,estimated_bytes=w*h*256)
    return (np.rint(np.clip(values,0,255)).astype(np.uint8) if quantize else values),report


def create_warped(workspace,args):
    from PIL import Image
    from pathlib import Path
    from nbt_pattern.assets import load,store
    from nbt_pattern.ornament_sample import read_raster,crop_image
    reference=args['source'];asset=load(workspace,reference['id'])
    if asset['image_sha256']!=reference['image_sha256']:raise ValueError('源纹样图像已变化')
    raster=crop_image(read_raster(Path(asset['image']).read_bytes()),args.get('crop')).convert('RGBA')
    if max(raster.size)>2048:raise ValueError('纹样源每轴最多2048像素，请先裁取区域')
    # Premultiplied alpha prevents dark fringes when transparent art is warped.
    data=np.asarray(raster,dtype=float);data[...,:3]*=data[...,3:4]/255
    output,compute=warp_pixels(data,args,quantize=False);alpha=output[...,3:4]
    output[...,:3]=np.divide(output[...,:3]*255,alpha,out=np.zeros_like(output[...,:3]),where=alpha>0)
    image=Image.fromarray(np.rint(np.clip(output,0,255)).astype(np.uint8))
    again=load(workspace,reference['id'])
    if again['image_sha256']!=reference['image_sha256']:raise ValueError('变换期间源纹样图像已变化')
    recipe=dict(generator='nbt_deform',revision=1,parameters=args,compute=compute)
    result=store(workspace,image,args['name'],args.get('tags',[]),recipe)
    return dict(result,compute=compute,source_modified=False,topology_preserved='not_guaranteed_recheck_after_fitting')
