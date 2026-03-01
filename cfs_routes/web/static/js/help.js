// help.js — reusable help modal module
//
// Usage:
//   HelpModal.init()                          — call once after DOM ready
//   HelpModal.open('topic', 'Title')          — open programmatically
//   HelpModal.createButton('topic', options)  — returns a <button> element
//
// createButton options:
//   iconType    'specific' (bi-patch-question-fill) | 'general' (bi-book-fill)
//   title       Modal heading text (also used as aria-label when no label)
//   label       Optional visible text appended after the icon
//   extraClasses  Additional CSS classes for the button
//
// Declarative (data-attribute) usage:
//   <button data-help-topic="my-topic" data-help-title="My Title" ...>
//
// Content is loaded from /static/help/{topic}.html

const HelpModal = (() => {
  const ICONS = {
    general:  'bi-book-fill',
    specific: 'bi-patch-question-fill',
  };

  let _bsModal  = null;
  let _titleEl  = null;
  let _bodyEl   = null;

  function init() {
    const el = document.getElementById('help-modal');
    _titleEl = document.getElementById('help-modal-title');
    _bodyEl  = document.getElementById('help-modal-body');
    _bsModal = new bootstrap.Modal(el);

    document.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-help-topic]');
      if (!btn) return;
      e.preventDefault();
      open(btn.dataset.helpTopic, btn.dataset.helpTitle || 'Help');
    });
  }

  function open(topic, title) {
    _titleEl.textContent = title || 'Help';
    _bodyEl.innerHTML = '<p class="text-secondary small">Loading\u2026</p>';
    _bsModal.show();
    fetch(`/static/help/${encodeURIComponent(topic)}.html`)
      .then(r => {
        if (!r.ok) throw new Error(`Help content not found: ${topic}`);
        return r.text();
      })
      .then(html => { _bodyEl.innerHTML = html; })
      .catch(err  => { _bodyEl.innerHTML = `<p class="text-danger small">${err.message}</p>`; });
  }

  function createButton(topic, { iconType = 'specific', title = 'Help', label = '', extraClasses = '' } = {}) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.dataset.helpTopic  = topic;
    btn.dataset.helpTitle  = title;
    btn.className = ['btn btn-sm btn-outline-secondary', extraClasses].filter(Boolean).join(' ');
    btn.innerHTML = `<i class="bi ${ICONS[iconType] || ICONS.specific}"></i>${label ? ` ${label}` : ''}`;
    if (!label) btn.setAttribute('aria-label', title);
    return btn;
  }

  return { init, open, createButton };
})();
