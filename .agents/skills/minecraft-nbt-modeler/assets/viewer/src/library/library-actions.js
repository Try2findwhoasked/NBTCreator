import {floatingDetails,chevron} from '../floating-panel.js'

// Move the live controls once, after the feature modules mount. Each command
// keeps its own handler, busy state and workspace permissions.
export function arrangeLibraryActions(){
 const $=id=>document.getElementById(id)
 function menu(host,id,label,groups){
  const root=document.createElement('details');root.id=id;root.className='library-filter-menu library-actions-menu'
  const summary=document.createElement('summary');summary.textContent=label;summary.insertAdjacentHTML('beforeend',chevron)
  const panel=document.createElement('div');panel.className='library-command-panel'
  for(const [title,ids] of groups){
   const section=document.createElement('section'),heading=document.createElement('strong')
   heading.textContent=title;section.append(heading)
   for(const entry of ids){
    const control=$(entry)
    if(control)section.append(control.type==='checkbox'?control.closest('label'):control)
   }
   panel.append(section)
  }
  root.append(summary,panel);host.append(root)
  const popover=floatingDetails(root,panel,{minimum:268})
  panel.addEventListener('click',event=>{
   if(event.target.closest('button')&&(event.target.closest('details')===root||event.target.id==='project-select'))popover.close()
  })
  return root
 }
 menu($('project-native-actions'),'project-library-menu','建筑库工具',[
  ['项目与方案',['project-workspace-menu','studio-project-new','architect-tools-menu']],
  ['批量处理',['project-queue-open','batch-workspaces-open']],
  ['列表显示',['project-refresh','project-generate-thumbnails','project-tree-sort-reset','project-auto-more']]
 ])
 const assets=$('asset-workspace')
 menu(assets.querySelector('.library-actions'),'asset-library-menu','素材库工具',[
  ['添加与制作',['asset-import','asset-create-agent']],
  ['素材管理',['asset-libraries-open','asset-batches-open','tool-effects-open','asset-refresh']]
 ])
 // Pattern and effect tools used to be scoped by their parent gallery.
 for(const [kind,ids] of Object.entries({patterns:['pattern-assets-import','pattern-assets-new'],effects:['effect-assets-capture']})){
  for(const id of ids)$(id).dataset.toolKind=kind
 }
 // Frequent create actions stay visible beside search for the selected edition.
 const assetToolbar=assets.querySelector('.library-toolbar')
 for(const id of ['pattern-assets-import','pattern-assets-new','effect-assets-capture'])assetToolbar.append($(id))
 const projectFilter=$('project-filter-controls'),assetFilter=$('asset-filters-menu').querySelector('.library-filter-panel')
 const quick=$('project-quick-version')
 $('project-workspace').querySelector('.library-toolbar').insertBefore(quick.closest('label'),$('project-filters-menu'))
 const assetSort=$('asset-sort'),assetReview=$('asset-review-filter')
 for(const field of [assetReview,assetSort])field.closest('label').dataset.toolKind='components'
 assetFilter.prepend(assetReview.closest('label'),assetSort.closest('label'))
 assetFilter.append($('asset-reset-view'))
 const select=$('project-select'),toolbar=$('project-workspace').querySelector('.library-toolbar')
 select.addEventListener('click',()=>{
  const active=select.getAttribute('aria-pressed')==='true'
  const compare=toolbar.querySelector('.library-compare-mode')
  if(active&&compare?.getAttribute('aria-pressed')==='true')compare.click()
 })
 projectFilter.querySelector('#project-clear').textContent='恢复默认筛选'
}
