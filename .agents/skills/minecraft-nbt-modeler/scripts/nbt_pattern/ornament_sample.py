"""Fit a local raster mask to the decoration plane and vary its threshold."""
from hashlib import sha256
from io import BytesIO
from math import floor
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError


ARCHITECTURAL_SAMPLES = {
    'kashan_star_cross': dict(
        url='https://www.metmuseum.org/art/collection/search/450455',
        rights='Public Domain', use='墙面星形与十字砖拼接',
        preparation='下载后裁出叶纹或制作星十字组合单元。单块十字砖不能直接无缝通铺。',
        suggested_repeat=[2, 2], suggested_layout='continuous'),
    'bursa_vine_frieze': dict(
        url='https://www.metmuseum.org/art/collection/search/453563',
        rights='Public Domain', use='布尔萨陵墓门口边带的交织卷草纹',
        preparation='裁出一段完整卷草周期，用于窄长边带。',
        suggested_repeat=[3, 1], suggested_layout='continuous'),
    'kashan_corner_vine': dict(
        url='https://www.metmuseum.org/art/collection/search/450364',
        rights='Public Domain', use='角部卷草装饰',
        preparation='选单个角部正视图，裁出植物纹样用于角饰。',
        suggested_repeat=[1, 1], suggested_layout='corners'),
}


def read_raster(raw):
    if len(raw)>8*1024*1024:
        raise ValueError('样本图片超过8MiB')
    try:
        with Image.open(BytesIO(raw), formats=['PNG', 'JPEG', 'WEBP']) as source:
            if source.width * source.height > 4_194_304 or getattr(source, 'is_animated', False):
                raise ValueError('样本须为单帧且不超过4194304像素')
            return ImageOps.exif_transpose(source).convert('RGBA')
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise ValueError('样本须为可读取的 PNG、JPEG 或 WebP') from error


def crop_image(image, box):
    if box is None:return image
    import math
    if (not isinstance(box,list) or len(box)!=4 or
        any(type(n) not in (float,int) or not math.isfinite(n) or not 0<=n<=1 for n in box) or
        box[0]>=box[2] or box[1]>=box[3]):
        raise ValueError('crop 须为左上角起算的归一化矩形[x0,y0,x1,y1]')
    left,top=int(box[0]*image.width),int(box[1]*image.height)
    right,bottom=math.ceil(box[2]*image.width),math.ceil(box[3]*image.height)
    return image.crop((left,top,right,bottom))


def sample_image(workspace,settings):
    root = Path(workspace).resolve()
    path = (root / settings['path']).resolve()
    if not path.is_relative_to(root):
        raise ValueError('样本图片须位于工作区内')
    with path.open('rb') as stream:
        raw = stream.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024 or sha256(raw).hexdigest() != settings['sha256']:
        raise ValueError('样本图片过大或 SHA256 不匹配')
    return crop_image(read_raster(raw),settings.get('crop'))


def resize_sample(image, size, fit='contain'):
    """One mapping for mask, alpha and colour; stretch is explicit distortion."""
    if fit == 'stretch':
        return image.resize(size, Image.Resampling.BOX)
    if fit == 'cover':
        return ImageOps.fit(image, size, Image.Resampling.BOX)
    if fit == 'contain':
        return ImageOps.pad(image, size, Image.Resampling.BOX, color=0)
    raise ValueError('sample.fit 须为 contain、cover 或 stretch')


