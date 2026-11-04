// Keep precise numeric entry and accessible native sliders in sync.
export function linkRange(number,range,limits,onSlide=()=>{}){
 function sync(){const [min,max]=limits();range.min=min;range.max=max;range.step=number.step||1;range.value=number.value;range.disabled=number.disabled||max<min}
 number.addEventListener('input',sync);number.addEventListener('change',sync)
 range.addEventListener('input',()=>{number.value=range.value;number.dispatchEvent(new Event('input',{bubbles:true}));onSlide()})
 sync();return sync
}
