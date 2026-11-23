"""An expanded block palette must solve the same physical source features."""
from hashlib import sha256
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_pattern.microfit import reference
from nbt_pattern.panel import sample_input


class PhysicalReference(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)

    def test_real_ornaments_have_one_source_topology_at_every_candidate_resolution(self):
        for preset,size in (('gothic-rose',[12,12]),('acanthus-frieze',[12,6]),
                            ('baroque-pilaster',[8,12]),('chinese-window-lattice',[12,12])):
            root,sample=sample_input(self.root,dict(surface='wall',preset=preset))
            rows=[reference(root,sample,*size,factor) for factor in (2,16,32)]
            with self.subTest(preset=preset):
                self.assertEqual(rows[0][3],rows[1][3])
                self.assertEqual(rows[0][3],rows[2][3])
                for factor,row in zip((16,32),rows[1:]):
                    self.assertTrue(np.array_equal(rows[0][0],row[0].reshape(size[1]*2,factor//2,size[0]*2,factor//2).mean(axis=(1,3))))

    def test_source_feature_anchors_map_to_the_same_physical_location(self):
        for preset,size in (('gothic-rose',[12,12]),('chinese-window-lattice',[12,12])):
            root,sample=sample_input(self.root,dict(surface='wall',preset=preset))
            low=reference(root,sample,*size,2)
            high=reference(root,sample,*size,16)
            with self.subTest(preset=preset):
                for index in (1,2):
                    self.assertEqual(low[index],{(y//8,x//8) for y,x in high[index]})

    def test_feature_area_cutoff_is_in_blocks_and_does_not_hide_extra_detail(self):
        image=Image.new('L',(128,128));draw=ImageDraw.Draw(image)
        draw.rectangle([0,0,31,31],fill=255)
        draw.rectangle([90,90,93,93],fill=255)
        source=self.root/'features.png';image.save(source)
        sample=dict(path=source.name,sha256=sha256(source.read_bytes()).hexdigest(),noise_strength=0)
        rows=[reference(self.root,sample,2,2,factor) for factor in (1,2,16,32)]
        self.assertTrue(all(row[3]==rows[0][3] for row in rows))
        self.assertEqual(rows[0][3]['components'],1)
        self.assertEqual(rows[0][3]['discarded_ink_components'],1)


    def test_identical_models_receive_identical_quality_scores_across_palettes(self):
        from nbt_agent.structure import dispatch
        from nbt_runtime.modeling_session import current
        base=dict(slab='stone_brick_slab',stairs='stone_brick_stairs')
        args=dict(surface='wall',preset='micro-diamond',size_uv=[4,4],micro_alignment='fixed',material='stone_bricks',quality_profile='ornate')
        coarse=dispatch(self.root,'pattern_microfit',dict(args,shapes=base))
        current().clear()
        fine=dispatch(self.root,'pattern_microfit',dict(args,shapes=dict(base,wall='stone_brick_wall')))
        self.assertEqual(coarse['content_sha256'],fine['content_sha256'])
        self.assertEqual(coarse['microfit']['visual_quality'],fine['microfit']['visual_quality'])
        self.assertEqual(fine['microfit']['quality_sampling_resolution'],32)

    def test_cached_source_analysis_does_not_hide_changed_bytes_or_share_mutations(self):
        image=Image.new('L',(64,64),255);source=self.root/'cached.png';image.save(source)
        sample=dict(path=source.name,sha256=sha256(source.read_bytes()).hexdigest(),noise_strength=0)
        first=reference(self.root,sample,1,1,2);first[3]['holes']=999
        second=reference(self.root,sample,1,1,16)
        self.assertEqual(second[3]['holes'],0)
        Image.new('L',(64,64),0).save(source)
        with self.assertRaisesRegex(ValueError,'SHA256'):reference(self.root,sample,1,1,32)

if __name__=='__main__':unittest.main(verbosity=2)
