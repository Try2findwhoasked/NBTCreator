"""Exact bitmap acceleration must preserve connectivity and fitted output."""
from collections import deque
from hashlib import sha256
from pathlib import Path
import json,sys,tempfile,unittest

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_pattern.bitmap_topology import component_sizes,component_masks,topology
from nbt_structure_agent import dispatch


def reference(mask,diagonal,interior):
    height,width=mask.shape;remaining={tuple(map(int,p)) for p in np.argwhere(mask)};sizes=[]
    steps=[(-1,0),(1,0),(0,-1),(0,1)]
    if diagonal:steps+=[(-1,-1),(-1,1),(1,-1),(1,1)]
    while remaining:
        first=remaining.pop();pending=deque([first]);count=0;border=False
        while pending:
            y,x=pending.popleft();count+=1;border|=y in (0,height-1) or x in (0,width-1)
            for dy,dx in steps:
                point=y+dy,x+dx
                if point in remaining:remaining.remove(point);pending.append(point)
        if not interior or not border:sizes.append(count)
    return sorted(sizes)


class BitmapTopology(unittest.TestCase):
    def assertEquivalent(self,mask):
        for diagonal in (False,True):
            for interior in (False,True):
                self.assertEqual(sorted(component_sizes(mask,diagonal,interior)),reference(mask,diagonal,interior))

    def test_exhaustive_small_masks_match_independent_coordinate_flood(self):
        for height,width in ((1,5),(5,1),(2,3),(3,4)):
            for bits in range(1<<(height*width)):
                mask=np.array([bool(bits&(1<<i)) for i in range(height*width)]).reshape(height,width)
                self.assertEquivalent(mask)

    def test_odd_rectangles_strides_and_input_bytes_are_preserved(self):
        random=np.random.default_rng(20261115)
        for height,width in ((3,17),(17,3),(11,13),(24,24),(1,1)):
            for density in (.05,.4,.9):
                original=random.random((height,width))<density
                for mask in (original,original[::-1,::2],np.asfortranarray(original)):
                    before=mask.tobytes();self.assertEquivalent(mask);self.assertEqual(before,mask.tobytes())

    def test_row_edges_never_wrap_and_voids_use_complementary_connectivity(self):
        # These cells touch only if row packing accidentally wraps horizontally.
        mask=np.array([[0,0,1],[1,0,0]],dtype=bool)
        self.assertEqual(component_sizes(mask),[1,1])
        diagonal=np.eye(3,dtype=bool)
        self.assertEqual(component_sizes(diagonal),[3]);self.assertEqual(component_sizes(diagonal,False),[1,1,1])
        mask=np.ones((5,5),dtype=bool);mask[0,0]=mask[1,1]=mask[2,2]=False
        self.assertEqual(topology(mask),dict(components=1,holes=2))
        self.assertEqual(component_sizes(~mask,True,True),[])

    def test_large_regions_and_empty_dimensions(self):
        mask=np.zeros((384,512),dtype=bool)
        mask[[0,-1],:]=True;mask[:,[0,-1]]=True;mask[192,:]=True;mask[:,256]=True
        self.assertEqual(topology(mask),dict(components=1,holes=4))
        for shape in ((0,0),(0,3),(3,0)):
            self.assertEqual(topology(np.zeros(shape,dtype=bool)),dict(components=0,holes=0))
        for value in (False,True):
            self.assertEquivalent(np.full((13,9),value,dtype=bool))
        with self.assertRaises(ValueError):component_sizes(np.zeros(3))

    def test_discrete_presets_preserve_geometry_and_use_versioned_physical_quality(self):
        cases=[('micro-fleur-de-lis','wall',[8,8],'82e98d61339a08bb59394c5852e576f99284cc445a623e74915ed43ea9aa3fa1'),
            ('micro-palmette','ceiling',[4,4],'4c52a68537b6feac4fe90083f7673bf86304293f77ea00ac9b3c2065e6cb2ef9'),
            ('micro-rose-window','wall',[12,12],'455d71645fc10a74959a144bc22820702374f89b369a6d461424aca85f955f20')]
        with tempfile.TemporaryDirectory() as directory:
            for preset,surface,size,content in cases:
                with self.subTest(preset=preset):
                    result=dispatch(Path(directory),'pattern_microfit',dict(preset=preset,surface=surface,size_uv=size))
                    self.assertEqual(result['content_sha256'],content)
                    quality=result['microfit']['visual_quality']
                    self.assertEqual(quality['evaluation_grid']['pixels_per_block'],32)
                    self.assertEqual(quality['evaluation_grid']['edge_tolerance_blocks'],1/32)
                    self.assertTrue(quality['method'].startswith('physical_32px_'))
                    self.assertTrue(result['microfit']['topology_preserved'])

    def test_component_masks_partition_real_pixels_without_row_wrap(self):
        for shape in ((3,7),(8,5),(1,9)):
            mask=np.indices(shape).sum(axis=0)%3==0
            expected=int.from_bytes(np.packbits(mask.ravel(),bitorder='little').tobytes(),'little')
            for diagonal in (False,True):
                groups=list(component_masks(mask,diagonal))
                combined=0
                for group in groups:
                    self.assertEqual(combined&group,0);combined|=group
                self.assertEqual(combined,expected)
                self.assertEqual(sorted(group.bit_count() for group in groups),reference(mask,diagonal,False))


if __name__=='__main__':unittest.main(verbosity=2)
