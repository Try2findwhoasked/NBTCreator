"""Bounded data-only bitmap and geometric composition for reusable stencils."""
from PIL import Image,ImageChops,ImageDraw,ImageOps

from nbt_ornament_sample import crop_image,sample_image,read_raster
from nbt_pattern_assets import load,store

COMMON={'kind','blend','box','rotation','repeat','flip_x','flip_y','radial_count','opacity'}
FIELDS={'bitmap':{'rows'},'rect':{'bounds','value','fill','stroke'},
        'ellipse':{'bounds','value','fill','stroke'},'polygon':{'points','value','fill','stroke'},
        'polyline':{'points','value','stroke'},'bezier':{'points','value','stroke','samples'},
        'preset':{'preset','crop','channel'},'asset':{'id','image_sha256','crop','channel'},'sample':{'sample'}}


def gray(image,channel='luminance'):
    rgba=image.convert('RGBA');alpha=rgba.getchannel('A')
    return alpha if channel=='alpha' else ImageChops.multiply(rgba.convert('L'),alpha)


def source(workspace,layer,size):
    kind=layer['kind'];provenance={}
    if set(layer)-COMMON-FIELDS[kind]:raise ValueError('图层含不适用参数：'+kind)
    required={'bitmap':{'rows'},'polygon':{'points'},'polyline':{'points'},'bezier':{'points'},
              'asset':{'id','image_sha256'},'preset':{'preset'},'sample':{'sample'}}.get(kind,set())
    if required-set(layer):raise ValueError('图层缺少参数：'+','.join(sorted(required-set(layer))))
    if kind in ('preset','asset','sample'):
        if kind=='sample':
            settings=layer['sample']
            if set(settings)-{'path','sha256','crop','channel'}:raise ValueError('组合的sample只接收图像、crop和channel；拟合参数在最终sample设置')
            image=sample_image(workspace,settings);channel=settings.get('channel','luminance')
            provenance=dict(sample=settings)
        else:
            identifier='builtin:'+layer['preset'] if kind=='preset' else layer['id']
            asset=load(workspace,identifier)
            if kind=='asset' and layer.get('image_sha256')!=asset['image_sha256']:raise ValueError('图层源纹样图像已变化')
            from pathlib import Path
            image=crop_image(read_raster(Path(asset['image']).read_bytes()),layer.get('crop'))
            channel=layer.get('channel','luminance')
            provenance=dict(id=identifier,image_sha256=asset['image_sha256'],crop=layer.get('crop'))
        return gray(image,channel).resize(size,Image.Resampling.LANCZOS),provenance
    if kind=='bitmap':
        rows=layer['rows'];width=len(rows[0])
        if not width or width>128 or any(len(row)!=width for row in rows):raise ValueError('小位图各行须等宽且最多128像素')
        image=Image.new('L',(width,len(rows)))
        try:image.putdata([255 if c=='#' else 0 if c=='.' else int(c,16)*17 for row in rows for c in row])
        except ValueError:raise ValueError('位图字符限于 . # 和十六进制0～f') from None
        return image.resize(size,Image.Resampling.NEAREST),provenance
    image=Image.new('L',size);draw=ImageDraw.Draw(image);value=layer.get('value',255)
    stroke=max(1,round(layer.get('stroke',.04)*min(size)))
    if kind in ('rect','ellipse'):
        bounds=layer.get('bounds',[0,0,1,1])
        if bounds[0]>=bounds[2] or bounds[1]>=bounds[3]:raise ValueError('绘图bounds须为正面积矩形')
        points=tuple(round(v*(size[i%2]-1)) for i,v in enumerate(bounds))
        getattr(draw,'rectangle' if kind=='rect' else 'ellipse')(points,fill=value if layer.get('fill',True) else None,outline=value,width=stroke)
    else:
        points=layer['points']
        if kind=='bezier' and len(points)!=4:raise ValueError('三次贝塞尔曲线须有4个控制点')
        if kind=='polygon' and len(points)<3:raise ValueError('多边形至少有3个点')
        points=[(x*(size[0]-1),y*(size[1]-1)) for x,y in points]
        if kind=='bezier':
            path=[]
            samples=layer.get('samples',257)
            for step in range(samples):
                t=step/(samples-1);s=1-t
                weights=(s**3,3*s*s*t,3*s*t*t,t**3)
                path.append(tuple(sum(weights[j]*points[j][i] for j in range(4)) for i in range(2)))
            draw.line(path,fill=value,width=stroke,joint='curve')
        elif kind=='polyline':draw.line(points,fill=value,width=stroke,joint='curve')
        elif layer.get('fill',True):draw.polygon(points,fill=value)
        else:draw.line(points+[points[0]],fill=value,width=stroke,joint='curve')
    return image,provenance


def create(workspace,args):
    width,height=args.get('resolution',[16,16]);size=(width*4,height*4)
    canvas=Image.new('L',size,args.get('background',0));sources=[]
    for layer in args['layers']:
        image,receipt=source(workspace,layer,size)
        if receipt:sources.append(receipt)
        if layer.get('flip_x'):image=ImageOps.mirror(image)
        if layer.get('flip_y'):image=ImageOps.flip(image)
        copies=layer.get('radial_count',1);rotated=Image.new('L',size)
        for index in range(copies):
            angle=layer.get('rotation',0)+index*360/copies
            rotated=ImageChops.lighter(rotated,image.rotate(angle,resample=Image.Resampling.BICUBIC))
        box=layer.get('box',[0,0,1,1])
        if box[0]>=box[2] or box[1]>=box[3]:raise ValueError('图层box须为正面积矩形')
        left,top=round(box[0]*size[0]),round(box[1]*size[1])
        right,bottom=round(box[2]*size[0]),round(box[3]*size[1])
        columns,rows=layer.get('repeat',[1,1])
        if right-left<columns or bottom-top<rows:raise ValueError('图层重复数超过有效区域像素')
        paint=Image.new('L',size)
        for column in range(columns):
            for row in range(rows):
                x0=left+(right-left)*column//columns;x1=left+(right-left)*(column+1)//columns
                y0=top+(bottom-top)*row//rows;y1=top+(bottom-top)*(row+1)//rows
                paint.paste(rotated.resize((x1-x0,y1-y0),Image.Resampling.LANCZOS),(x0,y0))
        opacity=layer.get('opacity',1)
        if opacity!=1:paint=paint.point([round(n*opacity) for n in range(256)])
        blend=layer.get('blend','union')
        operators={'union':ImageChops.lighter,'subtract':ImageChops.subtract,'intersect':ImageChops.darker,
                   'xor':ImageChops.difference,'add':ImageChops.add}
        canvas=operators[blend](canvas,paint)
    image=canvas.resize((width,height),Image.Resampling.BOX)
    if not image.getbbox():raise ValueError('组合结果为空，请调整图层和镂空范围')
    foreground=sum(image.histogram()[128:])
    seam_x=sum(abs(image.getpixel((0,y))-image.getpixel((width-1,y))) for y in range(height))/(255*height)
    seam_y=sum(abs(image.getpixel((x,0))-image.getpixel((x,height-1))) for x in range(width))/(255*width)
    recipe=dict(generator='nbt_pattern_design',revision=2,parameters=dict(args,resolution=[width,height]),sources=sources,
                analysis=dict(foreground_fraction=foreground/(width*height),edge_mismatch_x=seam_x,edge_mismatch_y=seam_y))
    return store(workspace,image,args['name'],args.get('tags',[]),recipe)
