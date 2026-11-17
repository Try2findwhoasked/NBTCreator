export function recipeSpacingTarget(args, controls={}){
 if(controls.spacing===false)return null
 const {kind,form}=args
 const stepped=args.style==='stepped'
 if(form?.handrail)return ['form','handrail','post_spacing']
 if(kind==='pillar')return form?.band_spacing?['form','band_spacing']:null
 if(kind==='wall'&&form)return ['form','panel_pitch']
 if(kind==='ceiling'&&form)return ['form','pitch']
 if(kind==='railing'&&form?.profile!=='lattice')return ['form','pitch']
 if(kind==='beam'&&(form?.profile??(stepped?'coffered':'solid'))!=='solid')return ['form','pitch']
 if(kind==='bracket'&&(form?.profile??(stepped?'curved':'stepped'))==='stepped')return ['form','pitch']
 if(kind==='frame'&&form?.profile==='mullioned')return ['form','pitch']
 if(kind==='pedestal'&&(form?.profile??(stepped?'stepped':'square'))==='stepped')return ['form','pitch']
 return ['wall','ceiling','shelf','planter'].includes(kind)&&!form?['spacing']:null
}

export function recipeHasStyle(args, controls={}){
 return controls.style!==false&&!(args.form&&!['railing','beam','bracket','arch','frame','pedestal'].includes(args.kind))
}
