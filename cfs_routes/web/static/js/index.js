// ─────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────
let bsModal = null;
let fromChoices = null;
let rows = [];
let nextRowId = 1;
let modalBodyOriginalHtml = '';
let airportsData = null;
let favoritesDirty = false;
const firByLabel = new Map(); // group label -> FIR code, for the group heading star

// ─────────────────────────────────────────────────────────
// SessionStorage persistence
// ─────────────────────────────────────────────────────────
const SESSION_KEY = 'cfs_rows';

function saveSession() {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify({ rows, nextRowId }));
}

function restoreSession() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(SESSION_KEY));
    if (!saved || !Array.isArray(saved.rows)) return;
    rows = saved.rows;
    nextRowId = saved.nextRowId || rows.length + 1;
    if (rows.length) renderRows();
  } catch {
    // corrupt data — ignore
  }
}

// ─────────────────────────────────────────────────────────
// Favorite airports and FIRs (localStorage)
// ─────────────────────────────────────────────────────────
const FAV_KEYS = { airport: 'cfs_favorites', fir: 'cfs_favorite_firs' };
const favorites = { airport: loadFavorites(FAV_KEYS.airport), fir: loadFavorites(FAV_KEYS.fir) };

function loadFavorites(key) {
  try {
    const saved = JSON.parse(localStorage.getItem(key));
    return new Set(Array.isArray(saved) ? saved : []);
  } catch {
    return new Set();
  }
}

function saveFavorites(kind) {
  try {
    localStorage.setItem(FAV_KEYS[kind], JSON.stringify([...favorites[kind]]));
  } catch {
    // storage unavailable — favorites last for this page only
  }
}

function makeStar(kind, code) {
  const star = document.createElement('i');
  star.className = 'fav-star bi';
  star.dataset.favKind = kind;
  star.dataset.fav = code;
  setStarState(star, favorites[kind].has(code));
  return star;
}

function setStarState(star, isFav) {
  star.classList.toggle('bi-star', !isFav);
  star.classList.toggle('bi-star-fill', isFav);
  star.classList.toggle('is-fav', isFav);
  star.title = i18n.t(isFav ? 'airports.favorite_remove' : 'airports.favorite_add');
}

function toggleFavorite(star) {
  const { favKind: kind, fav: code } = star.dataset;
  const isFav = !favorites[kind].has(code);
  if (isFav) favorites[kind].add(code); else favorites[kind].delete(code);
  saveFavorites(kind);
  setStarState(star, isFav);
  // Re-sort on close so the list doesn't jump under the cursor
  favoritesDirty = true;
}

// ─────────────────────────────────────────────────────────
// Boot
// ─────────────────────────────────────────────────────────
async function boot() {
  await i18n.init();
  bsModal = new bootstrap.Modal(document.getElementById('route-modal'));
  HelpModal.init();
  initChoices();
  await Promise.all([loadCycle(), loadAirports()]);
  restoreSession();

  const modalBody = document.getElementById('modal-body');
  modalBody.addEventListener('input', e => {
    if (e.target.id === 'modal-search-input') applyModalSearch(e.target.value);
  });
  modalBody.addEventListener('click', e => {
    const row = e.target.closest('.route-row');
    // Let the user select part of a route without triggering a copy
    if (row && !window.getSelection().toString()) copyRoute(row);
  });
  modalBody.addEventListener('keydown', e => {
    const row = e.target.closest('.route-row');
    if (row && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); copyRoute(row); }
  });
}

async function loadCycle() {
  try {
    const res = await fetch('/api/cycles/current');
    if (res.status === 404) {
      document.getElementById('cycle-badge').textContent = i18n.t('cycle.unavailable');
      return;
    }
    if (!res.ok) throw new Error(res.status);
    const cycle = await res.json();
    const eff = new Date(cycle.effective).toLocaleDateString(i18n.locale, { month: 'short', day: 'numeric' });
    document.getElementById('cycle-badge').textContent = i18n.t('cycle.label', { ident: cycle.ident, date: eff });
  } catch {
    document.getElementById('cycle-badge').textContent = i18n.t('cycle.error');
  }
}

