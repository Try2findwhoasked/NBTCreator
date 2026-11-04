import './library-browser.css'
import {floatingDetails,chevron} from './floating-panel.js'

// Shared chrome keeps both libraries aligned. Existing controls retain their IDs and handlers.
export function initLibraryBrowser({host,prefix,title,description,search,refresh,actions,filters,tree,main,count,breadcrumb,loading}){
 host.classList.add('library-browser')
 main.querySelector('#'+prefix+'-grid')?.classList.add('project-grid')
 const header=document.createElement('header');header.className='library-heading'
 const heading=document.createElement('div');heading.className='library-heading-title';const name=document.createElement('h1');name.textContent=title
 const help=document.createElement('details');help.className='inline-info';const summary=document.createElement('summary');summary.textContent='i';summary.setAttribute('aria-label',title+'使用说明');summary.title=title+'使用说明';const content=document.createElement('div');content.className='info-popover';const text=document.createElement('p');text.textContent=description;content.append(text);help.append(summary,content);heading.append(name,help)
 actions.classList.add('library-actions');header.append(heading,actions)
 const toolbar=document.createElement('div');toolbar.className='library-toolbar';const searchBox=document.createElement('div');searchBox.className='library-search';searchBox.innerHTML='<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5"/><path d="m13 13 4 4"/></svg>';search.setAttribute('aria-label',search.getAttribute('aria-label')||'搜索'+title);searchBox.append(search)
 const filter=document.createElement('details');filter.id=prefix+'-filters-menu';filter.className='library-filter-menu';const toggle=document.createElement('summary');toggle.innerHTML='<span>筛选</span>'+chevron;toggle.setAttribute('aria-label',title+'筛选条件');const panel=document.createElement('div');panel.className='library-filter-panel';panel.append(filters);filter.append(toggle,panel)
 const meta=document.createElement('div');meta.className='library-meta';meta.append(count,breadcrumb);if(loading)meta.append(loading)
 toolbar.append(searchBox,filter,refresh);const spacer=document.createElement('div');spacer.className='library-toolbar-spacer';toolbar.append(spacer)
 const body=document.createElement('div');body.className='library-layout';tree.classList.add('library-tree');main.classList.add('library-main');main.prepend(meta);body.append(tree,main)
 host.replaceChildren(header,toolbar,body);floatingDetails(filter,panel,{minimum:Math.min(600,innerWidth-24)})
 return {header,toolbar,body,main,filters:filter,help:content}
}
export function createLibraryTreeRow({label,level=0,folder=false,count='',expanded}){
 const row=document.createElement('div');row.className='project-tree-row';row.style.setProperty('--level',level);row.setAttribute('role','treeitem');row.setAttribute('aria-level',String(level+1));row.tabIndex=-1
 const toggle=document.createElement('button');toggle.type='button';toggle.tabIndex=-1;toggle.className='project-tree-toggle';toggle.innerHTML=expanded===undefined?'':'<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m6 4 4 4-4 4"/></svg>';toggle.disabled=expanded===undefined;toggle.setAttribute('aria-label',(expanded?'收起':'展开')+label);if(expanded!==undefined)row.setAttribute('aria-expanded',String(expanded))
 const icon=document.createElement('span');icon.className='project-tree-icon';icon.innerHTML=folder?'<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M2.5 5.5h5l2 2h8v8h-15z"/></svg>':'<svg viewBox="0 0 20 20" aria-hidden="true"><path d="m10 2 7 4v8l-7 4-7-4V6zm0 0v8m-7-4 7 4 7-4m-7 4v8"/></svg>'
 const button=document.createElement('button');button.className='project-tree-label';button.type='button';button.tabIndex=-1;button.textContent=label
 const total=document.createElement('span');total.className='project-tree-count';total.textContent=count;row.append(toggle,icon,button,total);return {row,toggle,button}
}
