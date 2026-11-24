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
  toggle.hidden = false;
  let visible = !('IntersectionObserver' in window);
  let hovering = hoverable.matches && rail.matches(':hover');
  let touching = false;
  let paused = reduced.matches;
  let timer, settle;
  const offset = element => element.getBoundingClientRect().left - rail.getBoundingClientRect().left + rail.scrollLeft;
  const cycle = () => offset(repeat[0]) - offset(cards[0]);
  function updateToggle() {
    toggle.textContent = paused ? 'Play carousel' : 'Pause carousel';
    toggle.setAttribute('aria-label', (paused ? 'Play' : 'Pause') + ' industry carousel');
  }
  function canPlay() {
    return visible && !document.hidden && !hovering && !touching && !paused && !rail.contains(document.activeElement);
  }
  function schedule() {
    clearTimeout(timer);
    if (canPlay()) timer = setTimeout(() => step(1), 4000);
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
    schedule();
  }
  rail.addEventListener('scroll', () => {
    clearTimeout(timer);
    clearTimeout(settle);
    settle = setTimeout(() => {
      if (!touching) normalize();
      schedule();
    }, 150);
  }, { passive: true });
  rail.addEventListener('pointerenter', () => {
    if (hoverable.matches) hovering = true;
    schedule();
  });
  rail.addEventListener('pointerleave', () => { hovering = false; schedule(); });
  rail.addEventListener('touchstart', () => { touching = true; schedule(); }, { passive: true });
  for (const name of ['touchend', 'touchcancel']) {
    rail.addEventListener(name, event => { touching = event.touches.length > 0; schedule(); }, { passive: true });
  }
  rail.addEventListener('focusin', schedule);
  rail.addEventListener('focusout', () => setTimeout(schedule, 0));
  document.addEventListener('visibilitychange', schedule);
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
