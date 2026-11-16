(()=>{
 const nav=document.querySelector('.journal-header #nav'),menu=document.querySelector('.journal-header #menu');
 if(!nav||!menu)return;
 const groups=[...nav.querySelectorAll('details')];
 function closeNav(){nav.classList.remove('open');menu.setAttribute('aria-expanded','false');groups.forEach(g=>g.open=false)}
 // Capture to avoid legacy homepage toggle handlers firing twice.
 menu.addEventListener('click',e=>{e.stopImmediatePropagation();const open=nav.classList.toggle('open');menu.setAttribute('aria-expanded',String(open));},true);
 groups.forEach(g=>g.addEventListener('toggle',()=>{if(g.open)groups.forEach(other=>{if(other!==g)other.open=false})}));
 document.addEventListener('click',e=>{if(!e.target.closest('.journal-header'))closeNav()});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeNav();menu.focus()}});
 function filter(value){const b=document.querySelector(`[data-filter="${value}"]`);if(b)b.click()}
 nav.querySelectorAll('a').forEach(a=>a.addEventListener('click',e=>{const f=a.dataset.journalFilter;if(f){if(document.getElementById('catalog')){e.preventDefault();document.getElementById('product-search').value='';document.getElementById('product-search').dispatchEvent(new Event('input'));filter(f);location.hash='collection';}else a.href='/?category='+encodeURIComponent(f)+'#collection';}closeNav()}));
 const category=new URLSearchParams(location.search).get('category');if(category)filter(category);
 document.querySelectorAll('[data-buyer-brief]').forEach(a=>a.addEventListener('click',()=>{const field=document.querySelector('#inquiry textarea[name="message"]');if(field){const text='Project pathway: '+a.dataset.buyerBrief+'.';if(!field.value.includes(text))field.value=text+'\n'+field.value;document.querySelector('#interest').value='OEM/ODM partnership';}}));
})();
