// =====================================================================================
// TABS AND START
// =====================================================================================
const TABS = { mix: ['Mix', 'mix'], music: ['Music', 'music'], vehicle: ['Vehicle', 'jet'], scene: ['Scene', 'scene'], takes: ['Takes', 'takes'] };
for (const [id, [label, glyph]] of Object.entries(TABS)) $('t-' + id).innerHTML = icon(glyph) + `<span>${label}</span>`;
function showTab(id) {
  if (!TABS[id]) id = 'mix';
  for (const name of Object.keys(TABS)) {
    $('tab-' + name).hidden = name !== id;
    $('t-' + name).setAttribute('aria-selected', name === id);
  }
  activeTab = id; prefs.tab = id; persist();
  window.scrollTo(0, 0);
  if (id === 'takes') requestAnimationFrame(drawWave);
}
for (const b of document.querySelectorAll('[data-tab]')) b.onclick = () => showTab(b.dataset.tab);
$('prev').innerHTML = icon('prev'); $('play').innerHTML = icon('play'); $('next').innerHTML = icon('next');
applySpeed(); showMusic(prefs.musicView); showTab(prefs.tab);
