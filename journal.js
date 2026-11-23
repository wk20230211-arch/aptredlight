(()=>{
 const nav=document.querySelector('.journal-header #nav'),menu=document.querySelector('.journal-header #menu');
 if(!nav||!menu)return;

 // Canonical CMS integration. English only; localized navigation remains unchanged.
 if(/^en(?:-|$)/i.test(document.documentElement.lang||'en')&&!nav.dataset.cmsIntegrated){
  nav.dataset.cmsIntegrated='1';
  const verified={"products": "https://www.aptredlight.com/cms/product-center/", "customized": "https://www.aptredlight.com/cms/customized/", "solution": "https://www.aptredlight.com/cms/solution/", "about": "https://www.aptredlight.com/cms/about-us/", "blog": "https://www.aptredlight.com/cms/news/", "about/certificate": "https://www.aptredlight.com/cms/certificate/", "about/factory": "https://www.aptredlight.com/cms/factory/", "about/exhibition": "https://www.aptredlight.com/cms/exhibition/", "about/video": "https://www.aptredlight.com/cms/video/", "about/company-history": "https://www.aptredlight.com/cms/company-history/", "customized/private-label": "https://www.aptredlight.com/cms/customized/private-label/", "customized/oem": "https://www.aptredlight.com/cms/customized/oem/", "customized/odm": "https://www.aptredlight.com/cms/customized/odm/", "customized/jdm": "https://www.aptredlight.com/cms/customized/jdm/", "customized/distribution": "https://www.aptredlight.com/cms/customized/distribution/", "customized/technology-customization": "https://www.aptredlight.com/cms/customized/technology-customization/", "solution/physiotherapy-rehabilitation": "https://www.aptredlight.com/cms/solution/physiotherapy-rehabilitation/", "solution/athletic-team-training": "https://www.aptredlight.com/cms/solution/athletic-team-training/", "solution/yoga-pilates": "https://www.aptredlight.com/cms/solution/yoga-pilates/", "solution/spa-sauna": "https://www.aptredlight.com/cms/solution/spa-sauna/", "solution/beauty-skin-care": "https://www.aptredlight.com/cms/solution/beauty-skin-care/", "solution/gyms-fitness": "https://www.aptredlight.com/cms/solution/gyms-fitness/", "solution/wellness-centers": "https://www.aptredlight.com/cms/solution/wellness-centers/", "solution/commercial-leisure": "https://www.aptredlight.com/cms/solution/commercial-leisure/", "solution/pet-hospitals-clinics-grooming": "https://www.aptredlight.com/cms/solution/pet-hospitals-clinics-grooming/", "product/apt-t300": "https://www.aptredlight.com/cms/product-center/apt-t300/", "product/apt-t1260": "https://www.aptredlight.com/cms/product-center/apt-t1260/", "product/apt-3050-ultra": "https://www.aptredlight.com/cms/product-center/apt-3050-ultra/", "product/apt-a13": "https://www.aptredlight.com/cms/product-center/apt-a13/", "product/apt-masks": "https://www.aptredlight.com/cms/product-center/apt-masks/", "family/red-light-panels": "https://www.aptredlight.com/cms/product-family/red-light-panels/", "family/portable-panels": "https://www.aptredlight.com/cms/product-family/portable-panels/", "family/flexible-mats-and-sleeping-bags": "https://www.aptredlight.com/cms/product-family/flexible-mats-and-sleeping-bags/", "family/led-face-masks": "https://www.aptredlight.com/cms/product-family/led-face-masks/"},scenes=[["physiotherapy-rehabilitation", "Physiotherapy & Rehabilitation", "Clinical governance, intended use and model-specific evidence must be reviewed by the responsible clinician."], ["athletic-team-training", "Athletic & Team Training Centers", "Review scheduling, supervision, shared-equipment cleaning and the approved operating instructions."], ["yoga-pilates", "Yoga / Pilates Studios", "If equipment is considered near reformers, review clearance, member positions, foot traffic, coverage and cleaning turnaround between classes."], ["spa-sauna", "SPA & Sauna", "Do not assume suitability for sauna heat, steam or wet areas. Obtain the exact environmental rating before placement."], ["beauty-skin-care", "Beauty & Skin Care", "Confirm intended use, operator training, eye protection and cleaning instructions for the exact device."], ["gyms-fitness", "Gyms & Fitness Studios", "Define access control, supervision, session records and shared-equipment hygiene before procurement."], ["wellness-centers", "Wellness Centers", "Review the service brief, user screening, operating instructions and escalation procedures."], ["commercial-leisure", "Commercial & Leisure", "Review storage and transport, staffed supervision and between-session cleaning. Clarify whether session controls or booking integration are requested; availability is not assumed."], ["pet-hospitals-clinics-grooming", "Pet Hospitals & Clinics & Grooming", "Veterinary supervision is required. Verify animal-specific device suitability, handling and hygiene. Human consumer equipment is not recommended here."]],custom=[["private-label", "Private Label", "01 / BRAND LAUNCH", "Review an existing product platform and define brand artwork, packaging and the evidence needed before launch."], ["oem", "OEM Manufacturing", "02 / MANUFACTURING", "Provide a controlled specification and agree sample approval, manufacturing responsibilities and change control."], ["odm", "ODM Development", "03 / PRODUCT DEVELOPMENT", "Define the product brief and ask which design and engineering work can be evaluated for your project."], ["jdm", "JDM Co-Development", "04 / JOINT DEVELOPMENT", "Explore a proposed joint-development arrangement. Scope, intellectual property and investment require written agreement; no past JDM case is claimed."], ["distribution", "Distribution & Brands", "05 / CHANNEL PARTNERSHIP", "Discuss territory, channel requirements, documentation and service responsibilities. Exclusivity and local stock are not assumed."], ["technology-customization", "Technology Customization", "06 / ENGINEERING CAPABILITIES", "Explore requested hardware, interface and brand options. All mockups are illustrative, not verified product features."]],guides=[["Red Light Therapy Second-Source Manufacturer: A Brand Qualification Plan", "https://www.aptredlight.com/guides/red-light-therapy-second-source-qualification.html"], ["What to verify before your first red light therapy OEM sample", "https://www.aptredlight.com/guides/oem-sample-checklist.html"], ["Red Light Therapy Manufacturer Selection Guide", "https://www.aptredlight.com/guides/red-light-manufacturer-selection.html"], ["Red Light Therapy OEM Total Cost Comparison: A Buyer Framework", "https://www.aptredlight.com/guides/red-light-therapy-oem-total-cost-comparison.html"], ["OEM/ODM Buyer Guides", "https://www.aptredlight.com/guides/index.html"], ["Red Light Therapy OEM After-Sales Support: An RMA Buyer Checklist", "https://www.aptredlight.com/guides/red-light-therapy-oem-after-sales-rma.html"], ["How to choose a red light therapy manufacturer in China", "https://www.aptredlight.com/guides/china-red-light-manufacturer.html"], ["How to Choose a Red Light Therapy OEM/ODM Manufacturer", "https://www.aptredlight.com/guides/oem-odm-buyer-guide.html"], ["Red Light Therapy Panel OEM: What to Include in Your RFQ", "https://www.aptredlight.com/guides/red-light-panel-oem-quotation-checklist.html"], ["Red Light Therapy OEM Packaging Approval: A Brand Buyer Checklist", "https://www.aptredlight.com/guides/red-light-therapy-oem-packaging-approval.html"], ["Red Light Therapy OEM Repeat Orders: A Buyer\u2019s Guide to Change Control", "https://www.aptredlight.com/guides/red-light-oem-repeat-order-change-control.html"], ["50 Red Light Therapy OEM/ODM Procurement FAQs", "https://www.aptredlight.com/guides/red-light-therapy-oem-faq.html"]];
  const resolve=(key,fallback)=>verified[key]||fallback;
  const link=(label,url)=>{const a=document.createElement('a');a.textContent=label;a.href=url;return a};
  const old=[...nav.children],oldProducts=old.find(el=>el.tagName==='DETAILS'&&/products/i.test(el.querySelector('summary')?.textContent||''));
  const legacy=document.createElement('div');legacy.className='cms-legacy-resources';
  old.forEach(el=>{if(el===oldProducts)return;if(el.tagName==='DETAILS'){el.querySelectorAll('.journal-dropdown>a').forEach(a=>legacy.append(a))}else if(el.tagName==='A'&&!['/','/index.html'].includes(el.getAttribute('href')))legacy.append(el)});
  function region(label,key,fallback,rows){
   const box=document.createElement('div');box.className='cms-about-nav cms-integrated-region';box.dataset.cmsGroup=key;if(key==='about')box.dataset.cmsAbout='true';
   box.append(link(label,resolve(key,fallback)));const d=document.createElement('details');d.className='journal-menu cms-about-menu';const summary=document.createElement('summary');summary.setAttribute('aria-label','Toggle '+label+' submenu');const sr=document.createElement('span');sr.className='cms-about-sr';sr.textContent=label+' submenu';summary.append(sr);const panel=document.createElement('div');panel.className='journal-dropdown cms-panel-'+key;rows.forEach(v=>panel.append(link(v[0],resolve(v[1],v[2]))));d.append(summary,panel);box.append(d);return {box,d,panel};
  }
  const products=region('Products','products','/product-library.html',[
   ['All published products','products','/product-library.html'],['Red light panels','family/red-light-panels','/?category=panels#collection'],['Portable panels','family/portable-panels','/?category=portable#collection'],['Mats & sleeping bags','family/flexible-mats-and-sleeping-bags','/?category=body#collection'],['LED face masks','family/led-face-masks','/?category=masks#collection'],['T300','product/apt-t300','/?category=panels#collection'],['T1260','product/apt-t1260','/?category=panels#collection'],['3050 ULTRA','product/apt-3050-ultra','/products/3050-ultra.html'],['A13','product/apt-a13','/products/a13.html'],['LED mask family','product/apt-masks','/?category=masks#collection']]);
  if(oldProducts){const extra=document.createElement('div');extra.className='cms-legacy-product-links';const title=document.createElement('strong');title.textContent='Existing product selection tools';extra.append(title);oldProducts.querySelectorAll('.journal-dropdown>a').forEach(a=>extra.append(a));products.panel.append(extra)}
  const customized=region('Customized','customized','/oem-odm.html',custom.map(v=>[v[1],'customized/'+v[0],v[0]==='technology-customization'?'/technical-documentation.html':'/oem-odm.html']));
  const solution=region('Solution','solution','/solutions/',scenes.map(v=>[v[1],'solution/'+v[0],'/solutions/']));const shortcuts=document.createElement('div');shortcuts.className='cms-solution-shortcuts';[['Beauty & Skincare','beauty-skin-care'],['SPA & Sauna','spa-sauna'],['Wellness Centers','wellness-centers'],['Sports & Gym','athletic-team-training'],['Yoga / Pilates','yoga-pilates']].forEach(v=>shortcuts.append(link(v[0],resolve('solution/'+v[1],'/solutions/'))));shortcuts.append(link('Product library · no checkout','/product-library.html'));solution.panel.prepend(shortcuts);solution.panel.append(link('Existing product selection paths','/solutions/'));
  const about=region('About Us','about','/company.html',[['Certificate','about/certificate','/certificates.html'],['Factory','about/factory','/company.html'],['Exhibition','about/exhibition','/company.html'],['Video','about/video','/company.html'],['Company History','about/company-history','/company.html']]);
  const blog=region('Blog','blog','/guides/',[['News list','blog','/guides/']]);const title=document.createElement('p');title.className='cms-resource-note';title.textContent='Existing buyer guides · not new WordPress posts';blog.panel.append(title);const grid=document.createElement('div');grid.className='cms-guide-grid';guides.slice(0,12).forEach(v=>grid.append(link(v[0],v[1])));blog.panel.append(grid);
  if(location.origin==='https://www.aptredlight.com'){
   let newsFetch=null;
   const categories=new Set(['industry-news','company-news','video']);
   const newsUrl=(v,img=false)=>{
    if(typeof v!=='string'||!v.startsWith('/cms/')||v.length>500||/[\\\s]/.test(v)||/%(?:2e|2f|5c)/i.test(v))return '';
    try{const u=new URL(v,location.origin);if(u.origin!==location.origin||!u.pathname.startsWith('/cms/')||u.hash||/\/(?:wp-admin|wp-login\.php|wp-json)(?:\/|$)/i.test(u.pathname))return '';
     if(img&&(!u.pathname.startsWith('/cms/wp-content/uploads/')||!/\.(?:png|jpe?g|webp|avif|gif)$/i.test(u.pathname)||u.search))return '';
     if(!img&&u.search&&!/^\?p=[1-9][0-9]{0,15}$/.test(u.search))return '';return u.pathname+u.search;
    }catch{return ''}
   };
   const guideCards=[...grid.children];
   blog.d.addEventListener('toggle',async()=>{
    newsFetch?.abort();if(!blog.d.open)return;
    grid.replaceChildren(...guideCards);title.textContent='Published buyer guides';
    const request=new AbortController();newsFetch=request;const timer=setTimeout(()=>request.abort(),4000);
    try{const r=await fetch('/cms/?rest_route=/aptredlight-news/v1/menu',{credentials:'omit',cache:'no-store',redirect:'error',signal:request.signal});
     if(!r.ok||!/^application\/json/i.test(r.headers.get('content-type')||''))return;
     const body=await r.text();if(body.length>24000)return;const j=JSON.parse(body);
     if(newsFetch!==request||!blog.d.open||j.version!==1||!Array.isArray(j.items))return;
     const cards=[],seen=new Set();for(const item of j.items.slice(0,12)){
      const href=newsUrl(item?.url),name=typeof item?.title==='string'?item.title.trim().slice(0,120):'';
      if(!href||!name||!categories.has(item.category)||seen.has(href))continue;seen.add(href);const a=link(name,href),imgUrl=newsUrl(item.image,true);
      if(imgUrl){const img=document.createElement('img');img.src=imgUrl;img.alt='';img.width=320;img.height=200;img.loading='lazy';a.prepend(img)}
      cards.push(a);
     }
     if(cards.length){grid.replaceChildren(...cards);title.textContent='Latest published news'}
    }catch{}finally{clearTimeout(timer)}
   });
  }
 if(legacy.children.length){const label=document.createElement('strong');label.textContent='Existing website resources';legacy.prepend(label);blog.panel.append(legacy)}
  nav.replaceChildren(link('Home','/'),products.box,customized.box,solution.box,about.box,blog.box,link('Contact Us','/#rfq-contact'));
 }
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
  const region=group.closest('[data-cms-group]')||group.closest('[data-cms-about]')||group;
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
