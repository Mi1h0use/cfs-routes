// i18n.js — locale detection and translation module
//
// Usage:
//   await i18n.init()          — call once before rendering; detects locale,
//                                fetches strings, applies data-i18n* to DOM
//   i18n.t('key')              — returns translated string (falls back to key)
//   i18n.t('key', { a: 'x' }) — returns string with {a} replaced by 'x'
//   i18n.locale                — detected locale code ('en' | 'fr')
//
// HTML attributes applied by _applyToDOM():
//   data-i18n="key"            → el.textContent
//   data-i18n-title="key"      → el.title
//   data-i18n-aria-label="key" → el.setAttribute('aria-label', ...)
//   data-help-topic="x"        → updates data-help-title + aria-label
//                                via key "help.x.title" (if present)
//
// Supported locales: 'en', 'fr'. Any other navigator.language falls back to 'en'.

const i18n = (() => {
  let _strings = {};
  let _locale = 'en';

  function detectLocale() {
    const lang = (navigator.language || 'en').slice(0, 2).toLowerCase();
    return lang === 'fr' ? 'fr' : 'en';
  }

  async function init() {
    _locale = detectLocale();

    try {
      const res = await fetch(`/static/i18n/${_locale}.json`);
      if (res.ok) _strings = await res.json();
    } catch {}

    if (!Object.keys(_strings).length && _locale !== 'en') {
      try {
        const res = await fetch('/static/i18n/en.json');
        if (res.ok) _strings = await res.json();
        _locale = 'en';
      } catch {}
    }

    document.documentElement.lang = _locale;
    _applyToDOM();
    return _locale;
  }

  function t(key, vars) {
    let str = _strings[key] ?? key;
    if (vars) str = str.replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? ''));
    return str;
  }

  function _applyToDOM() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      el.textContent = t(el.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      el.title = t(el.dataset.i18nTitle);
    });
    document.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
      el.setAttribute('aria-label', t(el.dataset.i18nAriaLabel));
    });
    document.querySelectorAll('[data-help-topic]').forEach(el => {
      const key = `help.${el.dataset.helpTopic}.title`;
      const val = t(key);
      if (val !== key) {
        el.dataset.helpTitle = val;
        el.setAttribute('aria-label', val);
      }
    });
    document.title = t('app.title');
  }

  return { init, t, get locale() { return _locale; } };
})();
