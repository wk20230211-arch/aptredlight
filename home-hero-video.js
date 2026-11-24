(() => {
  const site = 'https://www.aptredlight.com';
  const page = '/cms/homepage-factory-video-library/';
  const previewFallback = site + '/cms/wp-content/uploads/2026/11/aptredlight-t300-home-hero-12s.mp4';
  const player = document.getElementById('apt-hero-video');
  const toggle = document.getElementById('apt-hero-toggle');
  if (!player || !toggle || !window.matchMedia) return;
  const preferences = window.matchMedia('(min-width: 801px) and (prefers-reduced-motion: no-preference)');
  let media = '', loaded = false, pausedByVisitor = false;
  const permitted = (raw) => {
    try { const u = new URL(raw, site);
      return u.origin === site && /^\/cms\/wp-content\/uploads\/\d{4}\/\d{2}\/[^/]+\.mp4$/i.test(u.pathname) && !u.search && !u.hash ? u.href : '';
    } catch { return ''; }
  };
  const findMedia = async () => {
    if (location.origin !== site) return previewFallback;
    const result = await fetch(page, { credentials: 'omit', cache: 'no-cache', signal: AbortSignal.timeout(5000) });
    if (!result.ok) return '';
    const html = new DOMParser().parseFromString(await result.text(), 'text/html');
    return permitted(html.querySelector('main .wp-block-cover video')?.getAttribute('src'));
  };
  const hide = () => { player.pause(); player.hidden = true; toggle.hidden = true; };
  const start = async () => {
    if (!preferences.matches || navigator.connection?.saveData || pausedByVisitor || document.hidden) return;
    try {
      if (!media) media = await findMedia();
      if (!media || !preferences.matches || document.hidden) return;
      if (!loaded) { player.src = media; loaded = true; }
      player.muted = true;
      await player.play();
      if (!preferences.matches) return hide();
      player.hidden = false; toggle.hidden = false; toggle.textContent = 'Pause background video';
    } catch { hide(); }
  };
  toggle.addEventListener('click', () => {
    if (player.paused) { pausedByVisitor = false; void start(); }
    else { pausedByVisitor = true; player.pause(); toggle.textContent = 'Play background video'; }
  });
  preferences.addEventListener('change', () => preferences.matches ? void start() : hide());
  document.addEventListener('visibilitychange', () => document.hidden ? hide() : void start());
  player.addEventListener('error', hide);
  void start();
})();
