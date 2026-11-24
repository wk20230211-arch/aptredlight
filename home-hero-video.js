(() => {
  const site = 'https://www.aptredlight.com';
  const page = '/cms/homepage-factory-video-library/';
  const player = document.getElementById('apt-hero-video');
  const toggle = document.getElementById('apt-hero-toggle');
  if (!player || !toggle || !window.matchMedia) return;
  const fallback = toggle.href;
  const preferences = window.matchMedia('(min-width: 801px) and (prefers-reduced-motion: no-preference)');
  const permitted = (raw) => {
    try { const u = new URL(raw, site);
      return u.origin === site && /^\/cms\/wp-content\/uploads\/\d{4}\/\d{2}\/[^/]+\.mp4$/i.test(u.pathname) && !u.search && !u.hash ? u.href : '';
    } catch { return ''; }
  };
  let media = '', visitor = false, manual = false, failed = false, pending = false;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 4200);
  const resolved = location.origin === site ? fetch(page, {credentials:'omit',cache:'no-cache',signal:controller.signal})
    .then(r => r.ok ? r.text() : '')
    .then(markup => {
      const doc = new DOMParser().parseFromString(markup,'text/html');
      media = permitted(doc.querySelector('main .wp-block-cover video')?.getAttribute('src'));
      if(media) toggle.href = media;
      return media;
    }).catch(()=> '').finally(() => clearTimeout(timer)) : Promise.resolve('');
  if(location.origin !== site) clearTimeout(timer);
  const autoAllowed = () => preferences.matches && !navigator.connection?.saveData && !document.hidden;
  const label = () => { toggle.textContent = player.paused ? 'Play homepage video' : 'Pause homepage video'; };
  const hide = () => { player.pause();player.hidden = true;label(); };
  const start = (source) => {
    if (pending) return;
    pending = true;
    player.muted = true;
    if (!player.getAttribute('src')) player.src = source;
    Promise.resolve(player.play()).then(() => {
      if (document.hidden || (!manual && !autoAllowed())) return hide();
      player.hidden = false;
      label();
    }).catch(() => { hide(); if(manual) failed = true; }).finally(() => { pending = false; });
  };
  toggle.setAttribute('role','button');
  toggle.addEventListener('keydown',e=>{if(e.key===' '){e.preventDefault();toggle.click();}});
  toggle.addEventListener('click',(event) => {
    if (failed && player.paused) return;
    event.preventDefault();
    visitor = true; manual = true;
    if (player.paused) start(media || fallback);
    else { player.pause();label(); }
  });
  const auto = async () => {
    if (!autoAllowed() || visitor || !player.paused) return;
    await Promise.race([resolved,new Promise(r=>setTimeout(r,1400))]);
    if (!visitor && autoAllowed() && player.paused) start(media || fallback);
  };
  const onPreference = () => {if(!manual && !autoAllowed()) hide(); else void auto();};
  if(preferences.addEventListener) preferences.addEventListener('change',onPreference);
  else preferences.addListener(onPreference);
  document.addEventListener('visibilitychange',() => { if(document.hidden && !manual) hide(); else void auto(); });
  player.addEventListener('error',()=>{failed=true;hide();});
  void auto();
})();
