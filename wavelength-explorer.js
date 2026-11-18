(()=>{
 'use strict';
 const root=document.getElementById('wavelengths'),source=document.getElementById('wavelength-explorer-data');
 if(!root||!source)return;
 let data;try{data=JSON.parse(source.textContent)}catch{return}
 const waves=data.wavelengths,domain=data.domain_nm;
 if(!Array.isArray(waves)||!domain||domain.max<=domain.min)return;
 const get=id=>root.querySelector('#'+id),tabs=root.querySelector('.wave-tabs');if(!tabs)return;
 const buttons=[...tabs.querySelectorAll('button[data-wave]')];
 const fields=['wave-number','wave-family','wave-title','wave-description','wave-effect','wave-method','wave-engineering','spectrum-marker','spectrum-curve','spectrum-area','spectrum-guide','spectrum-peak','spectrum-peak-label','spectrum-chart-title','wave-status'];
 if(fields.some(id=>!get(id))||buttons.length!==waves.length)return;
 const content=root.querySelector('.wave-content'),visual=root.querySelector('.spectrum-visual');
 const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');let animation,visualAnimation;
 function profile(nm){
  const left=32,right=688,bottom=204,peak=62;
  const x=left+(nm-domain.min)/(domain.max-domain.min)*(right-left);
  const points=Array.from({length:281},(_,i)=>{
   const wavelength=domain.min+(domain.max-domain.min)*i/280;
   // A shared illustrative shape places a nominal wavelength; no measured width/output is implied.
   const height=Math.exp(-.5*((wavelength-nm)/18)**2);
   return [(left+i/280*(right-left)).toFixed(2),(bottom-height*(bottom-peak)).toFixed(2)].join(' ');
  });
  return{x,peak,line:'M '+points.join(' L '),area:'M '+left+' '+bottom+' L '+points.join(' L ')+' L '+right+' '+bottom+' Z'};
 }
 function select(nm,{focus=false,announce=true}={}){
  const wave=waves.find(item=>item.nm===nm);if(!wave)return false;
  const changed=Number(root.dataset.activeWavelength)!==nm;
  root.dataset.activeWavelength=String(nm);root.style.setProperty('--wave',wave.color);visual.style.setProperty('--wave',wave.color);
  buttons.forEach(button=>{const selected=Number(button.dataset.wave)===nm;button.setAttribute('aria-pressed',String(selected));button.tabIndex=selected?0:-1;if(selected&&focus)button.focus()});
  get('wave-number').replaceChildren(document.createTextNode(nm+' '),Object.assign(document.createElement('small'),{textContent:'nm'}));
  get('wave-family').textContent=wave.family;get('wave-title').textContent=wave.title;
  get('wave-description').textContent=nm<700?'Visible spectrum · explore application and engineering considerations.':'Invisible spectrum · shown in illustrative color for navigation.';
  get('wave-effect').textContent=wave.research_context;get('wave-method').textContent=wave.use_considerations;get('wave-engineering').textContent=wave.oem_considerations;
  const curve=profile(nm);get('spectrum-curve').setAttribute('d',curve.line);get('spectrum-area').setAttribute('d',curve.area);
  get('spectrum-guide').setAttribute('x1',curve.x);get('spectrum-guide').setAttribute('x2',curve.x);
  get('spectrum-peak').setAttribute('cx',curve.x);get('spectrum-peak').setAttribute('cy',curve.peak);
  const label=get('spectrum-peak-label');label.setAttribute('x',curve.x<80?curve.x+12:curve.x>640?curve.x-12:curve.x);label.setAttribute('text-anchor',curve.x<80?'start':curve.x>640?'end':'middle');label.textContent=nm+' nm';
  get('spectrum-chart-title').textContent=nm+' nm nominal wavelength position — illustrative curve, not a measured spectrum';
  get('spectrum-marker').style.left=((nm-domain.min)/(domain.max-domain.min)*100)+'%';
  const added=get('wave-added');if(added)added.textContent='';
  if(announce)get('wave-status').textContent=nm+' nm selected. '+wave.family+'. Illustrative profile and development notes updated.';
  if(changed&&!reduced.matches&&typeof content.animate==='function'){
   animation?.cancel();animation=content.animate([{opacity:.35,transform:'translateY(5px)'},{opacity:1,transform:'translateY(0)'}],{duration:180,easing:'ease-out'});
   if(typeof visual.animate==='function'){visualAnimation?.cancel();visualAnimation=visual.animate([{opacity:.5},{opacity:1}],{duration:180,easing:'ease-out'})}
  }
  visual.dataset.wavelength=String(nm);return true;
 }
 tabs.addEventListener('click',event=>{const button=event.target.closest('button[data-wave]');if(button&&tabs.contains(button))select(Number(button.dataset.wave))});
 tabs.addEventListener('keydown',event=>{
  const current=event.target.closest('button[data-wave]');if(!current)return;
  const index=buttons.indexOf(current);let next;
  if(event.key==='ArrowRight')next=(index+1)%buttons.length;
  else if(event.key==='ArrowLeft')next=(index-1+buttons.length)%buttons.length;
  else if(event.key==='Home')next=0;else if(event.key==='End')next=buttons.length-1;else return;
  event.preventDefault();select(Number(buttons[next].dataset.wave),{focus:true});
 });
 reduced.addEventListener('change',()=>{if(reduced.matches){animation?.cancel();visualAnimation?.cancel()}});
 select(Number(root.dataset.activeWavelength)||data.default_nm,{announce:false});
 root.dataset.explorerReady='true';
})();
