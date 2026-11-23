"""Detect and reconstruct a rectangular repeat in an already rectified raster."""
from hashlib import sha256
from itertools import product

import numpy as np
from PIL import Image, ImageOps

from nbt_pattern.ornament_sample import crop_image, sample_image


def _correlation(mask, shape):
    spectrum = np.fft.rfft2(mask, s=shape)
    return np.rint(np.fft.irfft2(abs(spectrum)**2, s=shape)).astype(np.int32)


def _raster(workspace, sample, settings, image, source_size):
    valid = np.ones((image.height, image.width), dtype=bool)
    if 'valid_mask' in settings:
        mask = sample_image(workspace, settings['valid_mask'])
        if mask.size != source_size:
            raise ValueError('有效像素掩模须与裁切前的纹样样本尺寸相同')
        mask = crop_image(mask, sample.get('crop'))
        valid = (np.asarray(mask.convert('L')) >= 128) & (np.asarray(mask.getchannel('A')) > 0)
    mask = image.getchannel('A') if sample.get('channel') == 'alpha' else image.convert('L')
    if sample.get('invert'):
        mask = ImageOps.invert(mask)
    ink = (np.asarray(mask) >= sample.get('threshold', 50)*255/100) & (np.asarray(image.getchannel('A')) > 0)
    labels = ink.astype(np.int8)
    colors = sample.get('colors', [])
    if colors:
        rgb = np.asarray(image.convert('RGB'), dtype=np.int32)
        distances = np.stack([np.sum((rgb - tuple(bytes.fromhex(entry['rgb'][1:])))**2, axis=-1)
                              for entry in colors])
        materials = list(dict.fromkeys(entry['material'] for entry in colors))
        roles = np.array([1 + materials.index(entry['material']) for entry in colors], dtype=np.int8)
        labels[ink] = roles[distances.argmin(axis=0)[ink]]
    return labels, valid


def _fold(y, x, observed, role_count, pu, pv):
    phases = (y % pv)*pu + x % pu
    return np.bincount(observed*(pu*pv) + phases, minlength=role_count*pu*pv).reshape(-1,pv,pu)


