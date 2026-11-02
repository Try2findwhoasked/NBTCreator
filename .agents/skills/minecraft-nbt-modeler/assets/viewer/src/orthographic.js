export function createOrthographic({getInfo,getRange,setRange}){
 const dialog=document.getElementById('orthographic-dialog'),host=document.getElementById('orthographic-views')
 const views=[{id:'top',title:'俯视 X → / Z ↓',axes:[0,2],flip:false},{id:'front',title:'正视 X → / Y ↑',axes:[0,1],flip:true},{id:'side',title:'侧视 Z → / Y ↑',axes:[2,1],flip:true}]
 const painters=[]
 for(const view of views){
  const section=document.createElement('section'),label=document.createElement('strong'),canvas=document.createElement('canvas');label.textContent=view.title;canvas.dataset.projection=view.id;canvas.setAttribute('aria-label',view.title+'拖动框选');section.append(label,canvas);host.append(section)
  let box,start
  function paint(){
   const info=getInfo(),projection=info?.projections?.[view.id];if(!projection)return
   const rect=canvas.getBoundingClientRect();if(!rect.width||!rect.height)return
   const ratio=Math.min(devicePixelRatio,2);canvas.width=rect.width*ratio;canvas.height=rect.height*ratio
   const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);ctx.fillStyle='#18232e';ctx.fillRect(0,0,rect.width,rect.height)
   const [w,h]=projection.size,scale=Math.min((rect.width-24)/w,(rect.height-24)/h);box={x:(rect.width-w*scale)/2,y:(rect.height-h*scale)/2,scale,w,h}
   ctx.fillStyle='#dce1e5';for(const cell of projection.cells){const x=cell%w,y=Math.floor(cell/w);ctx.fillRect(box.x+x*scale,box.y+(view.flip?h-1-y:y)*scale,Math.max(1,scale),Math.max(1,scale))}
   const range=getRange(),a=view.axes[0],b=view.axes[1],y=view.flip?h-1-range.hi[b]:range.lo[b]
   ctx.strokeStyle='#8de5b5';ctx.fillStyle='#5cba8b44';const x=box.x+range.lo[a]*scale,top=box.y+y*scale,width=(range.hi[a]-range.lo[a]+1)*scale,height=(range.hi[b]-range.lo[b]+1)*scale
   ctx.fillRect(x,top,width,height);ctx.lineWidth=2;ctx.strokeRect(x,top,width,height)
  }
  function point(event){const rect=canvas.getBoundingClientRect();const x=Math.max(0,Math.min(box.w-1,Math.floor((event.clientX-rect.left-box.x)/box.scale))),v=Math.max(0,Math.min(box.h-1,Math.floor((event.clientY-rect.top-box.y)/box.scale)));return [x,view.flip?box.h-1-v:v]}
  function apply(event){if(!start||!box)return;const end=point(event),range=getRange();view.axes.forEach((axis,i)=>{range.lo[axis]=Math.min(start[i],end[i]);range.hi[axis]=Math.max(start[i],end[i])});setRange(range);paintAll()}
  canvas.addEventListener('pointerdown',event=>{if(event.button!==0||!box)return;start=point(event);canvas.setPointerCapture(event.pointerId);apply(event)})
  canvas.addEventListener('pointermove',event=>{if(start)apply(event)})
  canvas.addEventListener('pointerup',event=>{if(!start)return;apply(event);start=null;if(canvas.hasPointerCapture(event.pointerId))canvas.releasePointerCapture(event.pointerId);document.getElementById('settings').dispatchEvent(new Event('input',{bubbles:true}))})
  canvas.addEventListener('pointercancel',()=>start=null);painters.push(paint);new ResizeObserver(()=>{if(!dialog.hidden)paint()}).observe(canvas)
 }
 function paintAll(){painters.forEach(paint=>paint());const range=getRange();document.getElementById('orthographic-range').textContent=`起点 ${range.lo.join(', ')} → 终点 ${range.hi.join(', ')}（包含边界方块）`}
 document.getElementById('open-orthographic').addEventListener('click',()=>{if(!getInfo()?.projections){document.getElementById('open-orthographic').title='请先打开建筑';return}dialog.hidden=false;paintAll()})
 document.getElementById('close-orthographic').addEventListener('click',()=>dialog.hidden=true)
 document.getElementById('settings').addEventListener('input',()=>{if(!dialog.hidden)paintAll()})
 return {refresh:paintAll}
}
