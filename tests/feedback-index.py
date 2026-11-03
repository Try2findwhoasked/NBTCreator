"""Version comment discovery, archival relocation and stale-evidence refusal."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_refine import save_master
from nbt_feedback import collect, scan, version_source, sha


class Feedback(unittest.TestCase):
    def fixture(self, workspace):
        version=workspace/'nbt_models/single/评论测试/v01'
        source=version/'master/master_geometry.json.gz'
        source.parent.mkdir(parents=True)
        model=Volume((48,12,48));model.put((3,2,4),'minecraft:stone')
        save_master(source,model,{(3,2,4)})
        snapshot=workspace/'nbt_models/_workspaces/jobs/snapshot.json';snapshot.parent.mkdir(parents=True)
        snapshot.write_text(json.dumps(dict(source_sha256=sha(source),geometry_sha256=model.fingerprint(),blocks=[[[3,2,4],'minecraft:stone']])),encoding='utf8')
        binding=dict(kind='3d',source=str(source),workdir=str(version.parent),source_sha256=sha(source),geometry_sha256=model.fingerprint(),snapshot=str(snapshot),snapshot_sha256=sha(snapshot))
        file=version.parent/'修改意见'/sha(source)/('3d_'+model.fingerprint()+'.json');file.parent.mkdir(parents=True)
        file.write_text(json.dumps(dict(binding=binding,notes=[dict(id='real-note-id',text='扶手要连续',status='open',anchors=[dict(kind='voxel',number=1,position=[3,2,4],state='minecraft:stone',geometry_sha256=model.fingerprint())])])),encoding='utf8')
        return version,source,snapshot,file

    def test_archive_scan_and_collect_survive_old_workspace_and_cache_removal(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();old=root/'old';new=root/'new'
            version,source,snapshot,file=self.fixture(old);source_hash=sha(source);note_hash=sha(file)
            result=collect(source,old,archive=True)
            self.assertTrue(result['verified']);self.assertEqual(sha(file),note_hash)
            self.assertEqual(scan(old)['notes'],1)
            shutil.copytree(old,new)
            # Delete only this verified, isolated temporary fixture.
            shutil.rmtree(old)
            shutil.rmtree(new/'nbt_models/_workspaces')
            new_version=new/version.relative_to(old)
            self.assertEqual(version_source(new_version),new/source.relative_to(old))
            self.assertTrue(scan(new)['verified'])
            moved=collect(version_source(new_version),new)
            self.assertTrue(moved['verified']);self.assertEqual(moved['notes'],1)
            self.assertEqual(sha(new/source.relative_to(old)),source_hash)
            self.assertEqual(sha(new/file.relative_to(old)),note_hash)
            evidence=Path(moved['records'][0]['assets'][1]['path'])
            evidence.write_text('changed',encoding='utf8')
            self.assertFalse(collect(version_source(new_version),new)['verified'])
            with self.assertRaises(ValueError):collect(version_source(new_version),new,archive=True)

    def test_comment_changed_after_index_is_detected_and_wrong_voxel_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);version,source,_,file=self.fixture(root)
            collect(source,root,archive=True)
            record=json.loads(file.read_text());record['notes'][0]['anchors'][0]['state']='minecraft:air'
            file.write_text(json.dumps(record))
            self.assertFalse(scan(root)['verified'])
            with self.assertRaises(ValueError):collect(source,root)
            (version/'修改意见/评论索引.json').unlink()
            result=collect(source,root);self.assertFalse(result['verified'])
            self.assertTrue(result['records'][0]['errors'])


if __name__=='__main__':unittest.main(verbosity=2)
