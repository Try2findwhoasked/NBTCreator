// Adapted from mattzh72/minecraft-builder-skill ce57d48; Apache-2.0. See LICENSE.upstream.
import { vec3 } from 'gl-matrix'
import { ViewCamera } from './camera-controls.mjs'
import { MeshNormalMaterial,Scene,Box3,Vector2,Vector3,Raycaster,Matrix3 } from 'three'
import { BlockState, Structure, ThreeStructureRenderer, ChunkBuilder, loadDefaultPackResources } from '@mattzh72/lodestone'
import {installMeshScheduling} from './mesh-scheduling.mjs'
import './style.css'
import { RangeBox } from './range-box.mjs'
import {differenceIndex,focusDifference} from './difference-index.mjs'
import {differenceOverlay} from './difference-overlay.js'
import {protectionOverlay} from './protection-overlay.js'
import {walkOverlay} from './walk-overlay.js'
import {createComponentGizmo} from './component-gizmo.js'
import { cameraView, normalizeView, includesBlock } from './view-contract.mjs'

installMeshScheduling(ThreeStructureRenderer,ChunkBuilder)

const originalWarn = console.warn.bind(console)
console.warn = (...args) => {
  if (args.length === 1 && args[0] === 'parent minecraft:builtin/entity does not exist!') return
  originalWarn(...args)
}

const LIGHTING_PRESETS = {
  day: {
    direction: vec3.fromValues(0.35, 0.85, 0.25),
    intensity: 1.15,
    ambientIntensity: 0.62,
    fillIntensity: 0.32,
    rimIntensity: 0.35,
    exposure: 1.08,
    sky: {
      zenithColor: [0.24, 0.48, 0.84],
      horizonColor: [0.78, 0.9, 1.0],
      groundColor: [0.18, 0.2, 0.22],
      stars: {
        enabled: false,
      },
    },
    fog: {
      color: [0.78, 0.86, 0.94],
      density: 0.00012,
      heightFalloff: 0.001,
    },
  },
  night: {
    direction: vec3.fromValues(-0.32, 0.5, -0.42),
    color: [0.62, 0.72, 1.0],
    ambientColor: [0.34, 0.43, 0.72],
    fillColor: [0.13, 0.18, 0.36],
    rimColor: [0.5, 0.64, 1.0],
    intensity: 0.28,
    ambientIntensity: 0.52,
    fillIntensity: 0.2,
    rimIntensity: 0.42,
    exposure: 0.92,
    sky: {
      zenithColor: [0.015, 0.025, 0.08],
      horizonColor: [0.055, 0.085, 0.18],
      groundColor: [0.018, 0.022, 0.038],
      sunGlowColor: [0.48, 0.6, 1.0],
      sunGlowIntensity: 0.22,
      sunGlowExponent: 20,
      stars: {
        enabled: true,
        density: 0.72,
        brightness: 0.92,
      },
    },
    disc: {
      size: 42,
      coreColor: [0.72, 0.78, 1.0],
      glowColor: [0.34, 0.45, 0.92],
      coreIntensity: 0.42,
      glowIntensity: 0.16,
      softness: 0.4,
    },
    fog: {
      color: [0.035, 0.05, 0.1],
      density: 0.00008,
      heightFalloff: 0.00065,
    },
    shadow: {
      enabled: true,
      intensity: 0.2,
      softness: 0.82,
    },
    emissive: {
      range: 18,
      intensity: 1.35,
      tint: [1.0, 0.88, 0.68],
    },
  },
}


function getParam(name, fallback) {
  const params = new URLSearchParams(window.location.search)
  return params.get(name) ?? fallback
}

function getLightingMode() {
  const value = getParam('lighting', 'day').toLowerCase()
  return value === 'night' ? 'night' : 'day'
}

function setLightingUrl(mode) {
  const url = new URL(window.location.href)
  if (mode === 'day') {
    url.searchParams.delete('lighting')
  } else {
    url.searchParams.set('lighting', mode)
  }
  window.history.replaceState({}, '', url)
}

function updateLightingButton(button, mode) {
  button.textContent = mode === 'night' ? 'Day' : 'Night'
  button.title = mode === 'night' ? 'Switch to day lighting' : 'Switch to night lighting'
  button.setAttribute('aria-pressed', String(mode === 'night'))
}

const api = { status: 'loading' }
window.nbtModeler = api

