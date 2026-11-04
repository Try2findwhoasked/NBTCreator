import './ui-icons.css'
const svg='<svg class="disclosure-chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="m6 4 4 4-4 4"/></svg>'
export function initDisclosureIcons(){
 const decorate=root=>{const nodes=[...(root.matches?.('summary')?[root]:[]),...(root.querySelectorAll?.('summary')??[])];for(const summary of nodes){if(summary.closest('.inline-info')||summary.querySelector('svg'))continue;summary.classList.add('has-disclosure-icon');summary.insertAdjacentHTML('afterbegin',svg)}}
 decorate(document)
 new MutationObserver(records=>{for(const record of records){if(record.target.nodeType===1&&record.target.matches('summary'))decorate(record.target);for(const node of record.addedNodes)if(node.nodeType===1)decorate(node)}}).observe(document.body,{childList:true,subtree:true})
}
