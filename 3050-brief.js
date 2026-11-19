(() => {
  const intents = new Map([
    ['documents', 'Documentation scope & quotation'],
    ['sample', 'Sample evaluation'],
    ['oem', 'Private-label OEM/ODM brief']
  ]);
  const storageKey = 'apt-3050-enquiry-draft';
  const query = new URLSearchParams(location.search);
  const brief = document.getElementById('apt-3050-brief');
  function message(draft) {
    return ['3050 ULTRA | ' + intents.get(draft.intent), 'Target market: ' + draft.market,
      'Estimated quantity: ' + draft.units + ' units', draft.format && 'Format: ' + draft.format,
      draft.notes && 'Project notes: ' + draft.notes].filter(Boolean).join('\n');
  }
  if (brief) {
    const selectIntent = hash => {
      const radio = brief.querySelector('label' + hash + ' input[type="radio"]');
      if (radio) radio.checked = true;
    };
    const validHash = hash => ['#apt-inquiry-doc', '#apt-inquiry-sample', '#apt-inquiry-oem'].includes(hash);
    if (validHash(location.hash)) selectIntent(location.hash);
    window.addEventListener('hashchange', () => {
      if (validHash(location.hash)) selectIntent(location.hash);
    });
    document.addEventListener('click', event => {
      const anchor = event.target.closest('a[href]');
      if (anchor && validHash(anchor.getAttribute('href'))) selectIntent(anchor.hash);
    });
    brief.addEventListener('submit', event => {
      event.preventDefault();
      const fields = new FormData(brief);
      const draft = Object.fromEntries(['intent','market','units','format','notes'].map(k => [k, String(fields.get(k) || '').trim()]));
      if (!draft.market) { brief.elements.market.focus(); return; }
      if (event.submitter?.dataset.briefChannel === 'web') {
        try {
          sessionStorage.setItem(storageKey, JSON.stringify(draft));
        } catch {
          const fallback = brief.querySelector('[data-manual-brief]');
          fallback.hidden = false;
          fallback.querySelector('textarea').value = message(draft);
          fallback.querySelector('textarea').focus();
          return;
        }
        location.assign('/?product=3050-ultra&brief=' + draft.intent + '#contact');
      } else {
        location.assign('https://wa.me/8618823435519?text=' + encodeURIComponent(message(draft)));
      }
    });
    brief.querySelectorAll('[data-brief-channel]').forEach(button => { button.hidden = false; });
    return;
  }
  const enquiry = document.getElementById('inquiry');
  if (!enquiry || query.get('product') !== '3050-ultra' || !intents.has(query.get('brief'))) return;
  try {
    const draft = JSON.parse(sessionStorage.getItem(storageKey));
    if (!draft || draft.intent !== query.get('brief') || !draft.market || !/^\d{1,8}$/.test(draft.units)) return;
    const quantity = enquiry.elements.quantity;
    const units = draft.units + ' units';
    const option = new Option(units, units);
    quantity.add(option);
    quantity.value = units;
    enquiry.elements.country.value = draft.market;
    enquiry.elements.message.value = message(draft);
    const product = [...enquiry.elements.product.options].find(item => item.textContent.startsWith('3050 ULTRA'));
    if (product) enquiry.elements.product.value = product.value;
    sessionStorage.removeItem(storageKey);
  } catch { /* The normal enquiry remains available if a draft has expired. */ }
})();