async function main() {
  if (getParam('embedded', '0') === '1') document.body.classList.add('embedded')
  const canvas = document.getElementById('preview')
  const loading = document.getElementById('loading')
  const modelKey = getParam('model_key', '')
  const response = await fetch('/__nbt_modeler__/model.json' + (modelKey ? '?model_key=' + encodeURIComponent(modelKey) : ''), { cache: 'no-store' })
  if (!response.ok) throw new Error(`Model load failed: ${response.status}`)
  let snapshot = await response.json()
  const pack = await loadDefaultPackResources({ baseUrl: new URL('/__minecraft_builder__/default-pack/', location.href).toString() })
  let size = snapshot.size
  const quality = getParam('quality', 'balanced')
  if (!['fast', 'balanced', 'high'].includes(quality)) throw new Error('quality must be fast/balanced/high')
  const maxFps = Number(getParam('maxFps', quality === 'fast' ? '24' : '60'))
  if (!Number.isFinite(maxFps) || maxFps < 1 || maxFps > 60) throw new Error('maxFps must be 1..60')
  const pixelRatio = Math.min(1.5, Math.max(0.5, Number(getParam('pixelRatio', '1'))))
  if (!Number.isFinite(pixelRatio)) throw new Error('Invalid pixelRatio')
  let lightingMode = getLightingMode()
  let fov = 60
  const cut = document.getElementById('cut-level')
  const layer = document.getElementById('layer')
  const cutValue = document.getElementById('cut-value')
  const lightingToggle = document.getElementById('lighting-toggle')
  const walls = new Set(snapshot.wall_positions.map(p => p.join(',')))
  const palette = []
  const paletteIds = new Map()
  let indexed = snapshot.blocks.map(([pos, value]) => {
    if (!paletteIds.has(value)) {
      paletteIds.set(value, palette.length)
      palette.push(BlockState.parse(value))
    }
    return { pos, state: paletteIds.get(value) }
  })
  let activeBlocks = indexed
  let activeLayer = 'all'
  let activeCuts = []
  let filterKey = JSON.stringify([activeLayer, activeCuts])
  let meshBuilds = 1
  let renderedFrames = 0
  const started = performance.now()
  function sunlight(mode) {
    const preset = LIGHTING_PRESETS[mode]
    return { ...preset, shadow: { ...preset.shadow, enabled: quality === 'high', mapSize: 1024 } }
  }
  const renderer = new ThreeStructureRenderer(canvas, new Structure(size, palette, indexed), pack.resources, {
    chunkSize: 16, useInvisibleBlockBuffer: false, asyncBuild: true,
    asyncChunkBuildTimeMs: 8, sunlight: sunlight(lightingMode),
  })
  if (quality === 'fast') {
    // The upstream colored pass encodes picking IDs, not display colors.
    renderer.coloredMaterial.dispose()
    renderer.coloredMaterial = new MeshNormalMaterial({ flatShading: true })
    renderer.renderer.setClearColor(0x263442, 1)
  }
  const selectionScene=new Scene()
  const differences=differenceOverlay()
  const protection=protectionOverlay();let protectionData=null,protectionConflicts=[],protectionEnabled=false
  const walk=walkOverlay();let walkData=null,walkOptions={enabled:false,target:0}
  let differenceData=null,differenceLookup=null,differenceSide='after',differenceEnabled=false,differenceOnly=false
  function updateDifferenceOverlay(){differences.update(differenceData,{cuts:activeCuts,layer:activeLayer,side:differenceSide,enabled:differenceEnabled})}
  const selectionBox=new RangeBox(new Box3(new Vector3(),new Vector3(1,1,1)),0x77e7b2)
  const pickedBox=new RangeBox(new Box3(new Vector3(),new Vector3(1,1,1)),0xffd469)
  for(const helper of [selectionBox,pickedBox]){helper.visible=false;helper.material.depthTest=false;helper.material.transparent=true;helper.material.opacity=.95;helper.renderOrder=1000;selectionScene.add(helper)}
  let selectionRange=null
  let commentMarkers=[]
  const markerLayer=document.createElement('div');markerLayer.className='voxel-marker-layer';document.body.append(markerLayer)
  function clearCommentMarkers(){for(const item of commentMarkers){selectionScene.remove(item.box);item.box.geometry.dispose();item.box.material.dispose()};commentMarkers=[];markerLayer.replaceChildren()}
  function setCommentMarkers(markers=[]){
    clearCommentMarkers()
    for(const marker of markers){
      const box=new RangeBox(new Box3(new Vector3(...marker.position),new Vector3(...marker.position.map(v=>v+1))),marker.status==='draft'?0xffd469:marker.status==='resolved'?0x77e7b2:0xff6576)
      box.material.depthTest=false;box.material.transparent=true;box.material.opacity=.9;selectionScene.add(box)
      const label=document.createElement('button');label.textContent='#'+marker.number;label.className='voxel-marker '+marker.status;label.title=marker.position.join(', ')+' · '+(marker.text ?? '未保存；点击移除此点')
      label.addEventListener('click',()=>{if(window.parent!==window)window.parent.postMessage({type:'nbt-annotation-focused',number:marker.number,draft:marker.status==='draft'},location.origin)})
      markerLayer.append(label);commentMarkers.push({...marker,box,label})
    }
    requestRender()
  }
  const center = vec3.fromValues(size[0] / 2, Math.max(1, size[1] / 2.5), size[2] / 2)
  const camera = new ViewCamera(canvas, center, Math.max(18, Math.max(...size) * 1.9), requestRender)
  let componentGizmo=null
  let frameRequest = 0
  let renderTimer = 0, lastDraw = -Infinity, viewportKey = ''
  let queue = Promise.resolve()
  function enqueue(action) {
    const result = queue.then(action)
    queue = result.catch(() => {})
    return result
  }
  function draw() {
    if (frameRequest) cancelAnimationFrame(frameRequest)
    if (renderTimer) clearTimeout(renderTimer)
    renderTimer = 0
    frameRequest = 0
    const state = camera.getCamera()
    renderer.setCamera({ position: state.position, target: state.target, up: state.up ?? [0, 1, 0], fov })
    if (quality === 'fast') renderer.drawColoredStructure()
    else renderer.drawStructure()
    const rect=canvas.getBoundingClientRect()
    for(const marker of commentMarkers){
      const p=new Vector3(...marker.position.map(v=>v+.5)).project(renderer.camera)
      const visible=p.z>=-1&&p.z<=1&&Math.abs(p.x)<=1&&Math.abs(p.y)<=1&&includesBlock(marker.position,activeCuts)&&(activeLayer==='all'||(activeLayer==='walls')===walls.has(marker.position.join(',')))
      marker.box.visible=visible;marker.label.hidden=!visible
      marker.label.style.left=rect.left+(p.x+1)*rect.width/2+'px';marker.label.style.top=rect.top+(1-p.y)*rect.height/2+'px'
    }
    const autoClear=renderer.renderer.autoClear
    renderer.renderer.autoClear=false;renderer.renderer.render(differences.scene,renderer.camera);renderer.renderer.render(protection.scene,renderer.camera);renderer.renderer.render(walk.scene,renderer.camera);if(componentGizmo)renderer.renderer.render(componentGizmo.scene,renderer.camera);renderer.renderer.clearDepth();renderer.renderer.render(selectionScene,renderer.camera);if(componentGizmo)renderer.renderer.render(componentGizmo.handlesScene,renderer.camera);renderer.renderer.autoClear=autoClear
    lastDraw = performance.now()
    renderedFrames += 1
    canvas.dataset.frameSerial = String(renderedFrames)
    canvas.dataset.meshBuilds = String(meshBuilds)
    canvas.dataset.camera = JSON.stringify(currentCamera())
  }
  function requestRender() {
    if (frameRequest || renderTimer) return
    const delay = Math.max(0, 1000/maxFps-(performance.now()-lastDraw))
    if (delay > 1) renderTimer = setTimeout(() => { renderTimer=0; frameRequest=requestAnimationFrame(draw) }, delay)
    else frameRequest = requestAnimationFrame(draw)
  }
  function currentCamera() {
    const state = renderer.getCamera()
    return { eye: Array.from(state.position), target: Array.from(state.target), up: Array.from(state.up), fov: state.fov }
  }
  function setCamera(view) {
    const state = cameraView(view)
    camera.fixed = { position: state.eye, target: state.target, up: state.up }
    fov = state.fov;camera.fov=fov
  }
  function setLighting(mode) {
    if (mode !== lightingMode) {
      lightingMode = mode
      renderer.setSunlight(sunlight(mode))
    }
    updateLightingButton(lightingToggle, lightingMode)
    setLightingUrl(lightingMode)
  }
  async function applyFilter(nextLayer, cuts) {
    const key = JSON.stringify([nextLayer, cuts,differenceOnly])
    if (key === filterKey) return
    const blocks = indexed.filter(({ pos }) => includesBlock(pos, cuts) &&
      (nextLayer === 'all' || (nextLayer === 'walls') === walls.has(pos.join(',')))&&(!differenceOnly||differenceLookup?.has(pos)))
    if (blocks.length !== activeBlocks.length || blocks.some((block, index) => block !== activeBlocks[index])) {
      renderer.setStructure(new Structure(size, palette, blocks))
      meshBuilds += 1
      await renderer.whenReady()
    }
    activeBlocks = blocks
    activeLayer = nextLayer
    activeCuts = cuts
    filterKey = key
    updateDifferenceOverlay();protection.update(protectionData,protectionConflicts,activeCuts,protectionEnabled);walk.update(walkData,walkOptions,activeCuts)
    canvas.dataset.meshBuilds = String(meshBuilds)
    cutValue.textContent = `${cuts.length ? JSON.stringify(cuts) : '完整模型'} · ${nextLayer}`
  }
  function metadata() {
    return {
      source_sha256: snapshot.source_sha256, geometry_sha256: snapshot.geometry_sha256,
      registry_sha256: snapshot.registry_sha256, camera: currentCamera(),
      cuts: activeCuts, layer: activeLayer, lighting: lightingMode, quality, pixel_ratio: pixelRatio,
      width: canvas.width, height: canvas.height, visible_blocks: activeBlocks.length, interaction_max_fps: maxFps,
      mesh_builds: meshBuilds, rendered_frames: renderedFrames,
      verification: snapshot.verification,
      rendering: 'Lodestone default-pack visual preview; no Minecraft collision or light-propagation certification',
    }
  }
  async function applyView(view) {
    await applyFilter(view.layer, view.cuts)
    setLighting(view.lighting)
    setCamera(view)
    layer.value = view.layer
    draw()
  }
  const reportError = error => {
    console.error(error)
    document.getElementById('inspection').textContent = error.message
  }
  document.getElementById('build-name').textContent = snapshot.name
  document.getElementById('build-stats').textContent = `${size.join(' x ')} | ${indexed.length.toLocaleString()} blocks`
  document.getElementById('source-hash').textContent = `源 SHA256: ${snapshot.source_sha256}`
  cut.max = String(size[1] - 1)
  cut.value = cut.max
  cutValue.textContent = '完整模型 · all'
  updateLightingButton(lightingToggle, lightingMode)
  function uiFilter() {
    const nextLayer = layer.value
    // The slider is a simple user control. Batch cuts support additional axes.
    const cuts = Number(cut.value) === size[1] - 1 ? []
      : [{ axis: 'y', position: Number(cut.value) + 1, removed_side: 'above' }]
    enqueue(async () => { await applyFilter(nextLayer, cuts); draw() }).catch(reportError)
  }
  cut.addEventListener('change', uiFilter)
  layer.addEventListener('change', uiFilter)
  lightingToggle.addEventListener('click', () => {
    enqueue(() => { setLighting(lightingMode === 'day' ? 'night' : 'day'); draw() }).catch(reportError)
  })
  for (const preset of snapshot.cameras) {
    const button = document.createElement('button')
    button.textContent = preset.role
    button.addEventListener('click', () => {
      // A camera change never invokes setStructure or changes the current cut/layer.
      enqueue(() => { setCamera(preset); draw() }).catch(reportError)
    })
    document.getElementById('camera-presets').append(button)
  }

  function download(name, value, type = 'application/json') {
    const link = document.createElement('a')
    const url = URL.createObjectURL(value instanceof Blob ? value : new Blob([value], { type }))
    link.href = url; link.download = name; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  document.getElementById('save-view').addEventListener('click', () => {
    enqueue(() => download('camera.json', JSON.stringify(metadata(), null, 2))).catch(reportError)
  })
  document.getElementById('save-image').addEventListener('click', () => {
    enqueue(async () => {
      draw()
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'))
      if (!blob) throw new Error('PNG encoding failed')
      download('preview.png', blob)
    }).catch(reportError)
  })
  const lookup = new Map(snapshot.blocks.map(([p, value]) => [p.join(','), value]))
  const owners = new Map(snapshot.owners ?? [])
  document.getElementById('inspect').addEventListener('click', () => {
    const p = document.getElementById('position').value.trim().split(',').map(Number)
    const valid = p.length === 3 && p.every((v, i) => Number.isInteger(v) && v >= 0 && v < size[i])
    document.getElementById('inspection').textContent = valid
      ? `${lookup.get(p.join(',')) ?? 'minecraft:air'} · operation: ${owners.get(p.join(',')) ?? '未记录'}`
      : '请输入界内整数坐标 x,y,z'
  })
  function resize() {
    const rect = canvas.getBoundingClientRect()
    if (rect.width <= 0 || rect.height <= 0) return false
    const key = `${rect.width}:${rect.height}:${pixelRatio}`
    if (key === viewportKey) return false
    viewportKey = key
    renderer.setViewport(0, 0, rect.width, rect.height, pixelRatio)
    return true
  }
  resize()
  await renderer.whenReady()
  draw()
  loading.classList.add('hidden')
  const observer = new ResizeObserver(() => { if (resize()) requestRender() })
  observer.observe(canvas)
  window.addEventListener('pagehide', () => {
    observer.disconnect()
    if (frameRequest) cancelAnimationFrame(frameRequest)
    if (renderTimer) clearTimeout(renderTimer)
    for(const helper of [selectionBox,pickedBox]){helper.geometry.dispose();helper.material.dispose()}
    clearCommentMarkers();markerLayer.remove()
    differences.clear()
    protection.clear()
    walk.clear()
    componentGizmo?.dispose()
    renderer.dispose()
  }, { once: true })
  function setSelectionRange(range){
    selectionRange=range
    selectionBox.visible=Boolean(range)&&range.lo.every((v,i)=>Number.isInteger(v)&&Number.isInteger(range.hi[i])&&v>=0&&v<=range.hi[i]&&range.hi[i]<size[i])
    if(selectionBox.visible){selectionBox.box.min.fromArray(range.lo);selectionBox.box.max.fromArray(range.hi.map(v=>v+1));selectionBox.updateMatrixWorld(true)}
    requestRender();return {visible:selectionBox.visible,range:selectionRange}
  }
  const raycaster=new Raycaster()
  function pickBlock(x,y){
    renderer.structureScene.updateMatrixWorld(true);renderer.camera.updateMatrixWorld(true)
    raycaster.setFromCamera(new Vector2(x,y),renderer.camera)
    const visible=new Set(activeBlocks.map(block=>block.pos.join(',')))
    for(const hit of raycaster.intersectObjects(renderer.structureScene.children,true)){
      if(!hit.face)continue
      const normal=hit.face.normal.clone().applyMatrix3(new Matrix3().getNormalMatrix(hit.object.matrixWorld)).normalize()
      const position=hit.point.clone().addScaledVector(normal,-.001).floor().toArray(),key=position.join(','),value=lookup.get(key)
      if(!value||!visible.has(key)||['minecraft:air','minecraft:cave_air','minecraft:void_air'].includes(value.split('[')[0]))continue
      pickedBox.box.min.fromArray(position);pickedBox.box.max.fromArray(position.map(v=>v+1));pickedBox.visible=true;requestRender()
      return {position,surface:hit.point.toArray(),normal:normal.toArray().map(v=>Math.round(v)),state:value,source_sha256:snapshot.source_sha256,geometry_sha256:snapshot.geometry_sha256,view:metadata()}
    }
    pickedBox.visible=false;requestRender();return null
  }
  let pickStart=null,pickMoved=false
  canvas.addEventListener('pointerdown',event=>{if(canvas.dataset.transformDragging==='true')return;if(canvas.dataset.pickMode==='true'&&event.button===0){event.preventDefault();pickStart=[event.clientX,event.clientY];pickMoved=false}})
  canvas.addEventListener('pointermove',event=>{if(pickStart&&Math.hypot(event.clientX-pickStart[0],event.clientY-pickStart[1])>5)pickMoved=true})
  canvas.addEventListener('pointerup',event=>{
    if(!pickStart||event.button!==0||canvas.dataset.transformDragging==='true')return
    const start=pickStart;pickStart=null;if(pickMoved||Math.hypot(event.clientX-start[0],event.clientY-start[1])>5)return
    const rect=canvas.getBoundingClientRect(),result=pickBlock((event.clientX-rect.left)/rect.width*2-1,1-(event.clientY-rect.top)/rect.height*2)
    if(window.parent!==window)window.parent.postMessage({type:canvas.dataset.pickPurpose==='comment'?'nbt-coordinate-picked':'nbt-material-picked',result},location.origin)
  })
  canvas.addEventListener('pointercancel',()=>pickStart=null)
  componentGizmo=createComponentGizmo({canvas,camera:renderer.camera,viewCamera:camera,requestRender,notify:value=>{if(window.parent!==window)window.parent.postMessage({type:'nbt-transform-change',value,source_sha256:snapshot.source_sha256,geometry_sha256:snapshot.geometry_sha256},location.origin)}})
  window.addEventListener('keydown',event=>{if(componentGizmo.state()&&!event.ctrlKey&&!event.metaKey&&!event.altKey&&['Escape','KeyW','KeyE'].includes(event.code)){event.preventDefault();window.parent.postMessage({type:'nbt-transform-key',code:event.code},location.origin)}})
  Object.assign(api, {
    snapshot, renderer, camera, metadata,
    setControls:value=>camera.setControls(value),
    configureTransform:value=>enqueue(()=>{const result=componentGizmo.configure(value);draw();return result}),
    transformStatus:()=>componentGizmo.state(),transformHandles:()=>componentGizmo.screenHandles(),
    setSelectionRange,pickBlock,setCommentMarkers,
    commentMarkerStatus:()=>commentMarkers.map(({number,position,status})=>({number,position,status})),
    selectionStatus:()=>({visible:selectionBox.visible,range:selectionRange}),
    setPicking:(enabled,purpose='material')=>{canvas.dataset.pickMode=String(Boolean(enabled));canvas.dataset.pickPurpose=purpose;canvas.style.cursor=enabled?'crosshair':''},
    replaceSnapshot: next => enqueue(async()=>{
      if(walkData&&(walkData.source_sha256!==next.source_sha256||walkData.geometry_sha256!==next.geometry_sha256)){walkData=null;walk.clear()}
      if(protectionData&&protectionData.source_sha256!==next.source_sha256){protectionData=null;protectionConflicts=[];protectionEnabled=false;protection.clear()}
      size=next.size;cut.max=String(size[1]-1);cut.value=String(Math.min(Number(cut.value),size[1]-1))
      const nextPalette=[],ids=new Map()
      const nextIndexed=next.blocks.map(([pos,value])=>{if(!ids.has(value)){ids.set(value,nextPalette.length);nextPalette.push(BlockState.parse(value))}return {pos,state:ids.get(value)}})
      snapshot=next;api.snapshot=next;pickedBox.visible=false;indexed=nextIndexed;palette.splice(0,palette.length,...nextPalette)
      walls.clear();next.wall_positions.forEach(p=>walls.add(p.join(',')))
      lookup.clear();next.blocks.forEach(([p,value])=>lookup.set(p.join(','),value));owners.clear()
      for(const [position,owner] of next.owners??[])owners.set(position,owner)
      document.getElementById('build-name').textContent=next.name;document.getElementById('build-stats').textContent=`${size.join(' x ')} | ${indexed.length.toLocaleString()} blocks`;document.getElementById('source-hash').textContent=`源 SHA256: ${next.source_sha256}`
      const blocks=indexed.filter(({pos})=>includesBlock(pos,activeCuts)&&(activeLayer==='all'||(activeLayer==='walls')===walls.has(pos.join(',')))&&(!differenceOnly||differenceLookup?.has(pos)))
      renderer.setStructure(new Structure(size,palette,blocks));meshBuilds+=1;await renderer.whenReady();activeBlocks=blocks
      updateDifferenceOverlay();protection.update(protectionData,protectionConflicts,activeCuts,protectionEnabled);walk.update(walkData,walkOptions,activeCuts)
      draw();return metadata()
    }),
    setDifference: (data,options={}) => enqueue(async()=>{
      const side=options.side??'after'
      if(!['before','after'].includes(side))throw Error('差异方向无效')
      if(data&&(data[side+'_geometry_sha256']!==snapshot.geometry_sha256||data[side+'_source_sha256']!==snapshot.source_sha256))throw Error('差异数据不属于当前画面')
      differenceLookup=data?differenceIndex(data):null;differenceData=data;differenceSide=side;differenceEnabled=!!data&&options.enabled!==false;differenceOnly=!!data&&options.only===true
      filterKey='';await applyFilter(activeLayer,activeCuts);draw();return api.differenceStatus()
    }),
    differenceStatus:()=>({enabled:differenceEnabled,only:differenceOnly,side:differenceSide,...differences.status()}),
    setProtection:(data,options={})=>{
      if(data&&(data.schema_version!==1||data.source_sha256!==snapshot.source_sha256||JSON.stringify(data.size)!==JSON.stringify(size)||!Array.isArray(data.runs)||data.runs.length>200000||data.runs.some(run=>!Array.isArray(run)||run.length!==4||!run.every(Number.isSafeInteger)||Math.min(...run.slice(0,3))<0||run[3]<1||run[0]+run[3]>size[0]||run[1]>=size[1]||run[2]>=size[2])))throw Error('保护区数据不属于当前模型或坐标无效')
      const conflicts=options.conflicts??[];if(!Array.isArray(conflicts)||conflicts.length>4096||conflicts.some(p=>!Array.isArray(p)||p.length!==3||p.some((n,i)=>!Number.isSafeInteger(n)||n<0||n>=size[i])))throw Error('保护冲突坐标无效')
      protectionData=data;protectionConflicts=conflicts;protectionEnabled=!!data&&options.enabled!==false;protection.update(data,conflicts,activeCuts,protectionEnabled);requestRender();return api.protectionStatus()
    },
    protectionStatus:()=>({enabled:protectionEnabled,count:protectionData?.count??0,conflicts:protectionConflicts.length,...protection.status()}),
    setWalkInspection:(data,options={})=>{
      if(data&&(data.schema_version!==1||data.source_sha256!==snapshot.source_sha256||data.geometry_sha256!==snapshot.geometry_sha256||JSON.stringify(data.size)!==JSON.stringify(size)||!Array.isArray(data.poses)||data.poses.length>33||!Array.isArray(data.report?.targets)||data.report.targets.length>32))throw Error('通路检查数据不属于当前画面')
      if(!Number.isInteger(options.target??0)||(options.target??0)<0||(data&&(options.target??0)>=data.report.targets.length))throw Error('通路终点无效')
      walkData=data;walkOptions={enabled:!!data&&options.enabled!==false,target:options.target??0};walk.update(walkData,walkOptions,activeCuts);requestRender();return api.walkStatus()
    },
    walkStatus:()=>({enabled:!!walkData&&walkOptions.enabled,geometry_sha256:walkData?.geometry_sha256??null,...walk.status()}),
    focusDifference: bounds => enqueue(async()=>{
      await applyFilter('all',[]);layer.value='all';cut.value=cut.max
      setCamera(focusDifference(bounds,currentCamera(),canvas.clientWidth/Math.max(1,canvas.clientHeight)));draw();return metadata()
    }),
    setCamera: view => enqueue(() => { setCamera(view); draw(); return metadata() }),
    renderView: view => enqueue(async () => { await applyView(normalizeView(view, size)); return metadata() }),
    captureCurrent: () => enqueue(async () => {
      await renderer.whenReady();draw()
      const image=document.createElement('canvas'),ratio=Math.min(1,1280/Math.max(canvas.width,canvas.height));image.width=Math.max(1,Math.round(canvas.width*ratio));image.height=Math.max(1,Math.round(canvas.height*ratio));image.getContext('2d').drawImage(canvas,0,0,image.width,image.height)
      return {dataUrl:image.toDataURL('image/jpeg',.82),width:image.width,height:image.height}
    }),
    capture: view => enqueue(async () => {
      await applyView(normalizeView(view, size))
      // Encode in the same task as the completed draw: never read a cleared WebGL buffer.
      const dataUrl = canvas.toDataURL('image/png')
      return { dataUrl, metadata: metadata() }
    }),
    initialization_ms: performance.now() - started,
  })
  Object.defineProperty(api, 'visibleBlocks', { get: () => activeBlocks.length })
}

api.ready = main().then(() => { api.status = 'ready' }).catch(error => {
  api.status = 'error'
  api.error = error.message
  document.getElementById('loading').textContent = error.message
  console.error(error)
  throw error
})