def fit_sample(workspace, settings, width, height, seed, symmetry, repeat=(1, 1), *, subcells=False, return_coverage=False):
    image=sample_image(workspace,settings)
    mask = image.getchannel('A') if settings.get('channel') == 'alpha' else image.convert('L')
    if settings.get('invert'):
        mask = ImageOps.invert(mask)
    alpha = image.getchannel('A')
    columns, rows = repeat
    if columns > width or rows > height:
        raise ValueError('重复次数超过装饰面格数')
    factor = 2 if subcells is True else subcells if type(subcells) is int else 1
    if factor not in (1,2,16,32):raise ValueError('采样细分须为1、2、16或32')
    size = (factor * (width // columns), factor * (height // rows))
    mask = resize_sample(mask, size, settings.get('fit', 'contain'))
    alpha = resize_sample(alpha, size, settings.get('fit', 'contain'))
    colors=image.convert('RGB')
    colors=resize_sample(colors,size,settings.get('fit','contain'))
    from nbt_model import state, AIR_NAMES
    palette=[]
    for entry in settings.get('colors',[]):
        value=state(entry['material'])
        if value in AIR_NAMES:
            raise ValueError('样本配色不能使用空气')
        palette.append((tuple(bytes.fromhex(entry['rgb'][1:])),value))

    def material_at(u,v):
        if not palette:
            return None
        rgb=colors.getpixel(pixel_at(u,v))
        return min(palette,key=lambda entry:sum((a-b)**2 for a,b in zip(rgb,entry[0])))[1]

    amplitude = settings.get('noise_strength', 15) / 100
    scale = settings.get('noise_scale', 4)
    threshold = settings.get('threshold', 50) / 100

    def lattice(x, y):
        return int.from_bytes(sha256(f'{seed}:{x}:{y}'.encode()).digest()[:4], 'big') / 4294967295

    def pixel_at(u,v):
        if symmetry:
            u = min(u, width - 1 / factor - u)
        return (int(u * columns * size[0] // width) % size[0],
                int((height - 1 / factor - v) * rows * size[1] // height) % size[1])

    def strength(u, v):
        pixel=pixel_at(u,v)
        if not alpha.getpixel(pixel):
            return 0
        value = mask.getpixel(pixel) / 255
        x, y = u / scale, v / scale
        a, b = floor(x), floor(y)
        fx, fy = x - a, y - b
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        noise = sum(lattice(a+i,b+j) * wx * wy for i,wx in enumerate((1-fx,fx))
                    for j,wy in enumerate((1-fy,fy)))
        return max(0,min(1,value + amplitude * (2 * noise - 1))) if value>0 else 0

    def sample(u,v):
        value=strength(u,v)
        return value>0 and value>=threshold

    def coverage(u,v):
        return tuple(max(0,min(1,.5+strength(u+x/factor,v+y/factor)-threshold))
                     for y in range(factor) for x in range(factor))

    if subcells:
        result=(lambda u,v:tuple(sample(u+x/factor,v+y/factor) for y in range(factor) for x in range(factor))),material_at
        return (*result,coverage) if return_coverage else result
    if return_coverage:
        return sample,material_at,lambda u,v:(max(0,min(1,.5+strength(u,v)-threshold)),)
    return sample,material_at


def silhouette_options(material, shapes):
    """Project true collision half-cubes onto the wall's local X/Y plane."""
    from nbt_collision import collision_cells
    from nbt_registry import effective
    from nbt_model import state

    options=[(None,(False,)*4)]
    for family in ('slab','stairs'):
        if family not in shapes:
            continue
        name,props=effective(shapes[family])
        if not name.endswith('_'+family) or props.get('waterlogged')!='false':
            raise ValueError('轮廓拟合须使用对应的未含水原版半砖或楼梯')
        for half in ('bottom','top'):
            if family=='slab':
                values=[f'{name}[type={half},waterlogged=false]']
            else:
                values=[f'{name}[half={half},facing={direction},shape=straight,waterlogged=false]'
                        for direction in ('east','west')]
            for value in values:
                cells,_=collision_cells(value)
                projected={(x,y) for x,y,_ in cells}
                options.append((state(value),tuple(p in projected for p in ((0,0),(1,0),(0,1),(1,1)))))
    options.append((material,(True,)*4))
    return options


def match_silhouette(mask, options, coverage=None):
    def score(option):
        _,projected=option
        missing=sum(a and not b for a,b in zip(mask,projected))
        extra=sum(b and not a for a,b in zip(mask,projected))
        # Resolve coarse-mask ties from the original gray coverage, so a
        # partially covered edge chooses its own direction instead of list order.
        gray_error=sum((float(b)-a)**2 for a,b in zip(coverage,projected)) if coverage is not None else 0
        return 2*missing+extra,extra,gray_error
    return min(options,key=score)
