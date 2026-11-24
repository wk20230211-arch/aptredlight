/* The English home industry rail only. */
(() => {
  'use strict';
  const section = document.getElementById('industry-application-planning');
  const rail = section?.querySelector('#afs-scenario-rail');
  const toggle = section?.querySelector('[data-industry-toggle]');
  const cards = rail ? [...rail.children] : [];
  if (!toggle || cards.length !== 6) return;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const hoverable = matchMedia('(hover: hover)');
  const repeat = cards.map(card => {
    const copy = card.cloneNode(true);
    copy.setAttribute('aria-hidden', 'true');
    copy.setAttribute('data-industry-copy', '');
    copy.querySelectorAll('a, button, input, select, textarea, [tabindex]').forEach(el => {
      el.tabIndex = -1;
    });
    return copy;
  });
  rail.append(...repeat);
  rail.setAttribute("data-industry-enhanced", "");
  toggle.hidden = false;
  let visible = !('IntersectionObserver' in window);
  let hovering = hoverable.matches && rail.matches(':hover');
  let touching = false;
  let paused = reduced.matches;
  let frame = 0, resumeTimer = 0, last = null, position = 0, length = 0, speed = 0;
  const offset = element => element.getBoundingClientRect().left - rail.getBoundingClientRect().left + rail.scrollLeft;
  const cycle = () => offset(repeat[0]) - offset(cards[0]);
  function updateToggle() {
    toggle.textContent = paused ? 'Play carousel' : 'Pause carousel';
    toggle.setAttribute('aria-label', (paused ? 'Play' : 'Pause') + ' industry carousel');
  }
  function canPlay() {
    return visible && !document.hidden && !hovering && !touching && !paused && !rail.contains(document.activeElement);
  }
  function stop() {
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    last = null;
  }
  function measure() {
    length = cycle();
    // Similar constant motion to the factory photo lane, with a brisker pace for these larger cards.
    speed = matchMedia('(max-width: 640px)').matches ? 36 : 48;
  }
  function animate(now) {
    if (!canPlay()) { stop(); return; }
    const elapsed = last === null ? 0 : Math.min(now - last, 64);
    last = now;
    position = (position + elapsed * speed / 1000) % length;
    rail.scrollLeft = position;
    frame = requestAnimationFrame(animate);
  }
  function schedule(delay = 0) {
    clearTimeout(resumeTimer);
    stop();
    if (!canPlay()) return;
    resumeTimer = setTimeout(() => {
      if (!canPlay()) return;
      measure();
      if (!(length > 0)) return;
      position = Math.max(0, rail.scrollLeft) % length;
      frame = requestAnimationFrame(animate);
    }, delay);
  }
  function jump(left) {
    // A same-frame seam reset must not inherit site-wide smooth scrolling.
    rail.scrollTo({ left, behavior: 'instant' });
  }
  function normalize() {
    const length = cycle();
    if (length > 0 && rail.scrollLeft >= length - 1) jump(Math.max(rail.scrollLeft - length, 0));
  }
  function step(direction) {
    stop();
    normalize();
    const length = cycle();
    if (length <= 0) return;
    const positions = cards.map(offset);
    const x = rail.scrollLeft;
    let target;
    if (direction > 0) {
      target = positions.find(p => p > x + 2) ?? length;
    } else {
      target = positions.slice().reverse().find(p => p < x - 2);
      if (target === undefined) {
        if (reduced.matches) target = positions[positions.length - 1];
        else {
          jump(length);
          target = positions[positions.length - 1];
        }
      }
    }
    rail.scrollTo({ left: target, behavior: reduced.matches ? 'instant' : 'smooth' });
    schedule(800);
  }
  rail.addEventListener('scroll', () => {
    // Ignore scroll events produced by our own frames; allow native swipe momentum to finish.
    if (!frame && !touching) schedule(280);
  }, { passive: true });
  rail.addEventListener('wheel', event => {
    if (Math.abs(event.deltaX) > 0 || event.shiftKey) schedule(450);
  }, { passive: true });
  rail.addEventListener('pointerenter', () => {
    if (hoverable.matches) { hovering = true; schedule(); }
  });
  rail.addEventListener('pointerleave', () => { hovering = false; schedule(180); });
  rail.addEventListener('touchstart', () => { touching = true; schedule(); }, { passive: true });
  for (const name of ['touchend', 'touchcancel']) {
    rail.addEventListener(name, event => { touching = event.touches.length > 0; schedule(320); }, { passive: true });
  }
  rail.addEventListener('focusin', () => schedule());
  rail.addEventListener('focusout', () => setTimeout(() => schedule(180), 0));
  document.addEventListener('visibilitychange', () => schedule());
  if ('ResizeObserver' in window) new ResizeObserver(() => schedule(120)).observe(rail);
  else window.addEventListener('resize', () => schedule(120), { passive: true });

  reduced.addEventListener('change', event => {
    paused = event.matches || paused;
    updateToggle();
    schedule();
  });
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      visible = entries.some(entry => entry.isIntersecting);
      schedule();
    });
    observer.observe(rail);
  }
  section.querySelectorAll('[data-industry-step]').forEach(button => {
    button.addEventListener('click', () => step(Number(button.dataset.industryStep)));
  });
  toggle.addEventListener('click', () => {
    paused = !paused;
    updateToggle();
    schedule();
  });
  updateToggle();
  schedule();
})();
