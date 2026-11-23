(()=>{
 const nav=document.querySelector('.journal-header #nav'),menu=document.querySelector('.journal-header #menu');
 if(!nav||!menu)return;
 // Company pages live in WordPress on the canonical site, including from the Sites mirror.
 const companyCms='https://www.aptredlight.com/cms/';
 if(!nav.querySelector('[data-cms-about]')){
  const region=document.createElement('div');region.className='cms-about-nav';region.dataset.cmsAbout='true';
  const parent=document.createElement('a');parent.className='cms-about-link';parent.href=companyCms+'about-us/';parent.textContent='About Us';
  const details=document.createElement('details');details.className='journal-menu cms-about-menu';
  const summary=document.createElement('summary');summary.setAttribute('aria-label','Toggle About Us submenu');
  const sr=document.createElement('span');sr.className='cms-about-sr';sr.textContent='About Us submenu';summary.append(sr);
  const panel=document.createElement('div');panel.className='journal-dropdown';
  [['Certificate','certificate'],['Factory','factory'],['Exhibition','exhibition'],['Video','video'],['Company History','company-history']].forEach(([label,slug])=>{
   const link=document.createElement('a');link.href=companyCms+slug+'/';link.textContent=label;panel.append(link);
  });
  details.append(summary,panel);region.append(parent,details);nav.insertBefore(region,nav.querySelector('[data-library-menu]'));
 }
 const groups=[...nav.querySelectorAll('details')];
 const hoverMedia=window.matchMedia('(min-width: 981px) and (hover: hover) and (pointer: fine)');
 const states=new Map();
 function setOpen(group,open){
  const state=states.get(group);
  if(state){clearTimeout(state.timer);state.summary.setAttribute('aria-expanded',String(open))}
  group.open=open;
 }
 function openGroup(group){groups.forEach(other=>{if(other!==group)setOpen(other,false)});setOpen(group,true)}
 function closeNav(){nav.classList.remove('open');menu.setAttribute('aria-expanded','false');groups.forEach(g=>setOpen(g,false))}
 // Capture to avoid legacy homepage toggle handlers firing twice.
 menu.addEventListener('click',e=>{e.stopImmediatePropagation();const open=nav.classList.toggle('open');menu.setAttribute('aria-expanded',String(open));},true);
 groups.forEach((group,index)=>{
  const summary=group.querySelector('summary'),panel=group.querySelector('.journal-dropdown');
  if(!summary||!panel)return;
  if(!panel.id)panel.id='navigation-dropdown-'+(index+1);
  summary.setAttribute('aria-controls',panel.id);
  summary.setAttribute('aria-expanded',String(group.open));
  const state={summary,timer:null,hovered:false};states.set(group,state);
  group.addEventListener('toggle',()=>{
   summary.setAttribute('aria-expanded',String(group.open));
   if(group.open)groups.forEach(other=>{if(other!==group)setOpen(other,false)});
  });
  const region=group.closest('[data-cms-about]')||group;
  region.addEventListener('pointerenter',event=>{
   if(!hoverMedia.matches||event.pointerType==='touch')return;
   state.hovered=true;clearTimeout(state.timer);openGroup(group);
  });
  region.addEventListener('pointerleave',()=>{
   state.hovered=false;clearTimeout(state.timer);
   if(!hoverMedia.matches)return;
   // Let the pointer cross the small gap without collapsing the panel.
   state.timer=setTimeout(()=>{
    if(!state.hovered&&!region.contains(document.activeElement))setOpen(group,false);
   },160);
  });
  region.addEventListener('focusout',()=>{
   clearTimeout(state.timer);
   state.timer=setTimeout(()=>{
    if(!region.contains(document.activeElement)&&!state.hovered)setOpen(group,false);
   },0);
  });
  summary.addEventListener('keydown',event=>{
   if(event.key!=='ArrowDown'&&event.key!=='ArrowUp')return;
   event.preventDefault();openGroup(group);
   const links=panel.querySelectorAll('a[href]');
   const target=event.key==='ArrowDown'?links[0]:links[links.length-1];
   if(target)target.focus();
  });
 });
 hoverMedia.addEventListener('change',()=>{
  states.forEach(state=>{state.hovered=false;clearTimeout(state.timer)});
  groups.forEach(group=>setOpen(group,false));
 });
 document.addEventListener('click',e=>{if(!e.target.closest('.journal-header'))closeNav()});
 document.addEventListener('keydown',event=>{
  if(event.key!=='Escape')return;
  const group=groups.find(g=>g.open&&g.contains(document.activeElement))||groups.find(g=>g.open);
  if(group){event.preventDefault();setOpen(group,false);states.get(group)?.summary.focus()}
  else if(nav.classList.contains('open')){event.preventDefault();closeNav();menu.focus()}
 });
 function filter(value){const b=document.querySelector(`[data-filter="${value}"]`);if(b)b.click()}
 nav.querySelectorAll('a').forEach(a=>a.addEventListener('click',e=>{const f=a.dataset.journalFilter;if(f){if(document.getElementById('catalog')){e.preventDefault();document.getElementById('product-search').value='';document.getElementById('product-search').dispatchEvent(new Event('input'));filter(f);location.hash='collection';}else a.href='/?category='+encodeURIComponent(f)+'#collection';}closeNav()}));
 const category=new URLSearchParams(location.search).get('category');if(category)filter(category);
 document.querySelectorAll('[data-buyer-brief]').forEach(a=>a.addEventListener('click',()=>{const field=document.querySelector('#inquiry textarea[name="message"]');if(field){const text='Project pathway: '+a.dataset.buyerBrief+'.';if(!field.value.includes(text))field.value=text+'\n'+field.value;document.querySelector('#interest').value='OEM/ODM partnership';}}));
})();
