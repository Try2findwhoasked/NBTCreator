import {floatingDetails,chevron} from './floating-panel.js'
export function initModelPicker(){
 const $=id=>document.getElementById(id),library=$('model-library'),header=library.querySelector('.section-title'),tools=$('workspace-tools'),info=$('model-info'),row=tools.querySelector('.two'),search=$('model-search').closest('label'),history=$('model-history').closest('label'),selection=$('models').closest('label')
 search.classList.add('model-picker-search');search.firstChild.textContent='';$('model-search').placeholder='搜索建筑、日期或路径';$('model-search').setAttribute('aria-label','搜索建筑');library.insertBefore(search,selection)
 const caption=[...selection.childNodes].find(node=>node.nodeType===Node.TEXT_NODE);if(caption)caption.textContent='';$('models').setAttribute('aria-label','选择建筑，自动载入')
 row.remove();const panel=document.createElement('div');panel.className='model-picker-options';panel.append($('workspace-tools-content'),history);tools.append(panel);tools.querySelector(':scope > summary').innerHTML='<span>筛选 / 工作区</span>'+chevron
 const actions=document.createElement('div');actions.className='model-picker-actions';actions.append(info,tools,$('refresh'));header.append(actions)
 const project=document.createElement('button');project.type='button';project.textContent='前往项目管理';project.onclick=()=>{window.creatorWorkspace.select('project')};const hint=document.createElement('p');hint.className='muted';hint.textContent='切换项目或打开其他 NBT，请前往项目管理。选择建筑后自动载入。';$('workspace-tools-content').append(hint,project)
 floatingDetails(tools,panel,{minimum:270})
}
