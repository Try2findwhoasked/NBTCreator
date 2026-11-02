// Synthetic browser regression: no user models, approvals, or running browser sessions.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {parseArgs} from 'node:util'
import {Box3, Vector3} from 'three'
import {RangeBox} from './src/range-box.mjs'
import {createViewerServer} from './viewer-server.mjs'
import {launchRenderBrowser} from './browser-launch.mjs'

const {values}=parseArgs({options:{output:{type:'string'}}})
if(!values.output)throw new Error('Usage: node test-selection.mjs --output new-directory')
const root=path.resolve(values.output);await fs.mkdir(root)
const checks={}
function checkEdges(box,lo,hi){
  box.updateMatrixWorld(true)
  assert.equal(box.geometry.index,null)
  const p=box.geometry.attributes.position
  assert.equal(p.count,24)
  const edges=new Set(),degree=new Map()
  for(let i=0;i<p.count;i+=2){
    const a=[p.getX(i),p.getY(i),p.getZ(i)], b=[p.getX(i+1),p.getY(i+1),p.getZ(i+1)]
    assert.equal(a.filter((v,j)=>v!==b[j]).length,1,'each edge must follow exactly one axis')
    for(const vertex of [a,b]){
      vertex.forEach((v,j)=>assert.ok(v===lo[j]||v===hi[j]))
      const key=vertex.join(',');degree.set(key,(degree.get(key)??0)+1)
    }
    edges.add([a.join(','),b.join(',')].sort().join('|'))
  }
  assert.equal(edges.size,12);assert.equal(degree.size,8)
  for(const count of degree.values())assert.equal(count,3)
}
const box=new RangeBox(new Box3(new Vector3(2,3,4),new Vector3(46,21,45)),0x77e7b2)
checkEdges(box,[2,3,4],[46,21,45])
box.box.set(new Vector3(7,5,9),new Vector3(8,6,10));checkEdges(box,[7,5,9],[8,6,10])
box.geometry.dispose();box.material.dispose();checks.twelve_axis_aligned_unique_edges_after_resize=true
const model=path.join(root,'snapshot.json')
const blocks=[];for(let x=0;x<48;x++)for(let z=0;z<48;z++)blocks.push([[x,0,z],'minecraft:stone'])
await fs.writeFile(model,JSON.stringify({size:[48,24,48],blocks,wall_positions:[],cameras:[]}))
const server=await createViewerServer({model});let browser
try{
  browser=await launchRenderBrowser()
  for(const quality of ['fast','balanced']){
    const page=await browser.newPage({viewport:{width:1000,height:700}}),errors=[]
    page.on('pageerror',e=>errors.push(e.message))
    await page.goto(server.url+'?embedded=1&quality='+quality)
    await page.waitForFunction(()=>window.nbtModeler?.status==='ready',undefined,{timeout:60000})
    const result=await page.evaluate(async()=>{
      const api=window.nbtModeler,r=api.renderer.renderer,gl=r.getContext(),calls=[]
      const draw=gl.drawArrays.bind(gl)
      gl.drawArrays=(mode,start,count)=>{if(mode===gl.LINES)calls.push({start,count});return draw(mode,start,count)}
      const meshBuilds=api.metadata().mesh_builds
      api.setSelectionRange({lo:[2,2,2],hi:[45,20,45]})
      await api.setCamera({eye:[65,50,65],target:[24,10,24]})
      const initial=calls.slice();calls.length=0
      api.setSelectionRange({lo:[8,3,8],hi:[30,15,34]})
      await api.setCamera({eye:[-45,38,65],target:[24,10,24]})
      const resized=calls.slice();calls.length=0
      api.setSelectionRange(null)
      await api.setCamera({eye:[65,50,65],target:[24,10,24]})
      const hidden=calls.slice()
      api.setSelectionRange({lo:[2,2,2],hi:[45,20,45]})
      await api.setCamera({eye:[65,50,65],target:[24,10,24]})
      return {initial,resized,hidden,meshBuilds,after:api.metadata().mesh_builds}
    })
    assert.ok(result.initial.some(c=>c.count===24))
    assert.ok(result.resized.some(c=>c.count===24))
    assert.equal(result.hidden.length,0)
    assert.equal(result.meshBuilds,result.after)
    assert.deepEqual(errors,[])
    await page.screenshot({path:path.join(root,quality+'.png')})
    checks[quality+'_gpu_lines_resize_hide_and_no_model_rebuild']=true
    await page.close()
  }
  await fs.writeFile(path.join(root,'results.json'),JSON.stringify({passed:true,checks},null,2))
  console.log({passed:true,checks})
}finally{await browser?.close();await server.close()}
