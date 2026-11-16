/* APTREDLIGHT enquiry delivery: response consent is separate from analytics choice. */
(()=>{
'use strict';
if(window.__aptLeadCaptureInstalled)return;
window.__aptLeadCaptureInstalled=true;
const ENDPOINT='https://aptredlight-wellness.wk20230211.chatgpt.site/api/leads/submit';
const FORM_IDS=new Set(['inquiry','intl-inquiry','b2b-inquiry']);
const LIMITS={name:100,email:160,company:160,country:100,product:160,quantity:100,customization:1000,phone:80,timeline:100,message:5000};
const UTM_KEYS=['utm_source','utm_medium','utm_campaign','utm_content','utm_term'];
const PRIVACY_KEY='apt-lead-attribution-v1';
const FAMILY=new Set(['panels','portable','masks','flexible','full-body','body','targeted','beds','caps']);
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const states=new WeakMap();let memoryAttribution=null;
function text(v,max){return String(v??'').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g,'').trim().slice(0,max)}
function safePath(v){try{const p=new URL(v,location.origin).pathname;return /^\/[a-zA-Z0-9_./-]{0,250}$/.test(p)&&!p.includes('..')?p:'/'}catch{return '/'}}
function safeHost(v){try{const u=new URL(v);return ['https:','http:'].includes(u.protocol)?u.hostname.slice(0,253):''}catch{return ''}}
function campaignText(v){const s=text(v,180);return /@|(?:\+?\d[\s()-]*){9,}/.test(s)?'':s.replace(/[<>]/g,'')}
function attributionRecord(v){const a={};for(const k of UTM_KEYS)a[k]=campaignText(v?.[k]);a.referrer_host=safeHost(v?.referrer_host?'https://'+v.referrer_host:'');a.landing_path=safePath(v?.landing_path||'/');return a}
function attribution(){
 if(memoryAttribution)return memoryAttribution;
 let saved=null;try{const raw=sessionStorage.getItem(PRIVACY_KEY);if(raw&&raw.length<8000)saved=JSON.parse(raw)}catch{}
 const u=new URL(location.href);const current={};for(const k of UTM_KEYS)current[k]=campaignText(u.searchParams.get(k));current.referrer_host=safeHost(document.referrer);current.landing_path=safePath(location.href);
 const first=saved?.first?attributionRecord(saved.first):current;
 memoryAttribution={first,current};try{sessionStorage.setItem(PRIVACY_KEY,JSON.stringify(memoryAttribution))}catch{}
 return memoryAttribution;
}
function uuid(){if(window.crypto?.randomUUID)return window.crypto.randomUUID();if(!window.crypto?.getRandomValues)throw new Error('Secure request ID unavailable');const b=window.crypto.getRandomValues(new Uint8Array(16));b[6]=(b[6]&15)|64;b[8]=(b[8]&63)|128;const s=[...b].map(n=>n.toString(16).padStart(2,'0')).join('');return s.slice(0,8)+'-'+s.slice(8,12)+'-'+s.slice(12,16)+'-'+s.slice(16,20)+'-'+s.slice(20)}
function analyticsAllowed(){if(window.aptAnalyticsConsent===false||navigator.globalPrivacyControl===true)return false;try{if(localStorage.getItem('apt-analytics-optout')==='1')return false}catch{}return typeof window.gtag==='function'}
function eventParams(form){const family=FAMILY.has(form.dataset.productFamily)?form.dataset.productFamily:'general';return {form_version:form.id==='inquiry'?'main':form.id==='intl-inquiry'?'localized':'b2b',page_category:form.id==='b2b-inquiry'?'oem_solution':'home',product_category:family}}
function emitConfirmed(form,state,receipt){if(state.emitted.has(receipt))return;state.emitted.add(receipt);if(analyticsAllowed())try{window.gtag('event','generate_lead',eventParams(form))}catch{}}
function values(form){const d=new FormData(form);const v={};for(const [k,max]of Object.entries(LIMITS))v[k]=text(d.get(k),max);const waves=d.getAll('wavelength').map(v=>text(v,30)).filter(Boolean).slice(0,12);if(waves.length)v.customization=text([v.customization,'Wavelengths to discuss: '+waves.join(', ')].filter(Boolean).join('\n'),LIMITS.customization);v.consent=d.get('consent')==='on'||d.get('consent')==='true'||form.elements.namedItem('consent')?.checked===true;v.website=text(d.get('website'),200);return v}
function payloadFor(v,started,attrs){const p={...v,client_started_at:started,submitted_from:safePath(location.href),attribution:attributionRecord(attrs.first)};return p}
function chooseRequest(state,payload,newId=uuid){const fingerprint=JSON.stringify(payload);if(state.fingerprint!==fingerprint||!state.requestId){state.fingerprint=fingerprint;state.requestId=newId();state.receipt=null}return {...payload,request_id:state.requestId}}
function validReceipt(response,body){return [200,201].includes(response.status)&&body?.ok===true&&UUID.test(body.lead_id||'')}
async function send(payload,fetcher=window.fetch.bind(window)){
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),18000);
 try{const response=await fetcher(ENDPOINT,{method:'POST',headers:{'Content-Type':'application/json'},mode:'cors',credentials:'omit',redirect:'error',body:JSON.stringify(payload),signal:controller.signal});let body=null;try{body=await response.json()}catch{}if(!validReceipt(response,body)){const error=new Error('Delivery not confirmed');error.status=response.status;throw error}return body}finally{clearTimeout(timer)}
}
function labelField(form,name,label,kind='input'){
 if(form.elements.namedItem(name))return;const l=document.createElement('label');l.lang='en';l.className='apt-lead-added-field';l.append(document.createTextNode(label));const el=document.createElement(kind);el.name=name;if(kind==='input')el.type=name==='phone'?'tel':'text';if(kind==='textarea')el.rows=3;l.append(el);const submit=form.querySelector('[type="submit"]');submit?.parentNode?.insertBefore(l,submit)||form.append(l);
}
function notify(state,message,kind){state.status.textContent=message;state.status.dataset.state=kind;state.status.hidden=false;state.status.setAttribute('role',kind==='error'?'alert':'status');if(kind==='error')state.status.focus({preventScroll:true})}
function summary(v){return ['APTREDLIGHT | OEM/ODM enquiry','Name: '+v.name,'Business email: '+v.email,'Company: '+v.company,'Destination market: '+v.country,'Product: '+v.product,'Quantity: '+v.quantity,v.customization&&'Customization: '+v.customization,v.phone&&'Phone: '+v.phone,v.timeline&&'Timeline: '+v.timeline,'Project details: '+v.message].filter(Boolean).join('\n')}
function fallback(form,state,v){
 state.fallback.replaceChildren();state.fallback.hidden=false;const p=document.createElement('p');p.lang='en';p.textContent='The website has not confirmed delivery. You may retry the same request, copy your details, or choose WhatsApp. Nothing is sent to WhatsApp automatically.';
 const output=document.createElement('textarea');output.readOnly=true;output.rows=5;output.value=summary(v);output.setAttribute('aria-label','Enquiry details for manual copy');
 const a=document.createElement('a');a.className='button outline';a.target='_blank';a.rel='noopener noreferrer';a.href='https://wa.me/8618823435519?text='+encodeURIComponent(output.value);a.textContent='Open WhatsApp manually →';a.lang='en';
 const copy=document.createElement('button');copy.type='button';copy.textContent='Copy enquiry details';copy.lang='en';copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(output.value);notify(state,'Details copied. You still need to send them through your chosen channel.','notice')}catch{output.focus();output.select();notify(state,'Select and copy the details above. Website delivery is still unconfirmed.','notice')}});
 state.fallback.append(p,output,a,copy);
}
async function submit(event){
 const form=event.target;if(!FORM_IDS.has(form?.id))return;event.preventDefault();event.stopImmediatePropagation();const state=states.get(form);if(!state||state.inflight)return;
 if(!form.reportValidity())return;const v=values(form);if(['name','email','company','country','product','quantity','message'].some(k=>!v[k])){notify(state,'Please complete all required fields with your enquiry details.','error');return}
 if(!v.consent){notify(state,'Please consent to storing this enquiry so our team can respond.','error');return}
 if(v.website){notify(state,'We could not accept this request. Please contact our team using the public contact options.','error');return}
 if(Date.now()-state.startedMs>24*60*60*1000){state.startedMs=Date.now();state.started=new Date(state.startedMs).toISOString();state.requestId=null;notify(state,'This form has been open for a long time. Review your details and submit again in a moment.','notice');return}
 if(Date.now()-state.startedMs<2000){notify(state,'Please take a moment to review your details, then submit again.','notice');return}
 const p=payloadFor(v,state.started,attribution());const request=chooseRequest(state,p);
 if(state.receipt){notify(state,'Your enquiry has already been received. You can update the details to send a new request.','success');return}
 state.inflight=true;for(const b of state.buttons)b.disabled=true;state.fallback.hidden=true;notify(state,'Sending your enquiry securely… Please wait.','sending');
 try{const receipt=await send(request);state.receipt=receipt.lead_id;notify(state,'Your enquiry has been received and stored for our team to review. This is not an order or a confirmed quotation.','success');emitConfirmed(form,state,receipt.lead_id)}
 catch(error){if(error.status===409){state.requestId=null;notify(state,'This request changed while being retried. Your details are retained; review them and submit again as a new request.','error')}else if(error.status===429)notify(state,'Too many attempts. Please wait before retrying, or use the manual contact option below. Delivery is not confirmed.','error');else if(error.status===400||error.status===422)notify(state,'We could not accept these details. Check the required fields and try again. Delivery is not confirmed.','error');else notify(state,'Delivery could not be confirmed. Your form is retained; retrying unchanged details will use the same request reference.','error');fallback(form,state,v)}
 finally{state.inflight=false;for(const b of state.buttons)b.disabled=false}
}
function install(form){
 if(states.has(form))return;form.classList.add('apt-lead-connected');
 for(const [n,label,kind]of [['name','Your name *'],['email','Business email *'],['company','Company / brand *'],['country','Destination market *'],['product','Product of interest *'],['quantity','Estimated quantity *'],['message','Project requirements *','textarea']])labelField(form,n,label,kind);
 labelField(form,'customization','Customization requirements (optional)','textarea');labelField(form,'phone','Phone / WhatsApp (optional)');labelField(form,'timeline','Target timeline (optional)');
 for(const [n,max]of Object.entries(LIMITS)){const f=form.elements.namedItem(n);if(f){if('maxLength'in f)f.maxLength=max;f.required=['name','email','company','country','product','quantity','message'].includes(n);if(n==='email')f.type='email';if(f.required){f.setAttribute('aria-required','true');const label=f.closest('label');if(label&&!label.textContent.includes('*')){const mark=document.createElement('span');mark.className='apt-required';mark.textContent=' *';label.append(mark)}}}}
 const former=form.querySelector('.form-note');if(former)former.hidden=true;for(const p of form.querySelectorAll(':scope > p'))if(/Nothing is sent|Nichts wird|Rien|Nada se|Aucun envoi|No se envía|不会自动|Nothing.*automatically/i.test(p.textContent))p.hidden=true;
 for(const id of ['prepared','intl-prepared']){const old=form.querySelector('#'+id);if(old)old.hidden=true}
 let consent=form.elements.namedItem('consent');if(!consent){const l=document.createElement('label');l.className='apt-lead-consent';l.lang='en';consent=document.createElement('input');consent.type='checkbox';consent.name='consent';consent.required=true;l.append(consent,document.createTextNode(' I agree that APTREDLIGHT may store this enquiry and contact me to respond. This does not subscribe me to marketing. '));const link=document.createElement('a');link.href='/privacy.html';link.target='_blank';link.rel='noopener';link.textContent='Privacy notice';l.append(link);const button=form.querySelector('[type="submit"]');if(button)button.parentNode.insertBefore(l,button);else form.append(l)}else{consent.required=true;const l=consent.closest('label');if(l&&!l.querySelector('a[href="/privacy.html"]')){const a=document.createElement('a');a.href='/privacy.html';a.textContent=' Privacy notice';a.lang='en';l.append(a)}}
 let pot=form.elements.namedItem('website');if(!pot){const l=document.createElement('label');l.className='apt-lead-honeypot';l.setAttribute('aria-hidden','true');l.textContent='Leave this field blank';pot=document.createElement('input');pot.type='text';pot.name='website';l.append(pot);form.append(l)}pot.tabIndex=-1;pot.autocomplete='off';pot.setAttribute('aria-hidden','true');pot.closest('label')?.classList.add('apt-lead-honeypot');
 const notice=document.createElement('p');notice.className='apt-lead-notice';notice.lang='en';notice.textContent='Submitting sends your details to APTREDLIGHT’s private enquiry records so our team can respond. Required fields are marked *. No payment or automatic WhatsApp message is sent.';const button=form.querySelector('[type="submit"]');if(button)button.parentNode.insertBefore(notice,button);else form.append(notice);
 const status=form.querySelector('#b2b-status')||document.createElement('p');status.classList.add('apt-lead-status');status.lang='en';status.tabIndex=-1;status.setAttribute('role','status');status.setAttribute('aria-live','polite');form.append(status);
 const box=document.createElement('div');box.className='apt-lead-fallback';box.hidden=true;form.append(box);
 const buttons=[...form.querySelectorAll('button[type="submit"],input[type="submit"]')];for(const b of buttons){if(b.tagName==='INPUT')b.value='Send enquiry';else b.textContent='Send enquiry →';b.lang='en'}
 const startedMs=Date.now();states.set(form,{startedMs,started:new Date(startedMs).toISOString(),inflight:false,requestId:null,fingerprint:null,receipt:null,emitted:new Set(),buttons,status,fallback:box});
 if(form.id==='b2b-inquiry'){let started=false;const first=()=>{if(!started){started=true;if(analyticsAllowed())try{window.gtag('event','quote_start',eventParams(form))}catch{}}};form.addEventListener('input',first,{once:true})}
}
function init(){attribution();for(const f of document.querySelectorAll('#inquiry,#intl-inquiry,#b2b-inquiry'))install(f)}
document.addEventListener('submit',submit,true);
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
if(typeof window.__APT_LEAD_CAPTURE_TEST_HOOK__==='function')window.__APT_LEAD_CAPTURE_TEST_HOOK__({text,safePath,safeHost,campaignText,attributionRecord,attribution,analyticsAllowed,eventParams,chooseRequest,validReceipt,send,payloadFor,emitConfirmed,FORM_IDS,LIMITS});
})();
