(() => {
  const site = 'https://www.aptredlight.com';
  const page = '/cms/homepage-factory-video-library/';
  const player = document.getElementById('apt-hero-video');
  const toggle = document.getElementById('apt-hero-toggle');
  const chapters = [...document.querySelectorAll('[data-hero-chapter]')];
  if (!player || !toggle || !chapters.length || !window.matchMedia) return;
  const preferences = window.matchMedia('(min-width: 801px) and (prefers-reduced-motion: no-preference)');
  const allowedUrl = (raw) => {
    try { const u = new URL(raw, site);
      return u.origin === site && /^\/cms\/wp-content\/uploads\/\d{4}\/\d{2}\/[^/]+\.mp4$/i.test(u.pathname) && !u.search && !u.hash ? u.href : '';
    } catch { return ''; }
  };
  const sources = chapters.map(x => allowedUrl(x.href));
  if (sources.some(x => !x)) return;
  let index=0, started=false, userPaused=false, manual=false, failed=false, serial=0, failures=0;
  const autoAllowed = () => preferences.matches && !navigator.connection?.saveData && !document.hidden;
  const label = () => {
    toggle.textContent = player.paused ? 'Play homepage videos' : 'Pause homepage videos';
    toggle.href = sources[index];
  };
  const activate = i => {
    index=i;
    chapters.forEach((x,n)=>n===index ? x.setAttribute('aria-current','true') : x.removeAttribute('aria-current'));
    label();
  };
  const hide = () => {++serial;player.pause();player.hidden=true;label();};
  const start = (i, restart=false) => {
    if(document.hidden || (!manual && !autoAllowed())) return;
    const turn=++serial, previous=player.getAttribute('src');
    activate(i);
    player.muted=true;
    player.loop=false;
    if(previous!==sources[i]) player.src=sources[i];
    else if(restart) player.currentTime=0;
    Promise.resolve(player.play()).then(()=>{
      if(turn!==serial) return;
      if(userPaused || document.hidden || (!manual && !autoAllowed())) return hide();
      failed=false; failures=0; started=true;player.hidden=false;label();
    }).catch((err)=>{
      if(turn!==serial) return;
      if(err?.name==='NotSupportedError') return skip();
      hide();
      if(manual) failed=true;
    });
  };
  const skip = () => {
    if(++failures >= sources.length || userPaused || manual || !autoAllowed()){failed=true;return hide();}
    start((index+1)%sources.length,true);
  };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 4200);
  const resolved = location.origin === site ? fetch(page,{credentials:'omit',cache:'no-cache',signal:controller.signal})
    .then(r=>r.ok?r.text():'').then(html=>{
      const doc=new DOMParser().parseFromString(html,'text/html');
      const managed=allowedUrl(doc.querySelector('main .wp-block-cover video')?.getAttribute('src'));
      if(managed){sources[0]=managed;chapters[0].href=managed;if(index===0)label();}
    }).catch(()=>{}).finally(()=>clearTimeout(timer)) : Promise.resolve();
  if(location.origin !== site) clearTimeout(timer);
  const auto=async()=>{
    if(!autoAllowed() || userPaused || manual || !player.paused) return;
    if(!started)await Promise.race([resolved,new Promise(r=>setTimeout(r,1300))]);
    if(autoAllowed()&&!userPaused&&!manual&&player.paused)start(index);
  };
  const bindSpace = a=>{a.setAttribute('role','button');a.addEventListener('keydown',e=>{if(e.key===' '){e.preventDefault();a.click();}});};
  bindSpace(toggle);
  toggle.addEventListener('click',e=>{
    if(failed&&player.paused) return;
    e.preventDefault();
    manual=true;
    if(player.paused){userPaused=false;start(index);}
    else{++serial;userPaused=true;player.pause();label();}
  });
  chapters.forEach((a,i)=>{
    bindSpace(a);
    a.addEventListener('click',e=>{
      if(failed && i===index && player.paused) return;
      e.preventDefault();manual=true;userPaused=false;failures=0;failed=false;
      start(i,true);
      player.closest('.factory-hero')?.scrollIntoView({block:'start',behavior:'instant'});
    });
  });
  player.addEventListener('ended',()=>{if(!userPaused)start((index+1)%sources.length,true);});
  player.addEventListener('error', skip);
  const preference=()=>{if(!manual&&!autoAllowed())hide();else void auto();};
  if(preferences.addEventListener)preferences.addEventListener('change',preference);else preferences.addListener(preference);
  document.addEventListener('visibilitychange',()=>{if(document.hidden&&!manual)hide();else void auto();});
  void auto();
})();
