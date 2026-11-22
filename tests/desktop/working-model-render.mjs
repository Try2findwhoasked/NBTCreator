import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {createHash} from 'node:crypto'
import {execFileSync} from 'node:child_process'
import {root, python} from '../../scripts/paths.mjs'

const output = await fs.mkdtemp(path.join(root, 'build/model-render-'))
const workspace = path.join(output, 'workspace')
await fs.mkdir(workspace)
execFileSync(python, ['-B', path.join(root, 'tests/support/working-model-fixture.py'), workspace, output], {cwd:root, windowsHide:true, encoding:'utf8'})
const fixture = JSON.parse(await fs.readFile(path.join(output, 'fixture.json'), 'utf8'))
const images = []
for (const stage of ['before', 'after']) {
  const candidate = fixture[stage]
  const destination = path.join(output, stage+'-textures')
  execFileSync(process.execPath, [path.join(root, 'scripts/cli.mjs'), '--workspace', workspace,
    'render', '--source', candidate.source, '--cameras', candidate.cameras, '--output', destination],
    {cwd:root, windowsHide:true, encoding:'utf8', timeout:120000})
  const manifest = JSON.parse(await fs.readFile(path.join(destination, 'render_manifest.json'), 'utf8'))
  assert.equal(manifest.status, 'complete')
  const names = await fs.readdir(destination)
  const image = path.join(destination, names.find(name => name.endsWith('.png')))
  const bytes = await fs.readFile(image)
  assert.equal(bytes.subarray(1,4).toString(), 'PNG')
  assert.ok(bytes.readUInt32BE(16) > 100)
  const corners = JSON.parse(execFileSync(python, ['-B', '-c',
    'import json,sys; from PIL import Image; image=Image.open(sys.argv[1]).convert("RGB"); x,y=image.width-3,image.height-3; print(json.dumps([image.getpixel(p) for p in [(2,2),(x,2),(2,y),(x,y)]]))',
    image], {cwd:root, windowsHide:true, encoding:'utf8'}))
  assert.ok(corners.every(rgb => rgb.some(value => value > 8)), 'Rendered sky must cover all four corners')
  images.push(image)
}
assert.notEqual(fixture.before.model_sha256, fixture.after.model_sha256)
assert.deepEqual(JSON.parse(await fs.readFile(fixture.before.cameras,'utf8')), JSON.parse(await fs.readFile(fixture.after.cameras,'utf8')))
const skyImages = []
for (const quality of ['balanced', 'high']) {
  for (const [width, height] of [[320,240], [240,320]]) {
    const pair = []
    for (const scene of ['empty', 'block']) {
      const source = fixture.sky_sources[scene]
      const destination = path.join(output, `sky-${quality}-${width}x${height}-${scene}`)
      execFileSync(process.execPath, [path.join(root, 'scripts/cli.mjs'), '--workspace', workspace,
        'render', '--source', source, '--cameras', fixture.sky_cameras, '--output', destination,
        '--width', String(width), '--height', String(height), '--quality', quality],
        {cwd:root, windowsHide:true, encoding:'utf8', timeout:120000})
      const manifest = JSON.parse(await fs.readFile(path.join(destination, 'render_manifest.json'), 'utf8'))
      assert.equal(manifest.status, 'complete')
      assert.equal(manifest.source_sha256, createHash('sha256').update(await fs.readFile(source)).digest('hex'))
      assert.equal(manifest.cameras_sha256, createHash('sha256').update(await fs.readFile(fixture.sky_cameras)).digest('hex'))
      const image = path.join(destination, (await fs.readdir(destination)).find(name => name.endsWith('.png')))
      assert.equal(manifest.images[0].sha256, createHash('sha256').update(await fs.readFile(image)).digest('hex'))
      const pixels = JSON.parse(execFileSync(python, ['-B', '-c',
        'import json,sys; from PIL import Image; im=Image.open(sys.argv[1]).convert("RGB"); w,h=im.size; points=[(2,2),(w-3,2),(2,h-3),(w-3,h-3)]+[(int(w*t),int(h*t)+d) for t in (.2,.8) for d in (-3,3)]; print(json.dumps([im.getpixel(p) for p in points]))', image],
        {cwd:root, windowsHide:true, encoding:'utf8'}))
      assert.ok(pixels.every(rgb => rgb.some(value => value > 8)), `Sky missing for ${quality}, ${width}x${height}, ${scene}`)
      pair.push(image);skyImages.push(image)
    }
    const changed = Number(execFileSync(python, ['-B', '-c',
      'import sys; from PIL import Image,ImageChops; a=Image.open(sys.argv[1]).convert("RGB"); b=Image.open(sys.argv[2]).convert("RGB"); print(sum(1 for p in ImageChops.difference(a,b).get_flattened_data() if p != (0,0,0)))', ...pair],
      {cwd:root, windowsHide:true, encoding:'utf8'}))
    assert.ok(changed > 10, 'The scene block must remain visible against the empty sky')
  }
}
const largeOutput = path.join(output, 'large-textures')
execFileSync(process.execPath, [path.join(root, 'scripts/cli.mjs'), '--workspace', workspace,
  'render', '--source', fixture.large.source, '--cameras', fixture.large_cameras, '--output', largeOutput,
  '--width', '320', '--height', '240'], {cwd:root, windowsHide:true, encoding:'utf8', timeout:120000})
