import './axis-navigation.css'

const dot=(a,b)=>a.reduce((sum,n,i)=>sum+n*b[i],0),sub=(a,b)=>a.map((n,i)=>n-b[i])
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
const unit=a=>{const length=Math.hypot(...a);if(!Number.isFinite(length)||length<1e-8)throw Error('视角方向无效');return a.map(n=>n/length)}
const vectors={x:[1,0,0],y:[0,1,0],z:[0,0,1]}
export function axisCamera(view,axis,sign=1){
 if(!Object.hasOwn(vectors,axis)||![1,-1].includes(sign))throw Error('无效的 XYZ 观察方向')
 const distance=Math.hypot(...sub(view.eye,view.target));if(!Number.isFinite(distance)||distance<1e-8)throw Error('观察点与相机位置重合')
 return {eye:view.target.map((n,i)=>n+vectors[axis][i]*distance*sign),target:[...view.target],up:axis==='y'?[0,0,-sign]:[0,1,0],fov:view.fov}
}
export function projectedAxes(view){
 const forward=unit(sub(view.target,view.eye)),right=unit(cross(forward,view.up??[0,1,0])),up=unit(cross(right,forward))
 return Object.entries(vectors).map(([axis,direction])=>({axis,x:42+dot(direction,right)*26,y:37-dot(direction,up)*26,depth:dot(direction,forward)}))
}
export function createAxisNavigation({select}){
 const root=document.createElement('aside');root.id='axis-navigation';root.setAttribute('aria-label','XYZ 观察方向');root.innerHTML='<svg viewBox="0 0 84 72" aria-hidden="true"></svg><div class="axis-directions" role="group" aria-label="沿坐标轴观察"></div>'
 const svg=root.querySelector('svg'),ns='http://www.w3.org/2000/svg',handles=new Map()
 for(const axis of Object.keys(vectors)){
  const group=document.createElementNS(ns,'g');group.classList.add('axis-'+axis)
  const line=document.createElementNS(ns,'line');line.setAttribute('x1','42');line.setAttribute('y1','37')
  const circle=document.createElementNS(ns,'circle');circle.setAttribute('r','9');const text=document.createElementNS(ns,'text');text.textContent=axis.toUpperCase();group.append(line,circle,text);svg.append(group);handles.set(axis,{group,line,circle,text})
 }
 const origin=document.createElementNS(ns,'circle');origin.setAttribute('cx','42');origin.setAttribute('cy','37');origin.setAttribute('r','2');origin.classList.add('axis-origin');svg.prepend(origin)
 const buttons=[]
 for(const sign of [1,-1])for(const axis of Object.keys(vectors)){
  const button=document.createElement('button');button.type='button';button.dataset.viewAxis=axis;button.dataset.viewSign=String(sign);button.className='axis-'+axis;button.textContent=(sign===1?'+':'−')+axis.toUpperCase();button.title='从 '+(sign===1?'+':'−')+axis.toUpperCase()+' 方向观察'+(axis==='y'?(sign===1?'（俯视）':'（仰视）'):'');button.setAttribute('aria-label',button.title);button.setAttribute('aria-pressed','false');button.onclick=()=>select(axis,sign);root.querySelector('.axis-directions').append(button);buttons.push(button)
 }
 document.body.append(root)
 return {update(view){const projected=projectedAxes(view).sort((a,b)=>b.depth-a.depth);for(const {axis,x,y,depth}of projected){const h=handles.get(axis);h.line.setAttribute('x2',x);h.line.setAttribute('y2',y);h.circle.setAttribute('cx',x);h.circle.setAttribute('cy',y);h.text.setAttribute('x',x);h.text.setAttribute('y',y);h.group.style.opacity=depth>.1?'.6':'1';svg.append(h.group)}const direction=unit(sub(view.eye,view.target));for(const button of buttons)button.setAttribute('aria-pressed',String(dot(direction,vectors[button.dataset.viewAxis])*Number(button.dataset.viewSign)>.9999))},root}
}
