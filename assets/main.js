// APTREDLIGHT: navigation, current year and accessible RFQ-to-WhatsApp handoff
const menuButton=document.getElementById('menu');
const navLinks=document.getElementById('navlinks');
menuButton?.addEventListener('click',()=>{
  const open=navLinks.classList.toggle('open');
  menuButton.setAttribute('aria-expanded',String(open));
});
navLinks?.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{
  navLinks.classList.remove('open');
  menuButton?.setAttribute('aria-expanded','false');
}));
const year=document.getElementById('year');if(year)year.textContent=String(new Date().getFullYear());
const ledGrid=document.getElementById('leds');for(let i=0;ledGrid&&i<54;i++)ledGrid.appendChild(document.createElement('i'));
const WA_NUMBER='8618823435519';
const clean=(val,max=400)=>String(val||'').trim().slice(0,max);
const makeMessage=(entries)=>'APTREDLIGHT | OEM/ODM RFQ\n'+entries.map(([key,val])=>key+': '+clean(val,1600)).join('\n')+'\n\nPlease confirm available model configurations, sample options and your quotation requirements.';
function openWhatsApp(message,status){
  const target='https://wa.me/'+WA_NUMBER+'?text='+encodeURIComponent(message);
  if(status){
    status.textContent='Your RFQ is ready. WhatsApp will open with a prefilled message. You must press Send to deliver it.';
    const a=document.createElement('a');a.href=target;a.target='_blank';a.rel='noopener noreferrer';a.textContent='Open WhatsApp manually ↗';status.appendChild(document.createTextNode(' '));status.appendChild(a);
  }
  // Opens only after a user-initiated submission; data is not stored by our static site.
  const win=window.open(target,'_blank');
  if(win)win.opener=null;
}
const rfq=document.getElementById('rfq-form');
const modelMap={
  't300-ultra':'T300 Ultra — flagship panel',
  'a13-pro':'A13 Pro — portable panel',
  'm70-core':'M70 Core — desktop panel',
  '3050-ultra':'3050 Ultra — full-body system',
  'mask':'LED Mask / wearable',
  'mat':'MAT / Sleeping Bag'
};
if(rfq){
  const selected=new URLSearchParams(location.search).get('product');
  if(selected && modelMap[selected]){
    const select=rfq.elements.namedItem('product');if(select)select.value=modelMap[selected];
  }
  const rows=()=>{const d=new FormData(rfq);return[
    ['Company / Brand',d.get('company')],['Contact name',d.get('contact')],
    ['Business email',d.get('email')],['Destination market',d.get('market')],
    ['Company website',d.get('website')],['WhatsApp / phone',d.get('phone')],
    ['Product direction',d.get('product')],['Estimated first order',d.get('quantity')],
    ['Sample / launch timeline',d.get('timeline')],['Target budget',d.get('budget')],
    ['Customization',d.get('customization')],['Required documents',d.get('documentation')],
    ['Project details',d.get('details')]
  ].filter(([,v])=>clean(v)!=='');};
  rfq.addEventListener('submit',e=>{
    e.preventDefault();if(!rfq.reportValidity())return;
    openWhatsApp('Hello APTREDLIGHT Team,\n\n'+makeMessage(rows()),document.getElementById('rfq-status'));
  });
  document.getElementById('rfq-copy')?.addEventListener('click',async()=>{
    const target=document.getElementById('rfq-status');const msg=makeMessage(rows());
    try{
      if(!navigator.clipboard?.writeText)throw new Error('Clipboard not supported');
      await navigator.clipboard.writeText(msg);
      target.textContent='RFQ details copied. Paste the details into your preferred communication channel.';
    }catch{
      target.textContent='Clipboard access is not available. Please continue with the WhatsApp button or copy the details manually.';
    }
  });
}
// Legacy quick-inquiry compatibility: homepage now directs buyers to the full RFQ.
document.getElementById('inquiry')?.addEventListener('submit',e=>{
  e.preventDefault();if(!e.currentTarget.reportValidity())return;
  const d=new FormData(e.currentTarget);
  const rows=[['Company',d.get('company')],['Email',d.get('email')],['Market',d.get('market')],['Product',d.get('product')],['Details',d.get('details')]];
  openWhatsApp(makeMessage(rows),document.getElementById('inquiry-status'));
});
