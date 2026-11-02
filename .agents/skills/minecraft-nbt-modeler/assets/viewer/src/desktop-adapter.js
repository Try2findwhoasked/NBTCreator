// Optional native bridge. Browser and headless skill workflows remain available.
export function initDesktop(loadSource){
 if(!window.nbtDesktop)return
 const host=document.createElement('div');host.className='two';host.id='desktop-controls'
 const workspace=document.createElement('button');workspace.type='button';workspace.textContent='选择工作区…';workspace.id='desktop-workspace'
 const source=document.createElement('button');source.type='button';source.textContent='打开 NBT / 主模型…';source.id='desktop-source'
 const info=document.createElement('p');info.className='muted';info.id='desktop-workspace-label'
 async function show(){const data=await window.nbtDesktop.info();info.textContent='工作区：'+data.workspace;info.title=data.workspace}
 workspace.onclick=async()=>{try{await window.nbtDesktop.chooseWorkspace();await show()}catch(e){info.textContent=e.message}}
 source.onclick=async()=>{try{const file=await window.nbtDesktop.chooseSource();if(file)await loadSource(file)}catch(e){info.textContent=e.message}}
 host.append(workspace,source);(document.getElementById('workspace-tools-content')??document.querySelector('.sidebar>.card')).prepend(host,info);show().catch(e=>info.textContent=e.message)
}