function initChoices() {
  const sel = document.getElementById('from-select');
  fromChoices = new Choices(sel, {
    searchEnabled: true,
    searchPlaceholderValue: i18n.t('airports.search_placeholder'),
    shouldSort: false,
    itemSelectText: '',
    callbackOnCreateTemplates: () => ({
      choice(...args) {
        const el = Choices.defaults.templates.choice.call(this, ...args);
        const choice = args[1];
        if (!choice.placeholder && choice.value) el.appendChild(makeStar('airport', choice.value));
        return el;
      },
      choiceGroup(...args) {
        const el = Choices.defaults.templates.choiceGroup.call(this, ...args);
        const fir = firByLabel.get(args[1].label);
        if (fir) el.querySelector('.choices__heading').appendChild(makeStar('fir', fir));
        return el;
      },
    }),
  });

  fromChoices.input.element.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      setTimeout(() => document.getElementById('add-row-btn').click(), 0);
    }
  });

  // Choices selects on mousedown/Enter via capture listeners on its container;
  // a capture listener on document runs first, so the star can swallow the event.
  document.addEventListener('mousedown', (e) => {
    const star = e.target instanceof Element && e.target.closest('[data-fav]');
    if (!star) return;
    e.preventDefault();
    e.stopPropagation();
    toggleFavorite(star);
  }, true);
  document.addEventListener('click', (e) => {
    if (e.target instanceof Element && e.target.closest('[data-fav]')) e.stopPropagation();
  }, true);
  document.addEventListener('keydown', (e) => {
    if (e.target !== fromChoices.input.element || e.key !== 'Enter' || !e.shiftKey) return;
    const star = fromChoices.dropdown.element.querySelector('.is-highlighted [data-fav]');
    if (!star) return;
    e.preventDefault();
    e.stopPropagation();
    toggleFavorite(star);
  }, true);

  fromChoices.passedElement.element.addEventListener('hideDropdown', () => {
    if (!favoritesDirty) return;
    favoritesDirty = false;
    renderAirportChoices();
  });
}

async function loadAirports() {
  try {
    const res = await fetch('/api/airports');
    if (!res.ok) throw new Error(res.status);
    airportsData = await res.json();
    renderAirportChoices();
  } catch (e) {
    console.error('Failed to load airports', e);
  }
}

function renderAirportChoices() {
  if (!airportsData) return;
  const toChoice = ap => ({ value: ap.icao, label: `${ap.icao} — ${ap.name}`, labelClass: 'fav-label' });
  const favFirst = (set, key) => (a, b) => set.has(key(b)) - set.has(key(a));

  // Favorite FIRs first, then by name; within a FIR, favorite airports first (sort is stable)
  firByLabel.clear();
  const groups = Object.entries(airportsData.firs)
    .map(([fir, airports]) => {
      const firKey = 'fir.' + fir;
      const label = i18n.t(firKey) !== firKey ? i18n.t(firKey) : fir;
      firByLabel.set(label, fir);
      return { fir, label, airports };
    })
    .sort((a, b) => favFirst(favorites.fir, g => g.fir)(a, b) || a.label.localeCompare(b.label, i18n.locale))
    .map(({ label, airports }) => ({
      label,
      choices: [...airports].sort(favFirst(favorites.airport, ap => ap.icao)).map(toChoice),
    }));

  const current = fromChoices.getValue(true);
  fromChoices.setChoices(groups, 'value', 'label', true);
  if (current) fromChoices.setChoiceByValue(current);
}

// ─────────────────────────────────────────────────────────
// Row management
// ─────────────────────────────────────────────────────────
document.getElementById('add-row-btn').addEventListener('click', () => {
  const sel = document.getElementById('from-select');
  const icao = sel.value;
  if (!icao) return;

  const id = nextRowId++;
  rows.push({ id, from: icao, to: '' });
  saveSession();
  renderRows();
});

