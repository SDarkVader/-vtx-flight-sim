// =====================================================================================
// TABS AND START
// =====================================================================================
const TABS = { tracks: ['Tracks', 'tracks'], mix: ['Mix', 'mix'], music: ['Music', 'music'], vehicle: ['Vehicle', 'jet'], scene: ['Scene', 'scene'], takes: ['Takes', 'takes'] };
for (const [id, [label, glyph]] of Object.entries(TABS)) $('t-' + id).innerHTML = icon(glyph) + `<span>${label}</span>`;
function showTab(id) {
  if (!TABS[id]) id = 'tracks';
  if (id === 'mix' && mixDirty) { buildMix(); mixDirty = false; }
  for (const name of Object.keys(TABS)) {
    $('tab-' + name).hidden = name !== id;
    $('t-' + name).setAttribute('aria-selected', name === id);
  }
  activeTab = id; prefs.tab = id; persist();
  window.scrollTo(0, 0);
  if (id === 'takes') requestAnimationFrame(drawWave);
  if (id === 'tracks') { renderTracks(); } else { $('play').innerHTML = icon(player.paused ? 'play' : 'pause'); showNow(); }
}
for (const b of document.querySelectorAll('[data-tab]')) b.onclick = () => showTab(b.dataset.tab);
$('prev').innerHTML = icon('prev'); $('play').innerHTML = icon('play'); $('next').innerHTML = icon('next');
// The header transport follows the bench: the timeline on Tracks, the radio everywhere else.
$('play').onclick = () => activeTab === 'tracks' ? arrToggle() : toggle();
$('prev').onclick = () => activeTab === 'tracks' ? arrSeek(arr.loop.on ? arr.loop.start : 0) : step(-1, true);
$('next').onclick = () => activeTab === 'tracks' ? arrSeek(snapT(songEnd())) : step(1, true);
buildTracks();
applySpeed(); showMusic(prefs.musicView); showTab(prefs.tab);
