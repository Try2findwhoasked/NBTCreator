export async function positionComponent(page, xyz, adjust) {
 const panel=page.locator('#component-editor')
 await panel.waitFor()
 const advanced=panel.locator('.transform-advanced')
 if(!await advanced.evaluate(element=>element.open))await advanced.locator('summary').click()
 if(adjust)await adjust(panel)
 await panel.evaluate((element,position)=>{
  const axes=['x','y','z']
  for(const [i,axis] of axes.entries())element.querySelector('#component-transform-'+axis).value=position[i]
  element.querySelector('#component-transform-z').dispatchEvent(new Event('change',{bubbles:true}))
 },xyz)
}

export async function confirmComponent(page) {
 const confirm=page.locator('#component-transform-apply')
 await confirm.click()
 await page.locator('#component-editor').waitFor({state:'hidden'})
}
