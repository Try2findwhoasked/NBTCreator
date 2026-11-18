export function mountRoomMigration(host,bridge){
 if(!bridge.migrationRun)return
 const panel=document.createElement('fieldset')
 panel.innerHTML='<legend>旧项目迁移</legend><p>预检旧目录，将约束和房间迁移到新工作区副本。</p><div class="note-actions"><button type="button" data-action="source">选择旧工作区</button><button type="button" data-action="target">选择副本位置</button></div><p class="path" data-path="source"></p><p class="path" data-path="target"></p><div class="note-actions"><button type="button" data-action="download">下载工具并预检</button><button type="button" data-action="local">使用随附工具预检</button></div><p role="status" data-migration-status></p><details hidden><summary>房间归属确认</summary><div data-rooms></div></details><div class="note-actions"><button type="button" data-action="apply" hidden>开始迁移到副本</button><button type="button" data-action="open" hidden>打开迁移后的工作区</button></div>'
 host.append(panel)
 const button=action=>panel.querySelector('[data-action='+action+']'),status=panel.querySelector('[data-migration-status]'),details=panel.querySelector('details')
 let source='',target='',plan=null,busy=false,verified=false
 function sync(){
  button('source').disabled=busy;button('target').disabled=busy||!source
  for(const key of ['download','local'])button(key).disabled=busy||!target
  button('apply').hidden=!plan||verified;button('apply').disabled=busy
  button('open').hidden=!verified;button('open').disabled=busy
  for(const select of details.querySelectorAll('select'))select.disabled=busy||verified
 }
 const action=run=>async()=>{
  if(busy)return
  busy=true;sync()
  try{await run()}catch(error){status.textContent=error.message}
  finally{busy=false;sync()}
 }
 for(const side of ['source','target'])button(side).onclick=action(async()=>{
  const selected=await bridge.migrationSelect(side)
  if(!selected)return
  ;({source,target}=selected)
  for(const key of ['source','target'])panel.querySelector('[data-path='+key+']').textContent=selected[key]
  plan=null;verified=false;details.hidden=true;status.textContent=''
 })
 for(const key of ['download','local'])button(key).onclick=action(async()=>{
  plan=null;verified=false;details.hidden=true;status.textContent=key==='download'?'正在获取工具并预检…':'正在预检…'
  plan=await bridge.migrationRun('plan',{download:key==='download'})
  const byProject=new Map()
  for(const rule of plan.constraints){
   if(!byProject.has(rule.project))byProject.set(rule.project,[])
   byProject.get(rule.project).push(rule)
  }
  const rows=document.createDocumentFragment()
  for(const room of plan.rooms){
   const label=document.createElement('label');label.textContent=room.name+(room.suggestions.length?' · 有历史引用建议':'')
   const select=document.createElement('select');select.dataset.room=room.id
   select.append(new Option('未归组',''),...(byProject.get(room.project)??[]).map(rule=>new Option(rule.name+(room.suggestions.includes(rule.id)?'（建议）':''),rule.id)))
   label.append(select);rows.append(label)
  }
  details.querySelector('[data-rooms]').replaceChildren(rows);details.hidden=!plan.rooms.length
  status.textContent=`预检完成 · ${plan.constraints.length} 条约束 · ${plan.rooms.length} 间房 · ${plan.count} 个文件 · ${(plan.bytes/1048576).toFixed(1)} MiB`
 })
 button('apply').onclick=action(async()=>{
  const owners=Object.fromEntries([...details.querySelectorAll('select')].map(select=>[select.dataset.room,select.value||null]))
  status.textContent='正在复制和验证文件…'
  const result=await bridge.migrationRun('apply',{owners})
  verified=result.passed===true
  status.textContent=`迁移验证完成 · ${result.rooms} 间房 · ${result.files} 个源文件`
 })
 button('open').onclick=action(async()=>{
  status.textContent='正在打开迁移后的工作区…'
  if(!await bridge.migrationOpen())status.textContent='迁移副本已验证。当前仍在原工作区。'
 })
 sync()
}
