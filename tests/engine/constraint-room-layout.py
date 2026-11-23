from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_project.constraints import dispatch
from nbt_project.constraint_registry import builtin_constraints
from nbt_project.room_links import add_room_links, read_links
from nbt_project.rooms import init_layout, register_room, room_dirs, room_info, update_room
from nbt_detail_control import catalog
from nbt_assembly import Volume
from nbt_prompts import publish, read_task, save, scan
from nbt_refine import save_master, digest
from nbt_history import History

spec=importlib.util.spec_from_file_location('room_migration',ROOT/'tools/constraint-room-migration/migrate.py')
migration=importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def rule(workspace,name,folder='nbt_models'):
    revision=dispatch(workspace,'constraints-list',{'folder':folder})['revision']
    return dispatch(workspace,'constraints-save',{'folder':folder,'revision':revision,'name':name,'rules':{'requirements':'保留入口'}})['saved']


def document(name,constraints,**project):
    return {'project':dict(name=name,stage='draft',buildingShape='standalone',size=[4,4,4],**project),'constraints':constraints}


class ConstraintRoomLayout(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name).resolve()
        self.workspace=self.base/'workspace'
        (self.workspace/'nbt_models').mkdir(parents=True)

    def test_catalog_lists_legacy_and_directory_constraints_together(self):
        project=self.workspace/'nbt_models'
        (project/'single').mkdir()
        legacy=rule(self.workspace,'单格通行','nbt_models/single')
        root_rule=rule(self.workspace,'Kuuu')
        shared=rule(self.workspace,'Apoc','')
        init_layout(project)
        newest=rule(self.workspace,'独立目录约束')
        data=catalog(self.workspace,include_bugged=True,index_only=True)
        self.assertEqual({item['id'] for item in data['constraint_groups']},{legacy['id'],root_rule['id'],shared['id'],newest['id']}|set(builtin_constraints()))
        self.assertEqual({item['id'] for item in dispatch(self.workspace,'constraints-list',{'folder':'nbt_models'})['items']},{root_rule['id'],newest['id']})
        self.assertEqual(dispatch(self.workspace,'constraints-list',{'folder':'nbt_models/single'})['items'],[legacy])
        revision=dispatch(self.workspace,'constraints-list',{'folder':'nbt_models'})['revision']
        dispatch(self.workspace,'constraints-delete',{'folder':'nbt_models','id':root_rule['id'],'revision':revision})
        self.assertEqual(dispatch(self.workspace,'constraints-list',{'folder':'nbt_models'})['items'],[newest])

    def test_legacy_grouping_follows_published_rule_ids_and_renamed_room_receipt(self):
        def model(name):
            file=self.workspace/'nbt_models/standalone'/name/'v01/master.json.gz'
            file.parent.mkdir(parents=True)
            volume=Volume((4,4,4));volume.put((0,0,0),'stone_bricks')
            save_master(file,volume,set())
            return file

        apoc_model=model('Apoc大厅')
        kuuu_model=model('已更名房间')
        unmatched=model('同形状旧房间')
        rules=[rule(self.workspace,name) for name in ('Apoc','Kuuu')]
        tasks=[]
        for name, snapshot, session in zip(('Apoc大厅','原名称'),rules,('a'*32,'b'*32)):
            output='nbt_models/standalone/'+name
            saved=save(self.workspace,dict(session_id=session,text='构建要求',document=document(name,[snapshot],output=output),plan={},context={}))
            tasks.append(publish(self.workspace,saved['index'],saved['id'],saved['revision']))
        (self.workspace/tasks[1]['directory']/'初稿回传.json').write_text(json.dumps({'source':str(kuuu_model),'source_sha256':digest(kuuu_model)}),encoding='utf-8')
        listed=catalog(self.workspace,include_bugged=True,index_only=True)
        linked={item['source']:item.get('constraint_ids',[]) for item in listed['models']}
        self.assertEqual(linked,{str(apoc_model):[rules[0]['id']],str(kuuu_model):[rules[1]['id']],str(unmatched):[]})
        returned=next(item for item in listed['models'] if item['source']==str(kuuu_model))
        self.assertEqual({entry['kind'] for entry in returned['constraint_evidence'][rules[1]['id']]},{'handoff','receipt'})
        proposal=migration.preview(self.workspace,self.base/'target')
        by_name={item['name']:item['suggestions'] for item in proposal['rooms']}
        self.assertEqual(by_name['已更名房间'],[rules[1]['id']])
        unlinked=next(item for item in listed['models'] if item['source']==str(unmatched))
        binding={key:unlinked[key] for key in ('source','file_size','modified_ns')}
        request=dict(action='add-room-links',constraint_id=rules[0]['id'],items=[binding])
        with self.assertRaisesRegex(ValueError,'已有变化'):
            add_room_links(self.workspace,dict(request,items=[binding,dict(binding,modified_ns='0')]))
        self.assertEqual(read_links(self.workspace),{})
        self.assertEqual(add_room_links(self.workspace,request),dict(rooms=1,changed=1))
        self.assertEqual(add_room_links(self.workspace,request),dict(rooms=1,changed=0))
        refreshed=catalog(self.workspace,include_bugged=True,index_only=True)
        changed=next(item for item in refreshed['models'] if item['source']==str(unmatched))
        self.assertEqual(changed['constraint_evidence'][rules[0]['id']][0]['kind'],'manual')

    def test_independent_rules_room_identity_and_draft_registration(self):
        owner=rule(self.workspace,'Kuuu')
        other=rule(self.workspace,'门洞')
        groups=self.workspace/'nbt_models/约束'
        files=list(groups.glob('*/约束.json'))
        self.assertEqual(len(files),2)
        labels=dispatch(self.workspace,'constraints-list',{'folder':'nbt_models','summary':True})['items']
        self.assertNotIn('rules',labels[0])
        self.assertEqual(dispatch(self.workspace,'constraints-list',{'folder':'nbt_models','id':owner['id']})['items'],[owner])
        first=save(self.workspace,dict(session_id='a'*32,text='新方案',document=document('大厅',[owner]),
                   plan={},context={}))
        self.assertIn('方案草稿',first['index'])
        self.assertEqual(list(room_dirs(self.workspace/'nbt_models')),[])
        registered=register_room(self.workspace,dict(session_id='a'*32,name='大厅',shape='standalone',
                                  owner_constraint_id=owner['id'],constraint_ids=[owner['id'],other['id']]))
        self.assertIn('Kuuu--',registered['folder'])
        located=self.workspace/registered['folder']
        self.assertEqual(room_info(self.workspace/'nbt_models',located)['constraint_ids'],[owner['id'],other['id']])
        saved=save(self.workspace,dict(session_id='a'*32,text='房间方案',document=dict(
            document('大厅',[owner],room_folder=registered['folder']),workbench={'layout_project':'nbt_models'}),
            plan={},context={}))
        self.assertTrue(saved['index'].startswith(registered['folder']+'/'))
        self.assertEqual(len({item['id'] for item in scan(self.workspace)['items']}),1)
        revision=dispatch(self.workspace,'constraints-list',{'folder':'nbt_models'})['revision']
        edited=dispatch(self.workspace,'constraints-save',dict(folder='nbt_models',id=owner['id'],revision=revision,
                        name='新的名称',rules=owner['rules']))['saved']
        self.assertEqual(edited['revision'],2)
        self.assertEqual(set(groups.glob('*/约束.json')),set(files))
        self.assertTrue(located.is_dir())
        refreshed=update_room(self.workspace,dict(folder=registered['folder'],revision=1,
            name='新大厅',constraint_ids=[owner['id'],other['id']]))
        self.assertEqual(refreshed['folder'],registered['folder'])
        with self.assertRaisesRegex(ValueError,'刷新'):
            update_room(self.workspace,dict(folder=registered['folder'],revision=1,name='旧修订'))
        moved=update_room(self.workspace,dict(folder=refreshed['folder'],revision=2,
            owner_constraint_id=other['id']),move=True)
        self.assertIn('门洞--',moved['folder'])
        self.assertEqual([self.workspace/moved['folder']],list(room_dirs(self.workspace/'nbt_models')))
        self.assertEqual(set(moved['constraint_ids']),{owner['id'],other['id']})
        self.assertEqual(len({item['id'] for item in scan(self.workspace)['items']}),1)

    def test_legacy_copy_matches_hashes_and_keeps_published_source(self):
        room=self.workspace/'nbt_models/single/旧大厅'
        version=room/'v01'
        version.mkdir(parents=True)
        source=version/'master.json.gz'
        model=Volume((4,4,4));model.put((0,0,0),'stone_bricks')
        save_master(source,model,set())
        chosen=rule(self.workspace,'旧约束')
        current=dispatch(self.workspace,'constraints-list',{'folder':'nbt_models'})
        replacement=dispatch(self.workspace,'constraints-save',dict(folder='nbt_models',id=chosen['id'],revision=current['revision'],
                             name='旧约束',rules={'requirements':'保留楼梯'}))['saved']
        old_history=History(self.workspace).record({'source':str(source)})['version']
        revision=save(self.workspace,dict(session_id='b'*32,text='既有修改说明',document={
            'project':dict(name='旧大厅',stage='plan',buildingShape='single',size=[4,4,4],source=str(source)),
            'constraints':[chosen]},plan={},context={}))
        task=publish(self.workspace,revision['index'],revision['id'],revision['revision'])
        target=self.base/'target'
        proposal=migration.preview(self.workspace,target)
        self.assertFalse(target.exists())
        self.assertEqual(len(proposal['rooms']),1)
        room_id=proposal['rooms'][0]['id']
        self.assertEqual(proposal['rooms'][0]['suggestions'],[chosen['id']])
        result=migration.apply(proposal,{room_id:chosen['id']})
        self.assertTrue(result['passed'])
        self.assertEqual(migration.apply(proposal,{room_id:chosen['id']}),result)
        self.assertFalse((self.workspace/'nbt_models/约束').exists())
        self.assertTrue(source.is_file())
        migrated=read_task(target,task['id'])
        self.assertTrue(migrated['source_matches'])
        self.assertEqual(migrated['text'],'既有修改说明')
        found=catalog(target,include_bugged=True,index_only=True)
        self.assertEqual(len(found['models']),1)
        self.assertEqual(found['models'][0]['room_id'],room_id)
        self.assertEqual(found['rooms'][0]['owner_constraint_id'],chosen['id'])
        folder=target/found['rooms'][0]['folder']
        self.assertEqual(len(list((folder.parent.parent/'历史版本').glob('*.json'))),2)
        active=dispatch(target,'constraints-list',{'folder':found['rooms'][0]['folder'],'include_references':True})['items']
        self.assertEqual(active,[replacement])
        new_source=found['models'][0]['source']
        self.assertEqual([version['id'] for version in History(target).list(new_source)['versions']],[old_history['id']])
        self.assertEqual(History(target).record({'source':new_source})['version']['id'],old_history['id'])

    def test_preflight_rejects_nested_destination_and_detects_source_change(self):
        with self.assertRaisesRegex(ValueError,'之外'):
            migration.preview(self.workspace,self.workspace/'new')
        target=self.base/'target'
        proposal=migration.preview(self.workspace,target)
        (self.workspace/'nbt_models/记录.txt').write_text('changed',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'重新预检'):
            migration.apply(proposal,{})
        self.assertFalse(target.exists())


if __name__=='__main__':unittest.main(verbosity=2)
