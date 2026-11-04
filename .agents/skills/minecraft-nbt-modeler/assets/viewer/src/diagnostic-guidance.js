import './diagnostic-guidance.css'
const element=(tag,text)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node}

// Locations come from explicit engine evidence; never parse coordinates from error prose.
export function renderDiagnostics(host,diagnostics,{focus,isCurrent=()=>true,status=()=>{}}={}){
 host.replaceChildren();if(!diagnostics?.issues?.length){host.hidden=true;return}host.hidden=false
 host.append(element('h4','问题解释与调整方向'))
 for(const issue of diagnostics.issues){const card=element('article');card.className='diagnostic-card';card.dataset.diagnosticCode=issue.code;card.append(element('strong',issue.title),element('small',({observed:'来自实际检查证据',incomplete:'检查不完整，不能直接断言不通',unknown:'尚未支持，结论不确定'})[issue.certainty]??'报告解释'),element('p',issue.explanation));const steps=element('ul');for(const line of issue.suggestions??[])steps.append(element('li',line));card.append(steps)
  if(issue.evidence?.error){const details=element('details');details.append(element('summary','原始检查原因'),element('pre',issue.evidence.error));card.append(details)}
  const controls=element('div');controls.className='diagnostic-actions'
  if(issue.bounds&&focus){const button=element('button','定位此问题');button.type='button';button.onclick=async()=>{try{if(!isCurrent())throw Error('画面或参数已变化，请重新检查');await focus(issue.bounds,issue);status('已定位“'+issue.title+'”；仅改变观察位置，未修改建筑。')}catch(error){status(error.message,true)}};controls.append(button)}
  const copy=element('button','复制检查证据');copy.type='button';copy.onclick=async()=>{try{const text=JSON.stringify({source_sha256:diagnostics.source_sha256,geometry_sha256:diagnostics.geometry_sha256,context_sha256:diagnostics.context_sha256,issue,notice:'只读检查证据与建议，不表示已修复或获批准；修改前核对当前源。'},null,2);if(window.nbtDesktop?.copyAgentPlan)await window.nbtDesktop.copyAgentPlan(text);else await navigator.clipboard.writeText(text);status('检查证据与调整方向已复制，可交给 Agent 核对。')}catch(error){status(error.message,true)}};controls.append(copy);card.append(controls);host.append(card)
 }
 host.append(element('p','建议不会自动修改建筑或放宽保护。调整后须重新检查，并按需要完成游戏内验收。'))
}
