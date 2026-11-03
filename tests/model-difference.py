import sys, tempfile, hashlib, json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_refine import save_master
from nbt_compare import describe, compare_sources

class Differences(unittest.TestCase):
    def test_states_layers_dimensions_and_lossless_runs(self):
        a,b=Volume((64,8,8)),Volume((80,8,8))
        for m in (a,b):
            m.box((1,1,1),(4,1,1),'stone')
            m.put((2,2,2),'oak_stairs[facing=north]')
        a.put((7,1,1),'stone');b.put((2,2,2),'oak_stairs[facing=south]')
        b.box((65,1,1),(68,1,1),'stone')
        d=describe(a,b,{(1,1,1),(2,2,2)},{(2,2,2)})
        self.assertEqual(d['counts'],dict(added=4,removed=1,replaced=1,wall=1))
        self.assertEqual(d['changed_positions'],7);self.assertEqual(d['wall_membership_changes'],1)
        positions={ (x,y,z) for _,start,y,z,n,_,_ in d['runs'] for x in range(start,start+n)}
        self.assertEqual(len(positions),7);self.assertIn((68,1,1),positions)
        self.assertEqual(d['bounds'],dict(lo=[1,1,1],hi=[68,2,2]))
        self.assertEqual(len(d['regions']),2);self.assertEqual(sum(r['count'] for r in d['regions']),7)
        self.assertTrue(any(r[0]=='wall' and r[-2:]==[True,False] for r in d['runs']))

    def test_identical_and_empty_models(self):
        a=Volume((4,4,4));self.assertIsNone(describe(a,a,set(),set())['bounds'])
        a.put((1,1,1),'stone');self.assertEqual(describe(a,a,set(),set())['runs'],[])
        self.assertEqual(describe(a,a,set(),{(1,1,1)})['counts']['wall'],1)

    def test_read_only_sources_bound_to_hashes_and_new_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);a,b=Volume((8,8,8)),Volume((10,8,8));a.put((1,1,1),'stone');b.put((2,1,1),'stone')
            save_master(p/'before.json.gz',a,set());save_master(p/'after.json.gz',b,set())
            digest=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
            old=[digest(p/'before.json.gz'),digest(p/'after.json.gz')]
            request=dict(source=str(p/'after.json.gz'),reference_source=str(p/'before.json.gz'),source_sha256=old[1],reference_sha256=old[0])
            result=compare_sources(request,p/'comparison');self.assertEqual(result['changed_blocks'],2)
            self.assertEqual(old,[digest(p/'before.json.gz'),digest(p/'after.json.gz')])
            self.assertFalse(result['model_modified']);self.assertFalse(result['validation_performed'])
            d=json.loads(Path(result['difference']).read_text());self.assertEqual(d['before_source_sha256'],old[0])
            self.assertTrue(json.loads(Path(result['snapshot']).read_text())['cameras'])
            with self.assertRaises(FileExistsError):compare_sources(request,p/'comparison')
            with self.assertRaisesRegex(ValueError,'已变化'):compare_sources(dict(request,reference_sha256='0'*64),p/'bad')

if __name__=='__main__':unittest.main()
