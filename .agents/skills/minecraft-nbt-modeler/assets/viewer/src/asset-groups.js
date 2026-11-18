export function initAssetGroups({host,api}){
 let data={revision:0,groups:[],assignments:{}},active=false,saving=Promise.resolve()
 const selected=new Set(),matching=new Map()
 const button=document.createElement('button');button.id='asset-groups-toggle';button.type='button';button.textContent='整理';host.querySelector('.library-actions').prepend(button)
 const panel=document.createElement('section');panel.id='asset-groups-panel';panel.hidden=true;panel.setAttribute('aria-label','素材文件夹管理')
 panel.innerHTML='<label>文件夹名称<input id="asset-group-name" maxlength="60" placeholder="例如：门窗、墙面或地面"></label><button id="asset-group-create" type="button">新建文件夹</button><label>当前文件夹<select id="asset-group-current"></select></label><button id="asset-group-rename" type="button">重命名</button><button id="asset-group-delete" type="button">移除文件夹</button><span id="asset-group-selection" role="status"></span><button id="asset-group-move" type="button">将所选移入文件夹</button><button id="asset-group-done" type="button">完成</button>'
 host.querySelector('.library-toolbar').after(panel)
 const $=id=>panel.querySelector('#'+id),kind=()=>host.dataset.kind||'components',key=(type,id)=>type+':'+id
 function report(message){$('asset-group-selection').textContent=message}
 const selectAll=document.createElement('button');selectAll.type='button';selectAll.id='asset-group-select-all';selectAll.textContent='选择全部';selectAll.title='选择当前筛选结果中的全部素材';$('asset-group-move').before(selectAll)
 const changed=()=>window.dispatchEvent(new Event('creator-asset-groups-change'))
 function syncSelection(){selectAll.disabled=!(matching.get(kind())??[]).some(id=>!selected.has(id));$('asset-group-move').disabled=!selected.size}
 function selectionCount(){syncSelection();report(`已选 ${selected.size} 项`)}
 function render(){const groups=data.groups.filter(group=>group.kind===kind()),select=$('asset-group-current'),previous=select.value;select.replaceChildren(new Option('未归组',''),...groups.map(group=>new Option(group.name,group.id)));if(groups.some(group=>group.id===previous))select.value=previous;syncSelection();$('asset-group-rename').disabled=$('asset-group-delete').disabled=!groups.length;button.setAttribute('aria-pressed',String(active));panel.hidden=!active;if(!selected.size)report('勾选列表中的素材后可批量移动。')}
 selectAll.onclick=()=>{for(const id of matching.get(kind())??[])selected.add(id);selectionCount();changed()}
 async function load(){data=await api('asset-groups');render();window.dispatchEvent(new Event('creator-asset-groups-change'))}
 function mutate(change){const operation=saving.catch(()=>{}).then(async()=>{const next=structuredClone(data);change(next);data=await api('asset-groups',next);render();window.dispatchEvent(new Event('creator-asset-groups-change'));return true});saving=operation;return operation.catch(error=>{report(error.message);return false})}
 button.onclick=()=>{active=!active;selected.clear();render();window.dispatchEvent(new Event('creator-asset-groups-change'))}
 $('asset-group-done').onclick=()=>{active=false;selected.clear();render();window.dispatchEvent(new Event('creator-asset-groups-change'))}
 $('asset-group-create').onclick=()=>{const name=$('asset-group-name').value.trim();if(!name){report('请填写文件夹名称');return}mutate(next=>{next.groups.push({id:crypto.randomUUID(),kind:kind(),name})}).then(saved=>{if(saved)$('asset-group-name').value=''})}
 $('asset-group-rename').onclick=()=>{const id=$('asset-group-current').value,name=$('asset-group-name').value.trim();if(!id||!name){report('先选择文件夹并填写新名称');return}mutate(next=>{next.groups.find(group=>group.id===id).name=name})}
 $('asset-group-delete').onclick=()=>{const id=$('asset-group-current').value;if(!id){report('先选择要移除的文件夹');return}mutate(next=>{next.groups=next.groups.filter(group=>group.id!==id);for(const [item,group]of Object.entries(next.assignments))if(group===id)delete next.assignments[item]})}
 $('asset-group-move').onclick=()=>{const id=$('asset-group-current').value,ids=[...selected],type=kind();mutate(next=>{for(const item of ids){const target=key(type,item);if(id)next.assignments[target]=id;else delete next.assignments[target]}}).then(saved=>{if(saved){selected.clear();render();window.dispatchEvent(new Event('creator-asset-groups-change'));report(`已整理 ${ids.length} 项素材`)}})}
 function decorate(article,type,id){if(!active||type!==kind())return;const label=document.createElement('label');label.className='asset-group-select';const input=document.createElement('input');input.type='checkbox';input.checked=selected.has(id);input.setAttribute('aria-label','选择素材以移动文件夹');input.onclick=event=>event.stopPropagation();input.onchange=()=>{if(input.checked)selected.add(id);else selected.delete(id);selectionCount()};label.append(input);article.append(label)}
 window.addEventListener('creator-workspace-change',event=>{if(event.detail==='assets')load().catch(error=>report(error.message))})
 load().catch(error=>report(error.message))
 return {groups:type=>data.groups.filter(group=>group.kind===type),assignment:(type,id)=>data.assignments[key(type,id)]??'',setVisible(type,items){matching.set(type,items.map(item=>item.id));if(type===kind())syncSelection()},decorate,clearSelection(){selected.clear();render()},get active(){return active}}
}
