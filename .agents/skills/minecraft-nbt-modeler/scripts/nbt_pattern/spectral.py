"""Bounded real-FFT stencil filtering; never a voxel/route solver shortcut."""
from math import log2
import numpy as np


def kernel_for(kind,radius):
    if kind not in ('gaussian','disk') or type(radius) is not int or not 1<=radius<=128:raise ValueError('滤波核须为gaussian/disk，半径1～128像素')
    axis=np.arange(-radius,radius+1,dtype=float)
    if kind=='gaussian':
        weights=np.exp(-.5*(axis/max(.5,radius/3))**2);weights/=weights.sum()
        kernel=weights[:,None]*weights[None,:]
    else:kernel=(axis[:,None]**2+axis[None,:]**2<=radius*radius).astype(float)
    return kernel/kernel.sum()


def smooth(image,kind,radius,boundary='reflect',method='auto',backend='auto'):
    values=np.asarray(image,dtype=float)
    if values.ndim!=2 or min(values.shape)<1 or max(values.shape)>512 or not np.isfinite(values).all():raise ValueError('频域处理须为有限二维数据，每轴最多512像素')
    if boundary not in ('reflect','wrap','zero') or method not in ('auto','spatial','fft'):raise ValueError('滤波边界或算法无效')
    kernel=kernel_for(kind,radius);height,width=values.shape
    padded=np.pad(values,radius,mode='constant' if boundary=='zero' else boundary)
    shape=tuple(1<<(n+len(kernel)-2).bit_length() for n in padded.shape)
    spatial_cost=height*width*int(np.count_nonzero(kernel))
    fft_cost=3*shape[0]*shape[1]*sum(log2(n) for n in shape)
    selected='spatial' if method=='auto' and (kind=='gaussian' or spatial_cost<=fft_cost) else 'fft' if method=='auto' else method
    if selected=='spatial' and kind=='disk' and spatial_cost>200_000_000:raise ValueError('空间卷积工作量过大，请使用auto或fft')
    from nbt_compute import execute
    # Convolution stays numerically identical. Only dense FFT work is selected
    # automatically; tiny micro-patterns avoid importing/initializing CUDA.
    def calculate(xp):
        signal=xp.asarray(padded);weights2=xp.asarray(kernel)
        if selected=='fft':
            spectrum=xp.fft.rfft2(signal,s=shape)*xp.fft.rfft2(weights2,s=shape)
            full=xp.fft.irfft2(spectrum,s=shape)
            return full[2*radius:2*radius+height,2*radius:2*radius+width]
        if kind=='gaussian':
            weights=kernel.sum(axis=0)
            if xp is np:
                horizontal=np.apply_along_axis(lambda row:np.convolve(row,weights,'valid'),1,padded)
                return np.apply_along_axis(lambda column:np.convolve(column,weights,'valid'),0,horizontal)
            horizontal=xp.zeros((padded.shape[0],width),dtype=xp.float64)
            for i,weight in enumerate(weights):horizontal+=weight*signal[:,i:i+width]
            output=xp.zeros((height,width),dtype=xp.float64)
            for i,weight in enumerate(weights):output+=weight*horizontal[i:i+height,:]
            return output
        output=xp.zeros((height,width),dtype=xp.float64)
        for y,x in zip(*np.nonzero(kernel)):output+=kernel[y,x]*signal[y:y+height,x:x+width]
        return output
    output,compute=execute(backend,selected=='fft' and values.size>=65536,calculate,estimated_bytes=shape[0]*shape[1]*96)
    algorithm=('numpy' if compute['actual']=='cpu' else 'cupy')+('_real_fft_linear_convolution' if selected=='fft' else '_separable_gaussian' if kind=='gaussian' else '_spatial_disk_convolution')
    return output,dict(algorithm=algorithm,kernel=kind,radius=radius,kernel_size=list(kernel.shape),boundary=boundary,
        fft_shape=list(shape) if selected=='fft' else None,selection='estimated_cost' if method=='auto' else 'explicit',compute=compute)



def filter_values(image,args):
    values=np.asarray(image,dtype=float)
    mode=args.get('filter','lowpass');radius=args.get('radius',4)
    if mode not in ('lowpass','highpass','bandpass'):raise ValueError('未知频段操作')
    if ('outer_radius' in args)!=(mode=='bandpass'):raise ValueError('只有bandpass须提供outer_radius')
    low,report=smooth(values,args.get('kernel','gaussian'),radius,args.get('boundary','reflect'),args.get('method','auto'),args.get('backend','auto'))
    reports=[report]
    if mode=='lowpass':output=low
    elif mode=='highpass':output=np.abs(values-low)
    else:
        if args['outer_radius']<=radius:raise ValueError('带通outer_radius须大于radius')
        outer,receipt=smooth(values,args.get('kernel','gaussian'),args['outer_radius'],args.get('boundary','reflect'),args.get('method','auto'),args.get('backend','auto'))
        reports.append(receipt);output=np.abs(low-outer)
    if args.get('normalize',False) and float(np.ptp(output))>1e-9:output=(output-output.min())*255/np.ptp(output)
    output=np.rint(np.clip(output,0,255)).astype(np.uint8)
    return output,dict(filter=mode,operations=reports,normalized=args.get('normalize',False),
        response='absolute_residual' if mode!='lowpass' else 'smoothed_luminance',
        scope='grayscale image preprocessing; topology and microfit quality must be checked after filtering')


def create_filtered(workspace,args):
    from PIL import Image,ImageOps
    from nbt_pattern.assets import load,store
    from nbt_pattern.design import gray
    from nbt_pattern.ornament_sample import read_raster,crop_image
    from pathlib import Path
    reference=args['source'];asset=load(workspace,reference['id'])
    if asset['image_sha256']!=reference['image_sha256']:raise ValueError('源纹样图像已变化')
    raster=crop_image(read_raster(Path(asset['image']).read_bytes()),args.get('crop'))
    image=gray(raster,args.get('channel','luminance'));original_size=list(image.size)
    if 'resolution' in args:image=image.resize(tuple(args['resolution']),Image.Resampling.BOX)
    elif max(image.size)>512:image=ImageOps.contain(image,(512,512),Image.Resampling.BOX)
    output,report=filter_values(image,args)
    if not output.any():raise ValueError('滤波结果为空；请调整频段或使用其他源，未创建资产')
    # Re-read the bound source after numerical work, before creating a new ID.
    again=load(workspace,reference['id'])
    if again['image_sha256']!=reference['image_sha256']:raise ValueError('处理期间源纹样图像已变化')
    report.update(source_size=original_size,output_size=list(image.size))
    recipe=dict(generator='nbt_spectral',revision=1,parameters=args,processing=report)
    result=store(workspace,Image.fromarray(output),args['name'],args.get('tags',[]),recipe)
    return dict(result,processing=report,source_modified=False)
