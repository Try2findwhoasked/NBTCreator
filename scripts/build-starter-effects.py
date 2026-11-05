"""Build/check release starter effects using the real shared simulation engine."""
import argparse,hashlib,json,sys,tempfile,uuid
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'.agents/skills/minecraft-nbt-modeler'
sys.path.insert(0,str(SKILL/'scripts'))
import nbt_effect_assets as effects
from nbt_starter_effects import BUNDLE,catalog,checked_files,engine_sha,sha


def definitions():
    tools=json.loads((SKILL/'tool-catalog.json').read_text(encoding='utf8'))['tools']
    items=[]
    def panel(key,name,note,**settings):
        settings['style_note']=note;settings['seed']=2718
        items.append((key,dict(name=name,tags=[],settings=settings)))
    def tool(key,name,note,kind,lo,hi,**params):
        op=deepcopy(tools[kind][1])
        for field in ['max_writes','overwrite','write_group','write_bounds']:op.pop(field,None)
        op.update(kind=kind,label=name,lo=lo,hi=hi,**params)
        panel(key,name,note,operations=[op])
    panel('stone-mix','石砖轻度混材','在原石砖表面加入少量安山岩和裂纹石砖，保留大面积整洁底色。',pattern=dict(enabled=True,fraction=.3,mode='clustered',scale=5,palette=[dict(state='andesite',weight=2),dict(state='cracked_stone_bricks',weight=1)]))
    panel('moss-mix','石砖苔斑混材','连片混入苔石砖，不改变实体轮廓。',pattern=dict(enabled=True,fraction=.45,mode='clustered',scale=7,palette=[dict(state='mossy_stone_bricks',weight=1)]))
    panel('dark-stone','石砖换为深板岩','将选中范围的石砖表面换为深板岩砖。',replace=dict(enabled=True,from_states=['stone_bricks'],state='deepslate_bricks',scope='surface'))
    panel('moss-weather','连续渗水苔痕','以连片苔痕表现潮湿墙面，裂纹比例较低。',weathering=dict(enabled=True,moss_fraction=.3,cracks_fraction=.03))
    panel('cracked-weather','旧石墙连续裂纹','以连续裂纹表现老化，保留墙体体积。',weathering=dict(enabled=True,moss_fraction=0,cracks_fraction=.25))
    panel('worn-floor','地面轻度磨损','可达地面形成少量半砖凹陷，保留必要通行路线。',floor=dict(enabled=True,profile='worn',fraction=.04,slab_share=1))
    panel('ruined-floor','遗迹地面小片破损','可达地面形成小片凹陷及有底坑洞，保留必要通路。',floor=dict(enabled=True,profile='ruined',fraction=.08,slab_share=.75,patch_size=[2,5]))
    tool('diagonal-road','三格宽石砖步道','在同一高度铺设连续斜向步道；不会自动清空头顶。','auto_road',[4,3,4],[28,3,28],start=[6,3,6],end=[26,3,26],state='stone_bricks')
    tool('corner-road','直角安山岩步道','先沿X轴、再沿Z轴铺设三格宽折线路面。','auto_road',[4,3,4],[28,3,28],start=[6,3,6],end=[26,3,26],route='x_first',state='andesite')
    tool('terrain-road','地表寻路安山岩路','在允许的地形材质上寻找有净空的路线，样例使用平坦地表。','terrain_road',[3,0,3],[28,12,28],start=[6,2,6],end=[26,2,26],terrain_states=['stone_bricks','stone','oak_planks','deepslate_tiles'],width=1,state='andesite')
    tool('stairs','半格上升石砖坡道','以完整块和底半砖组合上升四格；栏杆和支撑需另行设计。','auto_stairs',[4,0,4],[30,12,14],start=[6,3,8],end=[28,7,8],width=3)
    tool('gable-roof','石砖人字顶皮','生成沿Z轴的人字屋顶皮；不自动补山墙或梁柱。','auto_roof',[8,5,8],[28,12,24],rise=5,finish='slabs')
    tool('cylinder','圆柱体取样','在局部范围生成竖直圆柱，用于查看体素曲面效果。','geometry',[8,3,8],[24,12,24],geometry=dict(shape='cylinder',centre=[16,7,16],radius=4,height=8,axis='y'))
    tool('torus','水平圆环取样','生成水平圆环，展示环面体素化。','geometry',[6,3,6],[26,12,26],geometry=dict(shape='torus',centre=[16,7,16],major_radius=6,minor_radius=2))
    tool('arch','布尔挖空石拱','通过两个几何体的差集生成石拱轮廓。','geometry',[8,3,12],[24,12,15],geometry=dict(shape='difference',children=[dict(shape='box',min=[8,3,12],max=[25,12,16]),dict(shape='cylinder',centre=[16.5,3,14],radius=6,height=6,axis='z')]))
    tool('platform','两层石砖铺台','生成局部两层铺台，使用前按当前建筑调整坐标。','box',[8,3,8],[20,4,20],state='stone_bricks')
    tool('hollow','一格厚空心壳','生成一格厚空心壳；内部会挖空，请先检查目标范围。','hollow_box',[8,3,8],[22,11,22],thickness=1)
    tool('frame','单层石砖边框','在竖直平面生成一格宽边框。','frame',[8,3,12],[24,11,12])
    tool('beam','斜向原木梁','以一格宽原木生成斜梁；连接和承托仍须检查。','beam',[8,3,8],[24,11,24],start=[8,3,8],end=[24,11,24],width=1,state='oak_log[axis=y]')
    tool('replace','石柱精确换材','只将指定局部石砖换为安山岩，其他状态不变。','replace',[30,3,30],[32,8,32],from_states=['stone_bricks'],state='andesite')
    tool('move','石柱平移','把样例石柱移至左侧空地；源区域会清空。','move_region',[30,3,30],[32,8,32],offset=[-22,0,-22])
    tool('copy','石柱快照复制','从源选区复制到偏移位置，不修改原柱。','copy_region',[30,3,30],[32,8,32],offset=[-22,0,-22])
    tool('repeat','石柱等距阵列','从同一源快照复制三次，不递归复制刚生成的副本。','repeat_region',[30,3,30],[32,8,32],offset=[-8,0,0],count=3)
    tool('transform','石柱镜像旋转复制','镜像后绕Y轴转90度，复制到空地。','transform_region',[30,3,30],[32,8,32],destination=[8,3,28],mirror='x')
    tool('align','石柱按边界对齐','将源选区副本按目标最小边界对齐。','align_region',[30,3,30],[32,8,32],target_lo=[8,3,28],target_hi=[18,11,38],axes=['min','min','min'])
    tool('path-array','石柱沿路径阵列','按八格间距沿直线路径放置源选区副本。','array_region',[30,3,30],[32,8,32],points=[[8,3,28],[24,3,28]],spacing=8,source_anchor=[30,3,30])
    tool('dilate','石柱六邻接膨胀','将局部石柱向六邻接方向膨胀一层。','morphology',[28,3,28],[33,10,33],mode='dilate',iterations=1)
    tool('diffusion','石柱表面苔色扩散','从指定石柱表面种子扩散苔色，不跨越断开的表面。','diffusion',[30,3,30],[32,8,32],seeds=[[31,7,30]],steps=8,decay=.08,surface_only=True)
    tool('explosion','墙面放射缺口','在样例隔墙形成静态缺口和放射裂纹，不模拟TNT物理。','explosion',[8,3,32],[39,12,41],centre=[22,7,36],radius=3,rays=6,ray_length=5)
    tool('scatter','地面间距碎石','在有下方支承的空位散落少量碎石，保留间距。','scatter',[10,3,8],[38,3,26],fraction=.12,spacing=3)
    tool('surface','旧石墙表面斑驳','在隔墙表面少量换成裂纹和苔石砖，不挖空。','surface_palette',[8,3,36],[39,10,37],fraction=.4)
    tool('connected','连通石柱换材','从种子出发选择连通同状态方块，在限定柱体内换材。','selection_replace',[30,3,30],[32,8,32],seed_position=[31,5,31],state='andesite',selection='connected',match='state')
    return items


