// Lodestone's idle-only yield can remain pending in a minimized/occluded window.
// Keep its time-sliced mesh construction, but give each yield a timer fallback.
export function yieldForMeshBuild(host=globalThis){
 return new Promise(resolve=>{
  let idle,timer,done=false
  const finish=()=>{if(done)return;done=true;if(timer!==undefined)host.clearTimeout(timer);if(idle!==undefined)host.cancelIdleCallback?.(idle);resolve()}
  timer=host.setTimeout(finish,0)
  try{if(typeof host.requestIdleCallback==='function')idle=host.requestIdleCallback(finish,{timeout:32})}catch{/* The independent timer still completes the yield. */}
 })
}

export function installMeshScheduling(Renderer,Builder){
 // Scope the compatibility fix to our pinned renderer, never the global browser
 // scheduling functions. Install before construction, which starts a mesh build.
 for(const Constructor of [Renderer,Builder]){
  if(typeof Constructor?.prototype?.yieldControl!=='function')throw Error('渲染器版本不支持分片调度，请检查已锁定的依赖')
  Constructor.prototype.yieldControl=function(){return yieldForMeshBuild()}
 }
}
