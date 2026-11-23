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
 return args.kind!=='spectral_repeat'&&controls.style!==false&&!(args.form&&!['railing','beam','bracket','arch','frame','pedestal'].includes(args.kind))
}

export function createSpectralControls(prefix){
 const element=document.createElement('div')
 element.hidden=true
 element.innerHTML=`<label>重复周期（格）<input id="${prefix}-period" type="number" min="2" max="64" step="1" required></label>
 <label>相位偏移（格，正值沿 +X）<input id="${prefix}-phase" type="number" min="-64" max="64" step="1" required></label>`
 const [period,phase]=element.querySelectorAll('input')
 return {
  element,
  fill(args){
   element.hidden=args?.kind!=='spectral_repeat'
   period.value=args?.period??args?.spectrum?.samples??''
   phase.value=args?.phase??0
  },
  read(){
   if(!Number.isInteger(period.valueAsNumber)||period.valueAsNumber<2||period.valueAsNumber>64)throw Error('重复周期须为 2～64 格的整数')
   if(!Number.isInteger(phase.valueAsNumber)||Math.abs(phase.valueAsNumber)>64)throw Error('相位偏移须为 −64～64 格的整数')
   return {period:period.valueAsNumber,phase:phase.valueAsNumber}
  }
 }
}
