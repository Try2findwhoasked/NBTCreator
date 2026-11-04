import taxonomy from '../../../config/asset-taxonomy.json' with {type:'json'}
export function semanticTags(item){const tags=(item.tags??[]).filter(tag=>!/^\d+$/.test(tag)&&!taxonomy.generic_tags.includes(tag)&&tag!==item.name);if(tags.length)return [...new Set(tags)];return [taxonomy.groups.find(group=>group.words.some(word=>item.name.includes(word)))?.name??taxonomy.fallback]}
