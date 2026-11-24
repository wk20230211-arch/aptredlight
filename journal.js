(()=>{
 const nav=document.querySelector('.journal-header #nav'),menu=document.querySelector('.journal-header #menu');
 if(!nav||!menu)return;
 const guides=[["Red Light Therapy Second-Source Manufacturer: A Brand Qualification Plan", "https://www.aptredlight.com/guides/red-light-therapy-second-source-qualification.html"], ["What to verify before your first red light therapy OEM sample", "https://www.aptredlight.com/guides/oem-sample-checklist.html"], ["Red Light Therapy Manufacturer Selection Guide", "https://www.aptredlight.com/guides/red-light-manufacturer-selection.html"], ["Red Light Therapy OEM Total Cost Comparison: A Buyer Framework", "https://www.aptredlight.com/guides/red-light-therapy-oem-total-cost-comparison.html"], ["OEM/ODM Buyer Guides", "https://www.aptredlight.com/guides/index.html"], ["Red Light Therapy OEM After-Sales Support: An RMA Buyer Checklist", "https://www.aptredlight.com/guides/red-light-therapy-oem-after-sales-rma.html"], ["How to choose a red light therapy manufacturer in China", "https://www.aptredlight.com/guides/china-red-light-manufacturer.html"], ["How to Choose a Red Light Therapy OEM/ODM Manufacturer", "https://www.aptredlight.com/guides/oem-odm-buyer-guide.html"], ["Red Light Therapy Panel OEM: What to Include in Your RFQ", "https://www.aptredlight.com/guides/red-light-panel-oem-quotation-checklist.html"], ["Red Light Therapy OEM Packaging Approval: A Brand Buyer Checklist", "https://www.aptredlight.com/guides/red-light-therapy-oem-packaging-approval.html"], ["Red Light Therapy OEM Repeat Orders: A Buyer\u2019s Guide to Change Control", "https://www.aptredlight.com/guides/red-light-oem-repeat-order-change-control.html"], ["50 Red Light Therapy OEM/ODM Procurement FAQs", "https://www.aptredlight.com/guides/red-light-therapy-oem-faq.html"]];
 function wireNewsMenu(blog,grid,title,{fallback,latest,card}){
  if(location.origin!=='https://www.aptredlight.com')return;
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
    grid.replaceChildren(...guideCards);title.textContent=fallback;
    const request=new AbortController();newsFetch=request;const timer=setTimeout(()=>request.abort(),4000);
    try{const r=await fetch('/cms/?rest_route=/aptredlight-news/v1/menu',{credentials:'omit',cache:'no-store',redirect:'error',signal:request.signal});
     if(!r.ok||!/^application\/json/i.test(r.headers.get('content-type')||''))return;
     const body=await r.text();if(body.length>24000)return;const j=JSON.parse(body);
     if(newsFetch!==request||!blog.d.open||j.version!==1||!Array.isArray(j.items))return;
     const cards=[],seen=new Set();for(const item of j.items.slice(0,12)){
      const href=newsUrl(item?.url),name=typeof item?.title==='string'?item.title.trim().slice(0,120):'';
      if(!href||!name||!categories.has(item.category)||seen.has(href))continue;seen.add(href);const a=card(name,href),imgUrl=newsUrl(item.image,true);
      if(imgUrl){const img=document.createElement('img');img.src=imgUrl;img.alt='';img.width=320;img.height=200;img.loading='lazy';a.prepend(img)}
      cards.push(a);
     }
     if(cards.length){grid.replaceChildren(...cards);title.textContent=latest}
    }catch{}finally{clearTimeout(timer)}
   });
  }

 // Canonical English CMS menu; supported locales have their own equivalent menu below.
 if(/^en(?:-|$)/i.test(document.documentElement.lang||'en')&&!nav.dataset.cmsIntegrated){
  nav.dataset.cmsIntegrated='1';
  const verified={"products": "https://www.aptredlight.com/cms/product-center/", "customized": "https://www.aptredlight.com/cms/customized/", "solution": "https://www.aptredlight.com/cms/solution/", "about": "https://www.aptredlight.com/cms/about-us/", "blog": "https://www.aptredlight.com/cms/news/", "about/certificate": "https://www.aptredlight.com/cms/certificate/", "about/factory": "https://www.aptredlight.com/cms/factory/", "about/exhibition": "https://www.aptredlight.com/cms/exhibition/", "about/video": "https://www.aptredlight.com/cms/video/", "about/company-history": "https://www.aptredlight.com/cms/company-history/", "customized/private-label": "https://www.aptredlight.com/cms/customized/private-label/", "customized/oem": "https://www.aptredlight.com/cms/customized/oem/", "customized/odm": "https://www.aptredlight.com/cms/customized/odm/", "customized/jdm": "https://www.aptredlight.com/cms/customized/jdm/", "customized/distribution": "https://www.aptredlight.com/cms/customized/distribution/", "customized/technology-customization": "https://www.aptredlight.com/cms/customized/technology-customization/", "solution/physiotherapy-rehabilitation": "https://www.aptredlight.com/cms/solution/physiotherapy-rehabilitation/", "solution/athletic-team-training": "https://www.aptredlight.com/cms/solution/athletic-team-training/", "solution/yoga-pilates": "https://www.aptredlight.com/cms/solution/yoga-pilates/", "solution/spa-sauna": "https://www.aptredlight.com/cms/solution/spa-sauna/", "solution/beauty-skin-care": "https://www.aptredlight.com/cms/solution/beauty-skin-care/", "solution/gyms-fitness": "https://www.aptredlight.com/cms/solution/gyms-fitness/", "solution/wellness-centers": "https://www.aptredlight.com/cms/solution/wellness-centers/", "solution/commercial-leisure": "https://www.aptredlight.com/cms/solution/commercial-leisure/", "solution/pet-hospitals-clinics-grooming": "https://www.aptredlight.com/cms/solution/pet-hospitals-clinics-grooming/", "product/apt-t300": "https://www.aptredlight.com/cms/product-center/apt-t300/", "product/apt-t1260": "https://www.aptredlight.com/cms/product-center/apt-t1260/", "product/apt-3050-ultra": "https://www.aptredlight.com/cms/product-center/apt-3050-ultra/", "product/apt-a13": "https://www.aptredlight.com/cms/product-center/apt-a13/", "product/apt-masks": "https://www.aptredlight.com/cms/product-center/apt-masks/", "family/red-light-panels": "https://www.aptredlight.com/cms/product-family/red-light-panels/", "family/portable-panels": "https://www.aptredlight.com/cms/product-family/portable-panels/", "family/flexible-mats-and-sleeping-bags": "https://www.aptredlight.com/cms/product-family/flexible-mats-and-sleeping-bags/", "family/led-face-masks": "https://www.aptredlight.com/cms/product-family/led-face-masks/"},scenes=[["physiotherapy-rehabilitation", "Physiotherapy & Rehabilitation", "Clinical governance, intended use and model-specific evidence must be reviewed by the responsible clinician."], ["athletic-team-training", "Athletic & Team Training Centers", "Review scheduling, supervision, shared-equipment cleaning and the approved operating instructions."], ["yoga-pilates", "Yoga / Pilates Studios", "If equipment is considered near reformers, review clearance, member positions, foot traffic, coverage and cleaning turnaround between classes."], ["spa-sauna", "SPA & Sauna", "Do not assume suitability for sauna heat, steam or wet areas. Obtain the exact environmental rating before placement."], ["beauty-skin-care", "Beauty & Skin Care", "Confirm intended use, operator training, eye protection and cleaning instructions for the exact device."], ["gyms-fitness", "Gyms & Fitness Studios", "Define access control, supervision, session records and shared-equipment hygiene before procurement."], ["wellness-centers", "Wellness Centers", "Review the service brief, user screening, operating instructions and escalation procedures."], ["commercial-leisure", "Commercial & Leisure", "Review storage and transport, staffed supervision and between-session cleaning. Clarify whether session controls or booking integration are requested; availability is not assumed."], ["pet-hospitals-clinics-grooming", "Pet Hospitals & Clinics & Grooming", "Veterinary supervision is required. Verify animal-specific device suitability, handling and hygiene. Human consumer equipment is not recommended here."]],custom=[["private-label", "Private Label", "01 / BRAND LAUNCH", "Review an existing product platform and define brand artwork, packaging and the evidence needed before launch."], ["oem", "OEM Manufacturing", "02 / MANUFACTURING", "Provide a controlled specification and agree sample approval, manufacturing responsibilities and change control."], ["odm", "ODM Development", "03 / PRODUCT DEVELOPMENT", "Define the product brief and ask which design and engineering work can be evaluated for your project."], ["jdm", "JDM Co-Development", "04 / JOINT DEVELOPMENT", "Explore a proposed joint-development arrangement. Scope, intellectual property and investment require written agreement; no past JDM case is claimed."], ["distribution", "Distribution & Brands", "05 / CHANNEL PARTNERSHIP", "Discuss territory, channel requirements, documentation and service responsibilities. Exclusivity and local stock are not assumed."], ["technology-customization", "Technology Customization", "06 / ENGINEERING CAPABILITIES", "Explore requested hardware, interface and brand options. All mockups are illustrative, not verified product features."]];
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
  wireNewsMenu(blog,grid,title,{fallback:'Published buyer guides',latest:'Latest published news',card:link});
 if(legacy.children.length){const label=document.createElement('strong');label.textContent='Existing website resources';legacy.prepend(label);blog.panel.append(legacy)}
  nav.replaceChildren(link('Home','/'),products.box,customized.box,solution.box,about.box,blog.box,link('Contact Us','/#rfq-contact'));
 }
 // Keep verified locale destinations and explicitly identify English-only destination pages.
 const localNav={
  de:{top:['Startseite','Produkte','Individuelle Anpassung','Lösungen','Über uns','Blog','Kontakt'],ui:['Hauptnavigation','Menü öffnen oder schließen','Untermenü: %s','Zielseite auf Englisch','Einkaufsratgeber auf Englisch','Weitere Informationen'],products:['Alle Produkte','Rotlicht-Panels','Tragbare Panels','Matten und Schlafsäcke','LED-Gesichtsmasken','Gezielte Anwendungen','Ganzkörperliegen','Lichttherapie-Kappen'],custom:['Konfigurationsberatung','Private Label','OEM-Fertigung','ODM-Entwicklung','Gemeinsame JDM-Entwicklung','Vertrieb und Markenpartnerschaften','Technische Anpassung','Optische Technik'],solutions:['Physiotherapie und Rehabilitation','Athletik- und Mannschaftstraining','Yoga- und Pilatesstudios','Spa und Sauna','Schönheit und Hautpflege','Fitnessstudios','Wellnesszentren','Gewerbe und Freizeit','Tierkliniken und Tierpflege'],about:['Zertifikate','Fertigung','Messen','Videos','Unternehmensgeschichte','Einblick in die Fertigung'],blog:['Aktuelles','Einkaufsratgeber'],resources:['Unternehmen und Fertigung','Qualitätsprüfung','B2B-Beschaffung','Einkaufsratgeber','Produktbibliothek und Downloads','Zertifikate und Berichte']},
  fr:{top:['Accueil','Produits','Personnalisation','Solutions','À propos','Blog','Contact'],ui:['Navigation principale','Ouvrir ou fermer le menu','Sous-menu : %s','Page de destination en anglais','Guides d’achat en anglais','Autres ressources'],products:['Tous les produits','Panneaux de lumière rouge','Panneaux portables','Tapis et sacs de couchage','Masques LED','Équipements ciblés','Lits corps entier','Bonnets de luminothérapie'],custom:['Étudier votre configuration','Marque privée','Fabrication OEM','Développement ODM','Codéveloppement JDM','Distribution et partenariats','Personnalisation technique','Ingénierie optique'],solutions:['Physiothérapie et rééducation','Entraînement sportif et collectif','Studios de yoga et Pilates','Spa et sauna','Beauté et soins de la peau','Salles de sport','Centres de bien-être','Espaces commerciaux et de loisirs','Cliniques vétérinaires et toilettage'],about:['Certificats','Usine','Salons professionnels','Vidéos','Histoire de l’entreprise','Découvrir notre fabrication'],blog:['Actualités','Guides d’achat'],resources:['Entreprise et fabrication','Contrôle qualité','Approvisionnement B2B','Guides d’achat','Bibliothèque produits et téléchargements','Certificats et rapports']},
  es:{top:['Inicio','Productos','Personalización','Soluciones','Quiénes somos','Blog','Contacto'],ui:['Navegación principal','Abrir o cerrar el menú','Submenú: %s','Página de destino en inglés','Guías de compra en inglés','Más recursos'],products:['Todos los productos','Paneles de luz roja','Paneles portátiles','Esterillas y sacos de dormir','Máscaras LED','Equipos para zonas específicas','Camas de cuerpo entero','Gorros de fototerapia'],custom:['Revisar su configuración','Marca propia','Fabricación OEM','Desarrollo ODM','Desarrollo conjunto JDM','Distribución y alianzas de marca','Personalización técnica','Ingeniería óptica'],solutions:['Fisioterapia y rehabilitación','Entrenamiento deportivo y de equipos','Estudios de yoga y pilates','Spa y sauna','Belleza y cuidado de la piel','Gimnasios y centros de fitness','Centros de bienestar','Espacios comerciales y de ocio','Clínicas veterinarias y peluquería canina'],about:['Certificados','Fábrica','Ferias profesionales','Vídeos','Historia de la empresa','Conozca cómo fabricamos'],blog:['Noticias','Guías de compra'],resources:['Empresa y fabricación','Control de calidad','Abastecimiento B2B','Guías de compra','Biblioteca de productos y descargas','Certificados e informes']},
  'zh-cn':{top:['首页','产品','定制服务','解决方案','关于我们','博客','联系我们'],ui:['主导航','打开或关闭主菜单','展开或收起%s子菜单','目标页面为英文','英文采购指南','更多资料'],products:['全部产品','红光面板','便携面板','理疗垫与睡袋','LED 面罩','局部穿戴设备','全身理疗床','光疗帽'],custom:['配置咨询','自有品牌定制','OEM 制造','ODM 开发','JDM 联合开发','分销与品牌合作','技术定制','光学技术'],solutions:['理疗与康复机构','运动训练与团队训练中心','瑜伽与普拉提工作室','水疗与桑拿','美容与皮肤护理','健身房与健身工作室','健康管理中心','商业与休闲空间','动物医院、诊所与宠物美容'],about:['证书','工厂','展会','视频','公司发展历程','了解工厂生产'],blog:['新闻动态','采购指南'],resources:['公司与制造','质量核验','B2B 采购方案','采购指南','产品资料与下载','证书与报告']}
 };
 const pageLang=(document.documentElement.lang||'').toLowerCase();
 const locale=localNav[pageLang],localePath=pageLang==='zh-cn'?'zh-CN':pageLang;
 // pathname guards against mounting the locale menu on a non-locale route with incidental language metadata.
 if(locale&&location.pathname?.startsWith('/'+localePath+'/')&&!nav.dataset.cmsIntegrated){
  nav.dataset.cmsIntegrated='1';
  nav.setAttribute('aria-label',locale.ui[0]);menu.setAttribute('aria-label',locale.ui[1]);
  const base='/'+localePath+'/',cms='https://www.aptredlight.com/cms/';
  const rfqAnchor=/\/products\/[^/]+\.html$/.test(location.pathname)&&document.getElementById('rfq-contact')?'#rfq-contact':base+'#rfq-contact';
  const foreign=(a,label,enText=false)=>{
   a.hreflang='en';a.setAttribute('hreflang','en');
   if(enText)a.setAttribute('lang','en');
   a.textContent=label.replace(/\s*\(EN\)\s*→?\s*$/i,'')+' (EN)';
   // Use localized spoken context without assigning the translated label English pronunciation.
   if(!enText)a.setAttribute('aria-label',label.replace(/\s*\(EN\)\s*→?\s*$/i,'')+' — '+locale.ui[3]);
   else {const hint=document.createElement('span');hint.className='cms-about-sr';hint.lang=document.documentElement.lang;hint.textContent=' — '+locale.ui[3];a.append(hint)}
   return a;
  };
  function link(label,url,language='local'){
   const a=document.createElement('a');a.href=url;a.textContent=label;
   return language==='local'?a:foreign(a,label,language==='en-text');
  }
  function region(label,key,parent,rows){
   const box=document.createElement('div');box.className='cms-about-nav cms-integrated-region';box.dataset.cmsGroup=key;
   if(key==='about')box.dataset.cmsAbout='true';
   const disclosure=document.createElement('details');disclosure.className='journal-menu cms-about-menu';
   const summary=document.createElement('summary');const accessible=locale.ui[2].replace('%s',label);
   summary.setAttribute('aria-label',accessible);
   const sr=document.createElement('span');sr.className='cms-about-sr';sr.textContent=accessible;summary.append(sr);
   const panel=document.createElement('div');panel.className='journal-dropdown cms-panel-'+key;
   rows.forEach(row=>panel.append(link(...row)));disclosure.append(summary,panel);box.append(link(label,...parent),disclosure);
   return {box,panel,d:disclosure};
  }
  const categoryKeys=['panels','portable','body','masks','targeted','beds','caps'];
  const allProducts=base+'#products';
  const products=region(locale.top[1],'products',[allProducts],[[locale.products[0],allProducts],
   ...categoryKeys.map((key,i)=>[locale.products[i+1],base+'?category='+key+'#products']),
   ...[['T300','t300'],['T1260','t1260'],['3050 ULTRA','3050-ultra'],['A13','a13'],[locale.products[4],'smart-voice-mask']].map(([name,slug])=>[name,base+'products/'+slug+'.html'])]);
  const customPaths=['private-label','oem','odm','jdm','distribution','technology-customization'];
  const customized=region(locale.top[2],'customized',[base+'#configure'],[[locale.custom[0],base+'#configure'],[locale.custom[7],base+'#technology'],...customPaths.map((slug,i)=>[locale.custom[i+1],cms+'customized/'+slug+'/','en'])]);
  const solutionPaths=['physiotherapy-rehabilitation','athletic-team-training','yoga-pilates','spa-sauna','beauty-skin-care','gyms-fitness','wellness-centers','commercial-leisure','pet-hospitals-clinics-grooming'];
  const solution=region(locale.top[3],'solution',[cms+'solution/','en'],solutionPaths.map((slug,i)=>[locale.solutions[i],cms+'solution/'+slug+'/','en']));
  const aboutPaths=['certificate','factory','exhibition','video','company-history'];
  const about=region(locale.top[4],'about',[cms+'about-us/','en'],[[locale.about[5],base+'#factory'],...aboutPaths.map((slug,i)=>[locale.about[i],cms+slug+'/','en'])]);
  const blog=region(locale.top[5],'blog',[cms+'news/','en'],[[locale.blog[0],cms+'news/','en'],[locale.blog[1],'/guides/','en']]);
  const note=document.createElement('p');note.className='cms-resource-note';note.textContent=locale.ui[4];blog.panel.append(note);
  const grid=document.createElement('div');grid.className='cms-guide-grid';
  const newsCard=(name,url)=>link(name,url,'en-text');
  guides.slice(0,12).forEach(([name,url])=>grid.append(newsCard(name,url)));
  blog.panel.append(grid);
  const latest={de:'Neueste Meldungen auf Englisch',fr:'Dernières actualités publiées en anglais',es:'Últimas noticias publicadas en inglés','zh-cn':'最新英文新闻'};
  wireNewsMenu(blog,grid,note,{fallback:locale.ui[4],latest:latest[pageLang],card:newsCard});
  const resources=document.createElement('div');resources.className='cms-legacy-resources';
  const heading=document.createElement('strong');heading.textContent=locale.ui[5];resources.append(heading);
  ['/company.html','/quality-verification.html','/solutions/','/guides/','/product-library.html','/certificates.html'].forEach((url,i)=>resources.append(link(locale.resources[i],url,'en')));
  blog.panel.append(resources);
  nav.replaceChildren(link(locale.top[0],base),products.box,customized.box,solution.box,about.box,blog.box,link(locale.top[6],rfqAnchor));
  // Preserve existing footer links while disclosing English destinations to sighted and AT users.
  const englishPaths=new Set(['/guides/','/guides/red-light-therapy-oem-faq.html','/product-library.html','/certificates.html','/solutions/','/privacy.html','/company.html','/quality-verification.html','/resources/aptredlight-oem-buyer-checklist.pdf']);
  document.querySelectorAll('footer a[href]').forEach(a=>{
   const destination=new URL(a.href,location.href);
   if(destination.origin===location.origin&&englishPaths.has(destination.pathname)){
    const original=a.getAttribute('lang')==='en';a.removeAttribute('lang');
    const label=a.textContent.trim().replace(/\s*→$/,'');
    foreign(a,label,original&&(!/\(EN\)/i.test(label)||/^B2B sourcing|^Enquiry privacy|^Product library|^Certificates/.test(label)));
   }
  });
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