const largeManifest = JSON.parse(await fs.readFile(path.join(largeOutput, 'render_manifest.json'), 'utf8'))
assert.equal(largeManifest.status, 'complete')
assert.equal(largeManifest.source_kind, 'assembly')
assert.equal(largeManifest.source_sha256, fixture.large.source_sha256)
assert.equal(largeManifest.assembly_partitions.length, 2)
const largeSnapshot = JSON.parse(await fs.readFile(path.join(largeOutput, largeManifest.snapshot_file), 'utf8'))
assert.deepEqual(largeSnapshot.size, [300, 384, 300])
assert.deepEqual(largeSnapshot.wall_positions, [[2, 2, 2]])
assert.equal(largeSnapshot.blocks.length, 17)
const largeImage = await fs.readFile(path.join(largeOutput, largeManifest.images[0].image))
assert.equal(largeManifest.images[0].sha256, createHash('sha256').update(largeImage).digest('hex'))
const orthoOutputs={}
for(const scene of ['empty','block']){
  const destination=path.join(output,'orthographic-'+scene)
  execFileSync(process.execPath,[path.join(root,'scripts/cli.mjs'),'--workspace',workspace,'render',
    '--source',fixture.sky_sources[scene],'--cameras',fixture.ortho_cameras,'--output',destination,'--width','256','--height','256'],
    {cwd:root,windowsHide:true,encoding:'utf8',timeout:120000})
  const manifest=JSON.parse(await fs.readFile(path.join(destination,'render_manifest.json'),'utf8'))
  assert.equal(manifest.status,'complete');assert.equal(manifest.views.length,7)
  for(const view of manifest.views){if(view.id==='perspective'){assert.equal(view.projection,undefined);continue}assert.equal(view.projection,'orthographic');assert.equal(view.ortho_height,8)}
  for(const entry of manifest.images){
    const meta=JSON.parse(await fs.readFile(path.join(destination,entry.metadata),'utf8'))
    if(meta.id==='perspective')assert.equal(meta.camera.projection,undefined)
    else {assert.equal(meta.camera.projection,'orthographic');assert.equal(meta.camera.ortho_height,8)}
    const requested=manifest.views.find(view=>view.id===meta.id)
    assert.deepEqual(meta.lighting_options,requested.lighting_options)
  }
  assert.equal(manifest.images.find(item=>item.image==='near.png').sha256,manifest.images.find(item=>item.image==='near-again.png').sha256)
  assert.notEqual(manifest.images.find(item=>item.image==='warm.png').sha256,manifest.images.find(item=>item.image==='cool.png').sha256)
  const warm=manifest.images.find(item=>item.image==='warm.png').sha256,tempOnly=manifest.images.find(item=>item.image==='temp-only.png').sha256
  if(scene==='empty')assert.equal(warm,tempOnly,'Changing light temperature alone must preserve the empty background')
  else assert.notEqual(warm,tempOnly,'Changing light temperature must affect the lit block')
  orthoOutputs[scene]=destination
}
const boxes=JSON.parse(execFileSync(python,['-B','-c',
  'import json,sys; from PIL import Image,ImageChops; out=[];\nfor name in ("near","far"):\n a=Image.open(sys.argv[1]+"/"+name+".png").convert("RGB"); b=Image.open(sys.argv[2]+"/"+name+".png").convert("RGB"); d=ImageChops.difference(a,b).convert("L").point(lambda v:255 if v>20 else 0); out.append(d.getbbox())\nprint(json.dumps(out))',
  orthoOutputs.empty,orthoOutputs.block],{cwd:root,windowsHide:true,encoding:'utf8'}))
