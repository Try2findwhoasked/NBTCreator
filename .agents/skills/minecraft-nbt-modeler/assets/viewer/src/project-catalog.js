const versionCache=new WeakMap()
function versionInfo(model){
 if(versionCache.has(model))return versionCache.get(model)
 const text=[model.version,...(model.relative_path||'').split(/[\\/]/).filter(part=>/^(?:v\d|v_|refined_|detail_)/i.test(part))].join(' ')
 const dates=[...text.matchAll(/(20\d{2})[-_](\d{2})[-_](\d{2})(?:[_T -](\d{2})(\d{2})(\d{2}))?/g)].map(m=>Number(m.slice(1).map(v=>v||'00').join('')))
 const revisions=[...text.matchAll(/(?:^|[\s/_-])(?:refined_v|detail_v|draft|v)(\d+)([a-z]?)(?=$|[\s/_.-])/gi)].map(m=>[Number(m[1]),m[2]?.toLowerCase().charCodeAt(0)||0]).sort((a,b)=>b[0]-a[0]||b[1]-a[1])
 const result={date:Math.max(0,...dates),revision:revisions[0]?.[0]||0,suffix:revisions[0]?.[1]||0};versionCache.set(model,result);return result
}
function compareVersions(a,b){
 for(const key of ['unreadable','is_delivery','intermediate']){const difference=Number(!a[key])-Number(!b[key]);if(difference)return difference}
 const x=versionInfo(a),y=versionInfo(b)
 if(x.date&&y.date&&x.date!==y.date)return x.date-y.date
 if(x.date&&y.date||!x.date&&!y.date&&x.revision&&y.revision){if(x.revision!==y.revision)return x.revision-y.revision;if(x.suffix!==y.suffix)return x.suffix-y.suffix}
 if(a.version===b.version){const format=Number(a.source.endsWith('.json.gz'))-Number(b.source.endsWith('.json.gz'));if(format)return format}
 let modifiedA=0n,modifiedB=0n;try{modifiedA=BigInt(a.modified_ns??0)}catch{}try{modifiedB=BigInt(b.modified_ns??0)}catch{}return modifiedA<modifiedB?-1:modifiedA>modifiedB?1:0
}
export function latestSources(models){
 const groups=new Map()
 for(const item of models){
  const key=item.object_key||item.group||item.source,previous=groups.get(key)
  if(!previous||compareVersions(item,previous)>0)groups.set(key,item)
 }
 return new Set([...groups.values()].map(item=>item.source))
}

export function projectStage(item){
 if(['unrefined','refined','finalized','discarded'].includes(item.stage))return item.stage
 return /(?:^|[\\/])(?:refined(?:[_-]v?\d+)?|detail_v\d+)(?:[\\/]|$)/i.test(item.relative_path||'')?'refined':'unrefined'
}
const values=value=>Array.isArray(value)?value:[value]
const matches=(value,actual,all='*')=>values(value).includes(all)||values(value).includes(actual)
export const DEFAULT_PROJECT_STAGES=['unrefined','refined','finalized']
export const includesDiscarded=stage=>values(stage).some(value=>value==='all'||value==='discarded')
export function filterProjects(models,{project='*',shape='*',object='',version='latest',readability='all',stage=DEFAULT_PROJECT_STAGES,query=''}={},latest=latestSources(includesDiscarded(stage)?models:models.filter(item=>projectStage(item)!=='discarded'))){
 const text=query.trim().toLocaleLowerCase()
 return models.filter(item=>{
  const isLatest=latest.has(item.source)
  return matches(project,item.project_key)&&matches(shape,item.shape_group)&&(!object||(item.object_key||item.group||item.source)===object)
   &&values(version).some(value=>value==='all'||value==='latest'&&isLatest||value==='older'&&!isLatest||value==='intermediate'&&item.intermediate)
   &&values(readability).some(value=>value==='all'||value==='readable'&&!item.unreadable&&!item.unverified||value==='unreadable'&&item.unreadable||value==='unverified'&&item.unverified)
   &&matches(stage,projectStage(item),'all')
   &&(!text||[item.label,item.name_zh,item.name,item.project_name,item.shape_group_zh,item.version,item.relative_path,item.source].join(' ').toLocaleLowerCase().includes(text))
 })
}
