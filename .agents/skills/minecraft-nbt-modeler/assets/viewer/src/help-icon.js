import './help-icon.css'

// Draw the enclosing circle inside the icon, leaving the click target borderless.
export function decorateHelpButtons(root=document){
 for(const button of root.querySelectorAll('.inline-info > summary, #review-help-open, [data-help-icon]')){
  button.classList.add('help-icon-trigger')
  const icon=document.createElementNS('http://www.w3.org/2000/svg','svg')
  icon.setAttribute('viewBox','0 0 20 20');icon.setAttribute('aria-hidden','true');icon.setAttribute('focusable','false')
  const circle=document.createElementNS('http://www.w3.org/2000/svg','circle');circle.setAttribute('cx','10');circle.setAttribute('cy','10');circle.setAttribute('r','8')
  const path=document.createElementNS('http://www.w3.org/2000/svg','path');path.setAttribute('d','M10 9v4.5')
  const dot=document.createElementNS('http://www.w3.org/2000/svg','path');dot.setAttribute('d','M10 6.3h.01');dot.setAttribute('stroke-width','2.2')
  icon.append(circle,path,dot);button.replaceChildren(icon)
 }
}