function renderRows() {
  const container = document.getElementById('rows-container');
  container.innerHTML = '';

  rows.forEach(row => {
    const card = document.createElement('div');
    card.className = 'card mb-2';
    card.dataset.id = row.id;

    const body = document.createElement('div');
    body.className = 'card-body py-2 px-3 d-flex align-items-center gap-2 flex-wrap';

    const fromLabel = document.createElement('span');
    fromLabel.className = 'from-label font-mono fw-bold text-primary';
    fromLabel.textContent = row.from;

    const arrow = document.createElement('i');
    arrow.className = 'bi bi-arrow-right text-secondary';

    const toInput = document.createElement('input');
    toInput.type = 'text';
    toInput.className = 'form-control form-control-sm';
    toInput.style.width = '130px';
    toInput.placeholder = i18n.t('form.destination_placeholder');
    toInput.value = row.to;
    toInput.autocomplete = 'off';
    toInput.spellcheck = false;
    toInput.addEventListener('focus', e => { e.target.select(); });
    toInput.addEventListener('input', e => { row.to = e.target.value.trim().toUpperCase(); saveSession(); });
    toInput.addEventListener('keydown', e => {
      if (e.key === 'Enter') { doSearch(row); return; }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        const inputs = Array.from(document.querySelectorAll('#rows-container input[type="text"]'));
        const next = inputs[inputs.indexOf(e.target) + (e.key === 'ArrowDown' ? 1 : -1)];
        if (next) next.focus();
      }
    });

    const searchBtn = document.createElement('button');
    searchBtn.className = 'btn btn-sm btn-outline-secondary';
    searchBtn.title = i18n.t('btn.search');
    searchBtn.innerHTML = '<i class="bi bi-search"></i>';
    searchBtn.addEventListener('click', () => doSearch(row));

    const removeBtn = document.createElement('button');
    removeBtn.className = 'btn btn-sm btn-outline-danger';
    removeBtn.title = i18n.t('btn.remove');
    removeBtn.innerHTML = '<i class="bi bi-x-lg"></i>';
    removeBtn.addEventListener('click', () => {
      rows = rows.filter(r => r.id !== row.id);
      saveSession();
      renderRows();
    });

    body.append(fromLabel, arrow, toInput, searchBtn, removeBtn);
    card.appendChild(body);
    container.appendChild(card);

    if (row.to === '') toInput.focus();
  });
}

// ─────────────────────────────────────────────────────────
// Search
// ─────────────────────────────────────────────────────────
const CARDINALS = new Set(['N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW']);

async function doSearch(row) {
  const from = row.from;
  const to = (row.to || '').trim().toUpperCase();
  if (!to) return;

  openModal(`${from} → ${to}`, `<p class="text-secondary small"><span class="spinner-border spinner-border-sm me-1"></span>${i18n.t('ui.loading')}</p>`);

  try {
    const url = CARDINALS.has(to)
      ? `/api/routes?from=${encodeURIComponent(from)}&direction=${encodeURIComponent(to)}`
      : `/api/routes?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`;

    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      openModal(`${from} → ${to}`, `<p class="text-danger small">${escHtml(err.detail || 'API error')}</p>`);
      return;
    }

    renderResults(from, to, await res.json());
  } catch (e) {
    openModal(`${from} → ${to}`, `<p class="text-danger small">Network error: ${escHtml(e.message)}</p>`);
  }
}

function renderRouteGroups(routes) {
  let html = '';
  const groups = groupRoutes(routes);
  for (const [label, items] of groups) {
    const labelKey = 'route.label.' + label;
    const displayLabel = i18n.t(labelKey) !== labelKey ? i18n.t(labelKey) : label;
    html += `<div class="mb-3">
      <div class="text-uppercase text-secondary small fw-bold border-bottom pb-1 mb-2" style="font-size:0.7rem;letter-spacing:.08em">${escHtml(displayLabel)}</div>`;
    items.forEach(r => {
      const proc = r.procedure ? `<span class="route-pill badge text-bg-primary">${escHtml(r.procedure)}</span>` : '';
      const ovfl = r.direction_type === 'OVFL' ? '<span class="text-secondary">⟷ OVFL</span>' : '';
      html += `<div class="route-row font-mono small" role="button" tabindex="0" data-route="${escHtml(r.route)}" title="${escHtml(i18n.t('route.click_to_copy'))}">
        ${ovfl}${proc}<span class="route-text">${escHtml(r.route)}</span>
        <span class="route-lims">${limitationPills(r.limitations)}</span>
      </div>`;
    });
    html += '</div>';
  }
  return html;
}

function renderFallbackAccordion(routes, preferredDir) {
  const byDir = new Map();
  routes.forEach(r => {
    const key = r.direction || '?';
    if (!byDir.has(key)) byDir.set(key, []);
    byDir.get(key).push(r);
  });

  if (byDir.size === 0) {
    return `<p class="text-center text-secondary py-4 mb-0">${i18n.t('route.no_mandatory')}</p>`;
  }

  const openDir = (preferredDir && byDir.has(preferredDir)) ? preferredDir : byDir.keys().next().value;

  let html = '<div class="accordion">';
  let i = 0;
  for (const [dir, items] of byDir) {
    const panelId = `fb-acc-${i}`;
    const isOpen = dir === openDir;
    html += `<div class="accordion-item">
      <h2 class="accordion-header">
        <button class="accordion-button${isOpen ? '' : ' collapsed'} py-2 font-mono small" type="button"
            data-bs-toggle="collapse" data-bs-target="#${panelId}">
          TO ${escHtml(dir)}
          <span class="badge text-bg-secondary ms-2">${items.length}</span>
        </button>
      </h2>
      <div id="${panelId}" class="accordion-collapse collapse${isOpen ? ' show' : ''}">
        <div class="accordion-body py-2">${renderRouteGroups(items)}</div>
      </div>
    </div>`;
    i++;
  }
  html += '</div>';
  return html;
}

