import taxonomy from '../../../config/asset-taxonomy.json' with {type:'json'}
const label=value=>value==='装饰效果'?'装饰构件':value
export function semanticTags(item){const tags=(item.tags??[]).filter(tag=>!/^\d+$/.test(tag)&&!taxonomy.generic_tags.includes(tag)&&tag!==item.name);if(tags.length)return [...new Set(tags.map(label))];return [label(taxonomy.groups.find(group=>group.words.some(word=>item.name.includes(word)))?.name??taxonomy.fallback)]}
