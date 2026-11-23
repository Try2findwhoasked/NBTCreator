"""Exact connected-component sizes for bounded ornament bitmaps.

Python integer frontiers expand whole scanlines at once. Horizontal masks
prevent the last column from connecting to the next row's first column.
Detailed pixel groups remain the responsibility of the source-fit helpers.
"""
from functools import lru_cache

import numpy as np


@lru_cache(maxsize=64)
def _geometry(height,width):
    full=(1<<(height*width))-1
    left=sum(1<<(y*width) for y in range(height));right=left<<(width-1)
    row=(1<<width)-1
    return full,full^left,full^right,left|right|row|(row<<((height-1)*width))


def component_masks(mask,diagonal=True,interior=False):
    """Return exact sizes; optionally omit every border-touching component.

    Ink uses eight neighbours, voids use four. No dilation, thresholding or
    change to the requested connectivity is performed by this routine.
    """
    mask=np.asarray(mask,dtype=bool)
    if mask.ndim!=2:raise ValueError('纹样连通检查须为二维位图')
    height,width=mask.shape
    if not height or not width:return
    _,not_left,not_right,border=_geometry(height,width)
    remaining=int.from_bytes(np.packbits(mask.ravel(),bitorder='little').tobytes(),'little')

    def flood(seed):
        nonlocal remaining
        region=frontier=seed;remaining^=seed
        while frontier:
            horizontal=((frontier&not_left)>>1)|((frontier&not_right)<<1)
            neighbors=horizontal|(frontier>>width)|(frontier<<width)
            if diagonal:neighbors|=(horizontal>>width)|(horizontal<<width)
            frontier=neighbors&remaining
            remaining^=frontier;region|=frontier
        return region

    # Multiple outside components may be flooded together because all are
    # omitted, irrespective of whether the border itself connects them.
    if interior:flood(remaining&border)
    while remaining:yield flood(remaining&-remaining)


def component_sizes(mask,diagonal=True,interior=False):
    return [region.bit_count() for region in component_masks(mask,diagonal,interior)]

def topology(mask):
    mask=np.asarray(mask,dtype=bool)
    return dict(components=len(component_sizes(mask)),holes=len(component_sizes(~mask,False,True)))
