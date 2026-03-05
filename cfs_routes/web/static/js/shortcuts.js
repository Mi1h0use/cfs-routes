// ─────────────────────────────────────────────────────────
// Leader key
// Press Escape to activate, then a bound key to run the action.
// ─────────────────────────────────────────────────────────
let leaderActive = false;
let leaderTimer = null;

const LEADER_KEYS = {
  '1': () => focusRowInput(0),
  '2': () => focusRowInput(1),
  '3': () => focusRowInput(2),
  '4': () => focusRowInput(3),
  '5': () => focusRowInput(4),
  '6': () => focusRowInput(5),
  '7': () => focusRowInput(6),
  '8': () => focusRowInput(7),
  '9': () => focusRowInput(8),
  '0': () => focusRowInput(9),
};

function focusRowInput(idx) {
  const inputs = Array.from(document.querySelectorAll('#rows-container input[type="text"]'));
  if (inputs[idx]) inputs[idx].focus();
}

function activateLeader() {
  leaderActive = true;
  clearTimeout(leaderTimer);
  leaderTimer = setTimeout(() => { leaderActive = false; }, 1500);
}

// ─────────────────────────────────────────────────────────
// Keyboard shortcuts
// ─────────────────────────────────────────────────────────
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.key === 'k') {
    e.preventDefault();
    const modalSearch = document.getElementById('modal-search-input');
    if (modalSearch) { modalSearch.focus(); modalSearch.select(); return; }
    if (typeof fromChoices !== 'undefined' && fromChoices) fromChoices.showDropdown();
    return;
  }

  if (e.ctrlKey || e.altKey || e.metaKey) return;

  if (leaderActive) {
    clearTimeout(leaderTimer);
    leaderActive = false;
    const action = LEADER_KEYS[e.key];
    if (action) { e.preventDefault(); action(); }
    return;
  }

  if (e.key === 'Escape') {
    if (document.querySelector('.modal.show')) return;
    if (typeof fromChoices !== 'undefined' && fromChoices &&
        fromChoices.containerOuter.element.classList.contains('is-open')) return;
    activateLeader();
  }
});
