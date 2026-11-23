"""Repeat measured YZ sections from normalized one-sided Fourier coefficients."""
import hashlib
import json

import numpy as np

from nbt_model import AIR_NAMES, state


def _native_classes(spectrum):
    samples = spectrum['samples']
    channels = spectrum['channels']
    bins = samples // 2 + 1
    if len(channels) > samples or any(len(c['coefficients']) != bins for c in channels):
        raise ValueError('频谱通道或频点数量与原始采样数不符')
    pairs = np.asarray([c['coefficients'] for c in channels], dtype=np.float64)
    tolerance = 1e-6
    real_bins = [0, -1] if samples % 2 == 0 else [0]
    if np.any(np.abs(pairs[:, real_bins, 1]) > tolerance):
        raise ValueError('直流和偶数采样的奈奎斯特频点必须为实数')
    # Coefficients are rfft(one_hot, norm="forward"). Validate the actual
    # inverse before snapping to integers so corrupt spectra cannot invent cells.
    signal = np.fft.irfft(pairs[:, :, 0] + 1j * pairs[:, :, 1],
                          n=samples, axis=1, norm='forward')
    active = np.abs(signal - 1) <= tolerance
    if (np.any(~active & (np.abs(signal) > tolerance))
            or np.any(active.sum(axis=0) != 1) or not np.all(active.any(axis=1))):
        raise ValueError('逆变换后每个原始采样必须唯一对应一个截面类别')
    return active.argmax(axis=0).tolist()


def compile_repeat(workspace, arguments):
    from nbt_agent.structure import build

    required = {'kind', 'size', 'spectrum', 'period', 'phase'}
    if not required <= arguments.keys() or arguments.keys() - required - {'name', 'max_changed_blocks'}:
        raise ValueError('频谱配方需要 spectrum、period、phase，只接受名称、尺寸及方块预算调整')
    spectrum = arguments['spectrum']
    width, height, depth = arguments['size']
    if (height, depth) != (spectrum['height'], spectrum['depth']):
        raise ValueError('截面高度与厚度须与频谱一致')
    palette = [state(value) for value in spectrum['palette']]
    if set(palette) & AIR_NAMES:
        raise ValueError('空位置须省略，频谱调色板只接受实体方块')
    sections = [channel['cells'] for channel in spectrum['channels']]
    for cells in sections:
        seen = set()
        for y, z, index in cells:
            if y >= height or z >= depth or index >= len(palette) or (y, z) in seen:
                raise ValueError('频谱截面含越界坐标、无效材质或重复位置')
            seen.add((y, z))
    native = _native_classes(spectrum)
    period, phase = arguments['period'], arguments['phase']
    columns = [sections[native[((x - phase) % period) * len(native) // period]]
               for x in range(width)]
    block_count = sum(map(len, columns))
    limit = arguments.get('max_changed_blocks', 65536)
    if not 1 <= block_count <= limit:
        raise ValueError('频谱生成结果为空或超过方块预算')
    voxels = [[x, y, z, index] for x, cells in enumerate(columns) for y, z, index in cells]
    operation = dict(kind='paste_component', label='沿 X 重建建筑频谱', classification='body',
                     lo=[0, 0, 0], hi=[width - 1, height - 1, depth - 1],
                     palette=palette, voxels=voxels)
    spec = dict(name=arguments.get('name', '建筑重复频谱'), size=list(arguments['size']),
                anchor=[0, 0, 0], tags=['parametric', 'spectral_repeat'],
                operations=[operation], max_changed_blocks=limit)
    component = build(workspace, spec)
    identity = dict(generator='nbt_spectral_repeat', revision=1, parameters=arguments, spec=spec)
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True,
                                       separators=(',', ':')).encode()).hexdigest()
    return dict(spec=spec, revision=1, recipe_sha256=digest, content_sha256=component['content_sha256'],
                block_count=block_count, construction=dict(axis='x', samples=len(native), period=period, phase=phase),
                mount='沿局部 +X 展开，锚点位于截面起点', ornament=dict(profile='none', added_or_recolored_blocks=0),
                parts={}, end_decorations={}, resolved_form={}, interfaces=[], interface_scope='not_applicable',
                verification=dict(block_states=True, bounds=True, design='pending_visual_review', routes='not_checked',
                                  support='not_checked', game='not_checked'), model_modified=False, approval_created=False)