def check():
    bundle=catalog()
    if bundle is None or bundle.get('engine_sha256')!=engine_sha():raise ValueError('初始效果需重新生成：python scripts/build-starter-effects.py')
    expected={uuid.uuid5(uuid.NAMESPACE_URL,'nbtcreator:starter-effect:'+key+':1').hex:effects.validate(asset) for key,asset in definitions()}
    if set(expected)!={item['id'] for item in bundle['items']}:raise ValueError('初始效果清单与生成定义不同步')
    for item in bundle['items']:
        files=checked_files(item);asset=effects.validate(json.loads(files['effect.json'].read_text(encoding='utf8')))
        if asset!=expected[item['id']]:raise ValueError('初始效果配置与生成定义不同步')
        report=json.loads(files['preview/report.json'].read_text(encoding='utf8'))
        if report['content_sha256']!=asset['content_sha256'] or report['engine_sha256']!=engine_sha() or report['changed_blocks']<=0:raise ValueError('初始效果缺少实际变化预览')
        for side in ['before','after']:
            snapshot=json.loads(files['preview/'+side+'.json'].read_text(encoding='utf8'))
            if not snapshot.get('sample_only') or snapshot['source']!='tool-effect-sample':raise ValueError('初始资料不能包含用户模型路径')
    return bundle


