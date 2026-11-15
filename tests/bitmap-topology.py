"""Exact bitmap acceleration must preserve connectivity and fitted output."""
from collections import deque
from hashlib import sha256
from pathlib import Path
import json,sys,tempfile,unittest

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_bitmap_topology import component_sizes,topology
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

    def test_existing_stair_slab_geometry_and_complete_quality_receipts_are_identical(self):
        # Captured before optimization, including original candidate selection,
        # half-block orientations, topology and all fitted/visual-quality fields.
        # Search diagnostics may expand when a new bounded refinement is added.
        cases=[('micro-fleur-de-lis','wall',[8,8],
            '82e98d61339a08bb59394c5852e576f99284cc445a623e74915ed43ea9aa3fa1',
            '223f8cd724d5942ba925707afe3143b06ce5f456486a6d0f5687edd708ff359e'),
            ('micro-palmette','ceiling',[4,4],
            '4c52a68537b6feac4fe90083f7673bf86304293f77ea00ac9b3c2065e6cb2ef9',
            '67a69518f6b1f4160f9cae222a691aee44dc2d25e2c9f9d818c7f72d8defb18b'),
            ('micro-rose-window','wall',[12,12],
            '455d71645fc10a74959a144bc22820702374f89b369a6d461424aca85f955f20',
            '8602463d99315c907b1d12210429f71c20885085f6ef6934b270e5481417228b')]
        with tempfile.TemporaryDirectory() as directory:
            for preset,surface,size,content,quality in cases:
                with self.subTest(preset=preset):
                    result=dispatch(Path(directory),'pattern_microfit',dict(preset=preset,surface=surface,size_uv=size))
                    self.assertEqual(result['content_sha256'],content)
                    fitted_quality={k:v for k,v in result['microfit'].items() if k!='shape_search'}
                    actual=sha256(json.dumps(fitted_quality,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                    self.assertEqual(actual,quality)


if __name__=='__main__':unittest.main(verbosity=2)
