import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_change_policy import enforce_overwrite, enforce_changes

GROUP='12345678-1234-1234-1234-123456789abc'
class Overwrite(unittest.TestCase):
    def test_a_component_can_layer_its_own_new_blocks(self):
        model=Volume((8,8,8));owners={};walls=set();p=(3,3,3)
        for value in ('minecraft:gold_block','minecraft:stone_bricks'):
            enforce_overwrite(model,walls,dict(kind='box',classification='body',overwrite=False,write_group=GROUP),[(p,value)],owners);model.put(p,value)
        self.assertEqual(model.get(p),'minecraft:stone_bricks')
        with self.assertRaisesRegex(ValueError,'已有方块'):
            enforce_overwrite(model,walls,dict(kind='box',classification='body',overwrite=False,write_group='87654321-4321-4321-4321-cba987654321'),[(p,'minecraft:air')],owners)

    def test_unchanged_writes_cannot_claim_preexisting_blocks(self):
        model=Volume((8,8,8));p=(3,3,3);model.put(p,'stone');walls={p};owners={};operation=dict(kind='box',classification='wall',overwrite=False,write_group=GROUP)
        enforce_overwrite(model,walls,operation,[(p,model.get(p))],owners);self.assertNotIn(p,owners)
        with self.assertRaisesRegex(ValueError,'已有方块'):enforce_overwrite(model,walls,operation,[(p,'minecraft:gold_block')],owners)
        with self.assertRaisesRegex(ValueError,'墙层'):enforce_overwrite(model,walls,dict(operation,classification='body'),[(p,model.get(p))],owners)

    def test_explicit_overwrite_still_cannot_pass_protection(self):
        model=Volume((8,8,8));p=(3,3,3);model.put(p,'stone');old=dict(model.blocks)
        enforce_overwrite(model,set(),dict(kind='box',classification='body',overwrite=True,write_group=GROUP),[(p,'minecraft:gold_block')],{});model.put(p,'gold_block')
        with self.assertRaisesRegex(ValueError,'保护区'):enforce_changes(old,model.blocks,set(),set(),protected={p})
        with self.assertRaisesRegex(ValueError,'超过上限'):enforce_changes(old,model.blocks,set(),set(),maximum=0)

if __name__=='__main__':unittest.main()
