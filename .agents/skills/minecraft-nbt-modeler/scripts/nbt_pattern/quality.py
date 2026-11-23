"""Raster adapter and compatible pattern quality entry point."""
import numpy as np
from PIL import ImageOps

from nbt_pattern.metrics import assess, dilate, edge, features, groups, pruned_skeleton, skeleton_neighbours, thin


def source_bitmap(image,sample):
    gray=image.getchannel('A') if sample.get('channel')=='alpha' else image.convert('L')
    if sample.get('invert'):gray=ImageOps.invert(gray)
    result=(np.asarray(gray)>=sample.get('threshold',50)*255/100)&(np.asarray(image.getchannel('A'))>0)
    result=np.flipud(result)
    if sample.get('mirror'):
        result=result[:,np.minimum(np.arange(result.shape[1]),result.shape[1]-1-np.arange(result.shape[1]))]
    return result
