"""View-only nonplanar roof peel from a per-column height JSON and final NBT.

Height JSON is size_x rows of size_z values, in local Y, each a multiple of 0.5.
Remove geometry at/above that height in each XZ block column. No NBT is edited.
This diagnostic field can remove upper floors; it is NOT a general visibility
solution or proof that the original roof and every layer have been inspected.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from nbt_model import load
from nbt_preview import make_grid, render, vector


def peel_grid(grid, heights):
    heights=np.asarray(heights,dtype=float)
    sx,sy,sz=(n//2 for n in grid.shape)
    if heights.shape!=(sx,sz) or not np.all(np.isfinite(heights)):
        raise ValueError('Height JSON must have finite size_x by size_z values')
    if np.any(heights<0) or np.any(heights>sy) or not np.allclose(heights*2,np.round(heights*2),atol=1e-9,rtol=0):
        raise ValueError('Heights must be half-block multiples in 0..size_y')
    limit=np.repeat(np.repeat(heights,2,axis=0),2,axis=1)
    result=grid.copy()
    result[np.arange(grid.shape[1])[None,:,None]/2>=limit[:,None,:]]=0
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nbt',required=True,type=Path)
    parser.add_argument('--heights',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--eye',required=True,type=vector)
    parser.add_argument('--target',required=True,type=vector)
    parser.add_argument('--width',type=int,default=1280)
    parser.add_argument('--height',type=int,default=800)
    parser.add_argument('--fov',type=float,default=60)
    args=parser.parse_args()
    if not 64<=args.width<=4096 or not 64<=args.height<=4096 or not 10<=args.fov<=120:
        parser.error('Image dimensions 64..4096, FOV 10..120 required')
    if np.linalg.norm(args.eye-args.target)<1e-6:parser.error('eye and target must differ')
    if args.output.suffix.lower()!='.png':parser.error('Output must be PNG')
    source=args.nbt.read_bytes();height_source=args.heights.read_bytes()
    model=load(args.nbt);grid,colors,approx=make_grid(model)
    grid=peel_grid(grid,json.loads(height_source))
    image,visible=render(grid,colors,args.eye,args.target,args.width,args.height,args.fov)
    if args.nbt.read_bytes()!=source or args.heights.read_bytes()!=height_source:
        raise RuntimeError('Source changed while rendering')
    args.output.parent.mkdir(parents=True,exist_ok=True);image.save(args.output)
    metadata=dict(source_nbt=str(args.nbt.resolve()),source_nbt_sha256=hashlib.sha256(source).hexdigest(),
                  height_field=str(args.heights.resolve()),height_field_sha256=hashlib.sha256(height_source).hexdigest(),
                  removal_rule='Remove half-voxel cells with local bottom Y >= heights[floor(X)][floor(Z)]',
                  camera=dict(eye=args.eye.tolist(),target=args.target.tolist(),fov=args.fov),
                  visible_structure_pixels=visible,approximated_states=approx,
                  limitations=['Diagnostic roof peel only; no change to NBT.',
                               'Field can remove upper layers; keep intact exterior/sections and uncut player views.',
                               'Procedural opaque geometry preview, not Minecraft textures or lighting.'])
    Path(str(args.output)+'.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(image=str(args.output.resolve()),visible_structure_pixels=visible)))


if __name__=='__main__':main()