function renderResults(from, to, data) {
  const routes = (data.routes || []).filter(r => r.direction_type !== 'ARR');
  let html = '';

  if (data.fallback) {
    html += `<div class="alert alert-info py-2 small mb-3" role="alert">${i18n.t('route.fallback_notice', { from: escHtml(from), to: escHtml(to) })}</div>`;
    html += `<input type="search" class="form-control form-control-sm font-mono mb-3" id="modal-search-input" autocomplete="off" spellcheck="false" placeholder="${escHtml(i18n.t('modal.search_placeholder'))}">`;
    html += renderFallbackAccordion(routes, data.preferred_direction || null);
  } else if (routes.length === 0) {
    html += `<p class="text-center text-secondary py-4 mb-0">${i18n.t('route.no_mandatory')}</p>`;
  } else {
    html += renderRouteGroups(routes);
  }

  const title = to + (data.to_airport_name ? ` - ${data.to_airport_name}` : '');
  openModal(title, html);
}

function groupRoutes(routes) {
  const map = new Map();
  routes.forEach(r => {
    const cat = routeCategory(r);
    if (!map.has(cat)) map.set(cat, []);
    map.get(cat).push(r);
  });

  const order = ['HIGH', 'LOW', 'HIGH & LOW'];
  const sorted = new Map();
  order.forEach(k => { if (map.has(k)) sorted.set(k, map.get(k)); });
  map.forEach((v, k) => { if (!sorted.has(k)) sorted.set(k, v); });

  return sorted;
}

function routeCategory(r) {
  const alt = r.altitude || '';
  const dir = r.direction_type;

  let label = alt === 'H' ? 'HIGH' : alt === 'L' ? 'LOW' : alt === 'H&L' ? 'HIGH & LOW' : alt;

  if (dir === 'ARR') label = 'ARR ' + label;
  if (dir === 'OVFL') label = 'OVFLT';

  return label;
}

// Limitations are comma-separated, e.g. "NONJET, MAX F220" -> two pills.
function limitationPills(limitations) {
  if (!limitations) return '';
  return limitations.split(',').map(s => s.trim()).filter(Boolean).map(part => {
    const norm = part.toUpperCase().replace(/\s+/g, '');
    const cls = norm.startsWith('NONJET') ? 'text-bg-success'
              : norm.startsWith('JET') ? 'text-bg-warning'
              : 'text-bg-secondary';
    return `<span class="route-pill badge ${cls}">${escHtml(part)}</span>`;
  }).join('');
}

// ─────────────────────────────────────────────────────────
// Modal
// ─────────────────────────────────────────────────────────
function openModal(title, bodyHtml) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = bodyHtml;
  modalBodyOriginalHtml = bodyHtml;
  bsModal.show();
}

function applyModalSearch(query) {
  const body = document.getElementById('modal-body');
  body.innerHTML = modalBodyOriginalHtml;

  const inp = document.getElementById('modal-search-input');
  if (inp) {
    inp.value = query;
    if (query.trim()) { inp.focus(); inp.setSelectionRange(query.length, query.length); }
  }

  if (!query.trim()) return;

  new Mark(body).mark(query.trim(), { separateWordSearch: false, className: 'search-highlight' });

  body.querySelectorAll('.accordion-item').forEach(item => {
    const hasMatch = item.querySelector('mark.search-highlight') !== null;
    item.querySelector('.accordion-collapse').classList.toggle('show', hasMatch);
    item.querySelector('.accordion-button').classList.toggle('collapsed', !hasMatch);
  });
}

async function copyRoute(row) {
  const text = row.dataset.route;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // Clipboard API is unavailable outside secure contexts (plain http).
    // The textarea must live inside the modal: Bootstrap's focus trap steals focus from anything outside it.
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    row.closest('.modal').appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    row.focus();
    if (!ok) return;
  }
  row.classList.add('copied');
  setTimeout(() => row.classList.remove('copied'), 800);
}

// ─────────────────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ─────────────────────────────────────────────────────────
// Init
// ─────────────────────────────────────────────────────────
boot();
