/* APTREDLIGHT measurement: intentional actions, never inquiry message contents. */
(()=>{
 'use strict';
 if(window.__aptAnalyticsInstalled)return;
 window.__aptAnalyticsInstalled=true;
 const routes=/^\/(?:$|(?:de|fr|es|zh-CN)\/?$|(?:de\/|fr\/|es\/|zh-CN\/)?products\/[a-z0-9-]+\.html$|guides\/(?:[a-z0-9-]+\.html)?$|(?:oem-odm|technical-documentation|catalog|rfq|quality-process)\.html$)/;
 const path=routes.test(location.pathname)?location.pathname:'(other)';
 const language=(document.documentElement.lang||'en').split('-')[0];
 const seenEvents=new WeakSet();const startedForms=new Set();
 const names=new Set(['quote_cta_click','quote_start','rfq_prepared','whatsapp_click','alibaba_click','spec_download','product_compare']);
 function emit(name,params={}){
  if(!names.has(name)||typeof window.gtag!=='function'||window.aptAnalyticsConsent===false||navigator.globalPrivacyControl===true)return;
  try{if(localStorage.getItem('apt-analytics-optout')==='1')return}catch{}
  const clean={page_path:path,content_language:language,measurement_version:'2026-11-16-v1',...params};
  try{window.gtag('event',name,clean)}catch{/* Measurement must never interrupt navigation or inquiry preparation. */}
 }
 function start(e){const form=e.target?.closest?.('#inquiry,#intl-inquiry,#rfq-form');if(form&&!startedForms.has(form.id)){startedForms.add(form.id);emit('quote_start',{form_version:form.id==='intl-inquiry'?'localized':form.id==='inquiry'?'main':'legacy'})}}
 document.addEventListener('click',e=>{
  if(seenEvents.has(e))return;seenEvents.add(e);
  const t=e.target?.closest?.('a,button');if(!t)return;
  if(t.id==='compare-open'){emit('product_compare',{product_count:Math.min(3,document.querySelectorAll('.compare-check:checked').length)});return}
  if(t.tagName!=='A')return;
  let url;try{url=new URL(t.getAttribute('href'),location.origin)}catch{return}
  const host=url.hostname.toLowerCase();
  if(host==='wa.me'||host==='api.whatsapp.com'||host==='web.whatsapp.com'){emit('whatsapp_click',{action_location:t.id==='whatsapp-enquiry'||t.id==='intl-whatsapp'?'prepared_rfq':'direct_link'});return}
  if(host==='alibaba.com'||host.endsWith('.alibaba.com')){emit('alibaba_click',{action_location:t.id==='alibaba-enquiry'?'prepared_rfq':'catalog_link'});return}
  if(url.origin===location.origin&&/\.pdf$/i.test(url.pathname)){emit('spec_download',{document_type:url.pathname.includes('checklist')?'buyer_checklist':'product_document'});return}
  if(url.origin===location.origin&&(/^#(?:rfq-contact|contact|inquiry|intl-inquiry)$/.test(url.hash)||/\/rfq\.html$/.test(url.pathname))){emit('quote_cta_click',{action_location:'quote_link'})}
 },true);
 document.addEventListener('input',start,true);
 document.addEventListener('change',start,true);
 document.addEventListener('submit',e=>{
  const f=e.target;if(!['inquiry','intl-inquiry','rfq-form'].includes(f?.id)||!f.checkValidity())return;
  queueMicrotask(()=>{
   const prepared=document.getElementById(f.id==='intl-inquiry'?'intl-prepared':f.id==='inquiry'?'prepared':'rfq-status');
   if(prepared&&!prepared.hidden)emit('rfq_prepared',{handoff_type:'whatsapp',form_version:f.id==='intl-inquiry'?'localized':f.id==='inquiry'?'main':'legacy'});
  });
 },true);
})();