assert.ok(boxes.every(box=>box&&box[2]-box[0]>10&&box[3]-box[1]>10),'Orthographic renders must contain visible geometry')
assert.ok(boxes[0].every((value,index)=>Math.abs(value-boxes[1][index])<=2),'Orthographic apparent bounds must not change with camera distance')
const registeredOutputs={}
const frontCamera=path.join(path.dirname(fixture.registered.bundle),fixture.registered.views.front.file)
for(const scene of ['empty','block']){
  const destination=path.join(workspace,'nbt_models/_workspaces','registered-'+scene)
  execFileSync(process.execPath,[path.join(root,'scripts/cli.mjs'),'--workspace',workspace,'render',
    '--source',fixture.reference_sources[scene].source,'--cameras',frontCamera,'--output',destination,'--width','128','--height','128',
    '--camera-bundle',fixture.registered.bundle,'--camera-bundle-sha256',fixture.registered.bundle_sha256],
    {cwd:root,windowsHide:true,encoding:'utf8',timeout:120000})
  const manifest=JSON.parse(await fs.readFile(path.join(destination,'render_manifest.json'),'utf8'))
  assert.equal(manifest.reference_camera_binding.bundle_sha256,fixture.registered.bundle_sha256)
  assert.equal(manifest.reference_camera_binding.view,'front')
  const metadata=JSON.parse(await fs.readFile(path.join(destination,manifest.images[0].metadata),'utf8'))
  assert.deepEqual(metadata.lighting_options,{direction:[.3,.8,.2],temperature_kelvin:4200,background:[.2,.3,.4],exposure:1.1})
  registeredOutputs[scene]=path.join(destination,'front.png')
}
const registeredBox=JSON.parse(execFileSync(python,['-B','-c',
  'import json,sys;from PIL import Image,ImageChops;a=Image.open(sys.argv[1]).convert("RGB");b=Image.open(sys.argv[2]).convert("RGB");d=ImageChops.difference(a,b).convert("L").point(lambda v:255 if v>20 else 0);print(json.dumps(d.getbbox()))',
  registeredOutputs.empty,registeredOutputs.block],{cwd:root,windowsHide:true,encoding:'utf8'}))
assert.ok(registeredBox&&registeredBox.every((value,index)=>Math.abs(value-[56,56,72,72][index])<=2),'Registered material camera must align the block to the reference pixels')
const reviewRequest=path.join(workspace,'blind-review-request.json')
const renders=[]
for(const scene of ['empty','block']){
  const file=path.join(path.dirname(registeredOutputs[scene]),'render_manifest.json')
  renders.push({manifest:file,sha256:createHash('sha256').update(await fs.readFile(file)).digest('hex')})
}
await fs.writeFile(reviewRequest,JSON.stringify({renders,scope:'合成同机位对照',crop:[32,32,96,96],output:'nbt_models/_workspaces/reference-reviews/actual-blind'}))
const referenceCli=[path.join(root,'scripts/cli.mjs'),'--workspace',workspace,'reference']
const pack=JSON.parse(execFileSync(process.execPath,[...referenceCli,'review-prepare','--request',reviewRequest],{cwd:root,windowsHide:true,encoding:'utf8',timeout:120000}))
const publicData=JSON.parse(await fs.readFile(pack.public,'utf8'))
assert.equal(publicData.views.length,1);assert.ok(publicData.views[0].changed_pixels>0)
const observationPath=path.join(workspace,'blind-observation-request.json')
await fs.writeFile(observationPath,JSON.stringify({public:pack.public,public_sha256:pack.public_sha256,decision:'inconclusive',actor:'agent',
  observations:[{view:'view-01',note:'合成回归检查，记录变化区域。',remaining:'不代表真实用户审阅。'}],output:'nbt_models/_workspaces/reference-reviews/actual-observation.json'}))
const observation=JSON.parse(execFileSync(process.execPath,[...referenceCli,'review-record','--request',observationPath],{cwd:root,windowsHide:true,encoding:'utf8',timeout:120000}))
assert.equal(observation.approval_created,false)
const verifyPath=path.join(workspace,'blind-verify-request.json')
await fs.writeFile(verifyPath,JSON.stringify({binding:pack.binding,binding_sha256:pack.binding_sha256,record:observation.record,record_sha256:observation.record_sha256}))
const verified=JSON.parse(execFileSync(process.execPath,[...referenceCli,'review-verify','--request',verifyPath],{cwd:root,windowsHide:true,encoding:'utf8',timeout:120000}))
assert.equal(verified.valid,true);assert.equal(verified.approval_created,false)
await fs.appendFile(frontCamera,' ')
assert.throws(()=>execFileSync(process.execPath,[...referenceCli,'review-verify','--request',verifyPath],{cwd:root,windowsHide:true,encoding:'utf8',stdio:'pipe',timeout:120000}))
const result = {passed:true, output, images, skyImages, largeAssemblyRender:largeOutput, orthographic:orthoOutputs, registeredCamera:registeredOutputs, blindReview:pack.public, sameCamera:true, skyCornersCovered:true, sourceRoundtrip:true, nbtExported:false}
await fs.writeFile(path.join(output,'results.json'), JSON.stringify(result,null,2))
console.log(JSON.stringify(result))
