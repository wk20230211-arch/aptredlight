(()=>{
 // Keep authored language routes: untranslated pages intentionally lead to a locale home.
 const languageStates=[];
 const languageHover=window.matchMedia('(min-width: 981px) and (hover: hover) and (pointer: fine)');
 function languageRoute(value){
  let target;try{target=new URL(value,location.origin)}catch{return null}
  if(target.origin!==location.origin||!['http:','https:'].includes(target.protocol))return null;
  if(!target.search)target.search=location.search;
  if(!target.hash)target.hash=location.hash;
  // Localized home pages use #products for the collection, rather than #collection.
  if(/^\/(de|fr|es|zh-CN)\/$/.test(target.pathname)&&target.hash==='#collection')target.hash='#products';
  return target.pathname+target.search+target.hash;
 }
 function refreshLanguageLinks(state){state.routes.forEach(({link,value})=>{const href=languageRoute(value);if(href)link.setAttribute('href',href)})}
 function prepareLanguageOpen(state){
  languageStates.forEach(other=>{if(other!==state)setLanguageOpen(other,false)});
  document.querySelectorAll('.journal-header details').forEach(group=>{group.open=false;group.querySelector('summary')?.setAttribute('aria-expanded','false')});
  refreshLanguageLinks(state);
 }
 function setLanguageOpen(state,open){
  clearTimeout(state.timer);if(open)prepareLanguageOpen(state);
  state.details.open=open;state.summary.setAttribute('aria-expanded',String(open));
 }
 document.querySelectorAll('[data-language-switch]').forEach((select,index)=>{
  select.addEventListener('change',()=>{const href=languageRoute(select.value);if(href)location.assign(href)});
  if(!select.closest('.global-bar')||select.dataset.languageEnhanced)return;
  const options=[...select.options].filter(option=>!option.disabled&&languageRoute(option.value));
  if(options.length<2)return;
  const selected=options.find(option=>option.selected)||options[0];
  const name=selected.label||selected.textContent;
  const label=select.getAttribute('aria-label')||'Choose website language';
  const details=document.createElement('details');details.className='language-menu';
  const summary=document.createElement('summary');summary.setAttribute('aria-label',label+': '+name);summary.setAttribute('aria-expanded','false');
  const symbol=document.createElement('span');symbol.setAttribute('aria-hidden','true');symbol.textContent='◎';
  const current=document.createElement('span');current.textContent=name;summary.append(symbol,current);
  const panel=document.createElement('nav');panel.className='language-menu-panel';panel.id='apt-language-options-'+(index+1);panel.setAttribute('aria-label',label);summary.setAttribute('aria-controls',panel.id);
  const state={details,summary,panel,routes:[],hovered:false,timer:null};
  options.forEach(option=>{
   const link=document.createElement('a');link.textContent=option.label||option.textContent;
   const lang=option.getAttribute('lang');if(lang){link.setAttribute('lang',lang);link.setAttribute('hreflang',lang)}
   if(option===selected)link.setAttribute('aria-current','true');
   state.routes.push({link,value:option.value});
   link.addEventListener('click',()=>{refreshLanguageLinks(state);setLanguageOpen(state,false)});
   panel.append(link);
  });
  details.append(summary,panel);refreshLanguageLinks(state);
  const fallback=select.closest('label')||select;fallback.after(details);fallback.classList.add('language-select-fallback');fallback.hidden=true;select.dataset.languageEnhanced='true';
  languageStates.push(state);
  // Prepare native activation before its default action. Queued toggle events only
  // reflect state, so an old language toggle cannot reopen over a newer nav intent.
  summary.addEventListener('click',()=>{if(!details.open)prepareLanguageOpen(state)});
  details.addEventListener('toggle',()=>summary.setAttribute('aria-expanded',String(details.open)));
  details.addEventListener('pointerenter',event=>{
   if(!languageHover.matches||event.pointerType==='touch')return;
   state.hovered=true;setLanguageOpen(state,true);
  });
  details.addEventListener('pointerleave',()=>{
   state.hovered=false;clearTimeout(state.timer);if(!languageHover.matches)return;
   state.timer=setTimeout(()=>{if(!state.hovered&&!details.contains(document.activeElement))setLanguageOpen(state,false)},160);
  });
  details.addEventListener('focusout',()=>{
   clearTimeout(state.timer);state.timer=setTimeout(()=>{if(!state.hovered&&!details.contains(document.activeElement))setLanguageOpen(state,false)},0);
  });
  details.addEventListener('keydown',event=>{
   if(event.key==='Escape'&&details.open){event.preventDefault();event.stopPropagation();setLanguageOpen(state,false);summary.focus();return}
   const keys=['ArrowDown','ArrowUp','Home','End'];if(!keys.includes(event.key))return;
   const links=state.routes.map(route=>route.link),at=links.indexOf(document.activeElement);
   if(document.activeElement!==summary&&at===-1)return;
   event.preventDefault();setLanguageOpen(state,true);
   const next=event.key==='Home'?0:event.key==='End'?links.length-1:event.key==='ArrowDown'?(at+1)%links.length:at<0?links.length-1:(at-1+links.length)%links.length;
   links[next].focus();
  });
 });
 if(languageStates.length){
  document.querySelectorAll('.journal-header details').forEach(group=>group.addEventListener('toggle',()=>{if(group.open)languageStates.forEach(state=>setLanguageOpen(state,false))}));
  document.addEventListener('click',event=>languageStates.forEach(state=>{if(!state.details.contains(event.target))setLanguageOpen(state,false)}));
  document.addEventListener('keydown',event=>{if(event.key==='Escape'){const state=languageStates.find(item=>item.details.open);if(state){event.preventDefault();setLanguageOpen(state,false);state.summary.focus()}}});
  languageHover.addEventListener('change',()=>languageStates.forEach(state=>{state.hovered=false;setLanguageOpen(state,false)}));
  ['hashchange','popstate'].forEach(type=>window.addEventListener(type,()=>languageStates.forEach(refreshLanguageLinks)));
 }
 const root=document.querySelector('[data-localized-site]');if(!root)return;
 const labels=JSON.parse(document.getElementById('locale-ui').textContent),form=document.getElementById('intl-inquiry'),cards=[...document.querySelectorAll('.intl-card')];
 let category='all';const search=document.getElementById('intl-search');
 function filter(){let n=0;const q=(search?.value||'').toLocaleLowerCase();cards.forEach(c=>{const show=(category==='all'||c.dataset.category===category)&&c.textContent.toLocaleLowerCase().includes(q);c.hidden=!show;if(show)n++});const out=document.getElementById('intl-count');if(out)out.textContent=n+' '+labels.count;}
 document.querySelectorAll('[data-category-filter]').forEach(b=>b.addEventListener('click',()=>{category=b.dataset.categoryFilter;document.querySelectorAll('[data-category-filter]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));filter()}));search?.addEventListener('input',filter);filter();
 document.querySelectorAll('[data-wave]').forEach(b=>b.addEventListener('click',()=>{b.setAttribute('aria-pressed',String(b.getAttribute('aria-pressed')!=='true'))}));
 const waveButton=document.getElementById('wave-transfer');waveButton?.addEventListener('click',()=>{const waves=[...document.querySelectorAll('[data-wave][aria-pressed=true]')].map(b=>b.dataset.wave+' nm').join(' + ');form.elements.message.value=[labels.form[17]+': '+(waves||'—'),form.elements.message.value].filter(Boolean).join('\n');document.getElementById('wave-status').textContent=labels.form[19];document.getElementById('intl-prepared').hidden=true;});
 const config=document.getElementById('intl-platform');document.getElementById('config-transfer')?.addEventListener('click',()=>{form.elements.product.value=config.value;form.elements.message.value=[labels.form[8]+': '+document.getElementById('intl-config-message').value,form.elements.message.value].filter(Boolean).join('\n');document.getElementById('intl-prepared').hidden=true;});
 const preselect=new URLSearchParams(location.search).get('product');if(preselect&&[...form.elements.product.options].some(o=>o.value===preselect))form.elements.product.value=preselect;
 form.addEventListener('input',()=>document.getElementById('intl-prepared').hidden=true);
 form.addEventListener('submit',e=>{e.preventDefault();if(!form.reportValidity())return;const f=new FormData(form);const p=form.elements.product.selectedOptions[0];const message=['APTREDLIGHT · OEM / ODM',labels.form[4]+': '+p.textContent+' ['+f.get('product')+']',labels.form[0]+': '+f.get('name'),labels.form[1]+': '+f.get('email'),labels.form[2]+': '+(f.get('company')||'—'),labels.form[3]+': '+f.get('country'),labels.form[5]+': '+f.get('quantity'),'',''+f.get('message')].join('\n');document.getElementById('intl-message-output').value=message;document.getElementById('intl-whatsapp').href='https://wa.me/8618823435519?text='+encodeURIComponent(message);document.getElementById('intl-prepared').hidden=false;document.getElementById('intl-copy-status').textContent='';document.getElementById('intl-prepared').scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth'});});
 document.getElementById('intl-copy').addEventListener('click',async()=>{const t=document.getElementById('intl-message-output');try{await navigator.clipboard.writeText(t.value);document.getElementById('intl-copy-status').textContent=labels.form[14]}catch{t.focus();t.select()}});
})();