def build():
    validated=[(key,effects.validate(asset)) for key,asset in definitions()]
    BUNDLE.mkdir(parents=True,exist_ok=True);items=[]
    # Simulation outputs remain outside installation resources; only reviewed
    # data files are copied into the explicitly authored release asset bundle.
    with tempfile.TemporaryDirectory(prefix='nbt-starter-effects-') as temporary:
        for key,value in validated:
            identifier=uuid.uuid5(uuid.NAMESPACE_URL,'nbtcreator:starter-effect:'+key+':1').hex
            result=effects.preview(temporary,dict(value,id=identifier))
            if result['changed_blocks']<=0:raise ValueError('样例没有实际变化：'+value['name'])
            folder=BUNDLE/identifier;preview=folder/'preview';preview.mkdir(parents=True,exist_ok=True)
            (folder/'effect.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
            for side in ['before','after']:
                snapshot=json.loads(Path(result[side+'_snapshot']).read_text(encoding='utf8'));snapshot.update(source='tool-effect-sample',sample_only=True);snapshot.pop('source_sha256',None)
                (preview/(side+'.json')).write_text(json.dumps(snapshot,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf8',newline='\n')
            (preview/'thumbnail.jpg').write_bytes(Path(result['thumbnail']).read_bytes())
            report=dict(schema_version=1,content_sha256=value['content_sha256'],engine_sha256=engine_sha(),cameras=result['cameras'],changed_blocks=result['changed_blocks'],files={name:sha(preview/name) for name in ['before.json','after.json','thumbnail.jpg']})
            (preview/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
            items.append(dict(id=identifier,key=key,name=value['name'],content_sha256=value['content_sha256'],files={name:sha(folder/name) for name in sorted(['effect.json','preview/before.json','preview/after.json','preview/thumbnail.jpg','preview/report.json'])}))
            print(json.dumps(dict(name=value['name'],changed_blocks=result['changed_blocks']),ensure_ascii=False),flush=True)
    manifest=dict(schema_version=1,asset_type='tool_effect_starter_pack',version='2026-11-05.1',engine_sha256=engine_sha(),items=items)
    (BUNDLE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');check()
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args();bundle=check() if args.check else build()
    print(json.dumps(dict(passed=True,effects=len(bundle['items']),bytes=sum(p.stat().st_size for p in BUNDLE.rglob('*') if p.is_file()),mode='check' if args.check else 'build'),ensure_ascii=False))
