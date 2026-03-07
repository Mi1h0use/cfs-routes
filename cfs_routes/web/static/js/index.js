// ─────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────
let bsModal = null;
let fromChoices = null;
let rows = [];
let nextRowId = 1;
let modalBodyOriginalHtml = '';

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
// Boot
// ─────────────────────────────────────────────────────────
async function boot() {
  await i18n.init();
  bsModal = new bootstrap.Modal(document.getElementById('route-modal'));
  HelpModal.init();
  initChoices();
  await Promise.all([loadCycle(), loadAirports()]);
  restoreSession();

  document.getElementById('modal-body').addEventListener('input', e => {
    if (e.target.id === 'modal-search-input') applyModalSearch(e.target.value.trim());
  });
}

async function loadCycle() {
  try {
    const res = await fetch('/api/cycles');
    if (!res.ok) throw new Error(res.status);
    const cycles = await res.json();
    const parsed = cycles.find(c => c.status === 'parsed');
    if (parsed) {
      const eff = new Date(parsed.effective).toLocaleDateString(i18n.locale, { month: 'short', day: 'numeric' });
      document.getElementById('cycle-badge').textContent = i18n.t('cycle.label', { ident: parsed.ident, date: eff });
    } else {
      document.getElementById('cycle-badge').textContent = i18n.t('cycle.unavailable');
    }
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
  });

  fromChoices.input.element.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      setTimeout(() => document.getElementById('add-row-btn').click(), 0);
    }
  });
}

async function loadAirports() {
  try {
    const res = await fetch('/api/airports');
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();

    const groups = Object.entries(data.firs).sort().map(([fir, airports]) => {
      const firKey = 'fir.' + fir;
      const label = i18n.t(firKey) !== firKey ? i18n.t(firKey) : fir;
      return {
        label,
        choices: airports.map(ap => ({ value: ap.icao, label: `${ap.icao} — ${ap.name}` })),
      };
    });

    fromChoices.setChoices(groups, 'value', 'label', true);
  } catch (e) {
    console.error('Failed to load airports', e);
  }
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
      const proc = r.procedure ? `<span class="route-proc badge text-bg-primary me-2">${escHtml(r.procedure)}</span>` : '';
      const lim = r.limitations ? `<span class="route-lim text-secondary ms-2">(${escHtml(r.limitations)})</span>` : '';
      const ovfl = r.direction_type === 'OVFL' ? '<span class="text-secondary me-1">⟷ OVFL</span>' : '';
      html += `<div class="font-mono small py-1">${ovfl}${proc}${escHtml(r.route)}${lim}</div>`;
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
  const lim = (r.limitations || '').toUpperCase();
  const dir = r.direction_type;

  let label = alt === 'H' ? 'HIGH' : alt === 'L' ? 'LOW' : alt === 'H&L' ? 'HIGH & LOW' : alt;

  if (dir === 'ARR') label = 'ARR ' + label;
  if (dir === 'OVFL') label = 'OVFLT';

  if (lim.includes('NONJET')) label += ' (NONJET)';
  else if (lim.includes('JET')) label += ' (JET)';

  return label;
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
    if (query) { inp.focus(); inp.setSelectionRange(query.length, query.length); }
  }

  if (!query) return;

  new Mark(body).mark(query, { separateWordSearch: false, className: 'search-highlight' });

  body.querySelectorAll('.accordion-item').forEach(item => {
    const hasMatch = item.querySelector('mark.search-highlight') !== null;
    item.querySelector('.accordion-collapse').classList.toggle('show', hasMatch);
    item.querySelector('.accordion-button').classList.toggle('collapsed', !hasMatch);
  });
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