def detect(workspace, sample, settings):
    """Return an evidence receipt and a unit raster, or a reason to use a manual unit."""
    if sample.get('mirror') or sample.get('noise_strength'):
        raise ValueError('重复检测对原始拉正图运行，须关闭 mirror 和 noise_strength')
    source = sample_image(workspace, {k:v for k,v in sample.items() if k != 'crop'})
    image = crop_image(source, sample.get('crop'))
    if max(image.size) > 1024 or image.width*image.height > 262144:
        raise ValueError('重复检测最多262144像素且每轴最多1024像素，请先裁切或等比缩小')
    labels, valid = _raster(workspace, sample, settings, image, source.size)
    visible = int(valid.sum())
    roles = np.unique(labels[valid])
    report = dict(method='zero_padded_2d_fft_with_spatial_verification', detected=False,
                  source_sha256=sample['sha256'], valid_mask_sha256=settings.get('valid_mask', {}).get('sha256'),
                  crop=sample.get('crop'), size_pixels_uv=list(image.size), valid_pixels=visible,
                  agreement_min=.99, min_axis_pairs=max(8, (visible + 4)//5),
                  candidates=dict(u=[], v=[]), coordinate_origin='cropped_image_upper_left')
    if visible < 16 or len(roles) < 2:
        return dict(report, reason='insufficient_visible_pixels' if visible < 16 else 'no_visible_pattern_contrast'), None

    height, width = labels.shape
    shape = (2*height - 1, 2*width - 1)
    support = _correlation(valid, shape)
    matches = [np.zeros(n,dtype=np.int32) for n in (width,height)]
    least_role_matches = [np.full_like(axis,visible) for axis in matches]
    for role in roles:
        correlation = _correlation(valid & (labels == role), shape)
        for i, axis in enumerate((correlation[0,:width],correlation[:height,0])):
            matches[i] += axis
            np.minimum(least_role_matches[i],axis,out=least_role_matches[i])
    limits = settings.get('max_period_uv', [128, 128])
    periods = []
    for i, (axis, dimension, limit) in enumerate(zip(('u', 'v'), (width, height), limits)):
        axis_labels,axis_valid = (labels,valid) if axis == 'u' else (labels.T,valid.T)
        accepted = []
        for lag in range(1, min(dimension//2, limit) + 1):
            index = (0, lag) if axis == 'u' else (lag, 0)
            pairs = int(support[index])
            agreement = int(matches[i][lag])/pairs if pairs else 0.
            role_pairs = int(least_role_matches[i][lag])
            eligible = pairs >= report['min_axis_pairs'] and agreement >= report['agreement_min'] and role_pairs > 0
            report['candidates'][axis].append(dict(period=lag, valid_pairs=pairs,
                                                   pair_fraction=pairs/visible, agreement=agreement,
                                                   minimum_same_role_pairs=role_pairs, eligible=eligible))
            if eligible:
                paired = axis_valid[:,:-lag] & axis_valid[:,lag:]
                if np.mean(axis_labels[:,:-lag][paired] == axis_labels[:,lag:][paired]) >= report['agreement_min']:
                    accepted.append(lag)
        periods.append(accepted)
    if not all(periods):
        return dict(report, reason='no_supported_axis_periods'), None

    # Choose the smallest jointly verified rectangle. A high background match
    # alone cannot establish a period or silently discard a rare material.
    y,x = np.nonzero(valid)
    observed = labels[y,x].astype(np.int32)
    candidate_pairs = sorted(product(*periods),key=lambda p:(p[0]*p[1],sum(p),p))
    trials = []
    report['spatial_candidates'] = trials
    for pu,pv in candidate_pairs[:64]:
        counts = _fold(y,x,observed,int(roles.max())+1,pu,pv)
        unit = counts.argmax(axis=0)
        totals = counts.sum(axis=0)
        winners = counts.max(axis=0)
        phase_agreement = np.divide(winners,totals,out=np.zeros_like(totals,dtype=float),where=totals>0)
        spatial = dict(period_uv=[pu,pv],compared_pixels=visible,agreeing_pixels=int(winners.sum()),
                       minimum_phase_observations=int(totals.min()),agreement=int(winners.sum())/visible,
                       minimum_phase_agreement=float(phase_agreement.min()))
        reason = None
        if spatial['minimum_phase_observations'] < 2:
            reason = 'insufficient_phase_coverage'
        elif spatial['minimum_phase_agreement'] < .75 or spatial['agreement'] < report['agreement_min']:
            reason = 'inconsistent_rectangular_unit'
        elif len(np.unique(unit)) != len(roles):
            reason = 'unrepresented_visible_roles'
        if reason is None:
            report['spatial_verification'] = spatial
            break
        trials.append(dict(spatial,reason=reason))
    else:
        return dict(report,reason='spatial_search_limit' if len(candidate_pairs)>64 else trials[0]['reason']),None

    # Select an actual, matching RGBA pixel for each phase, ordered by
    # frequency, with a deterministic tie break. Keep material/alpha semantics.
    rgba = np.asarray(image, dtype=np.uint8)
    recovered = np.empty((pv, pu, 4), dtype=np.uint8)
    for v, u in np.ndindex(pv, pu):
        evidence = valid[v::pv, u::pu] & (labels[v::pv, u::pu] == unit[v, u])
        pixels, frequencies = np.unique(rgba[v::pv, u::pu][evidence], return_counts=True, axis=0)
        recovered[v, u] = pixels[frequencies.argmax()]
    return dict(report, detected=True, period_uv=[pu, pv], unit_source='phase_consensus_of_visible_pixels',
                unit_rgba_sha256=sha256(recovered.tobytes()).hexdigest()), Image.fromarray(recovered)


def inspect_repeat(workspace, arguments):
    report, _ = detect(workspace, arguments['sample'], arguments.get('detection', {}))
    return report
