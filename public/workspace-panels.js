(() => {
  const main = document.querySelector('main');
  const mission = document.querySelector('.mission-panel');
  const controls = document.querySelector('.controls-panel');
  const bar = document.createElement('div');
  bar.className = 'workspace-tabs';
  bar.setAttribute('role', 'group');
  bar.setAttribute('aria-label', 'Cockpit panels');
  for (const [label, panel, cls] of [['Mission', mission, 'mission-open'], ['Controls', controls, 'controls-open']]) {
    const b = document.createElement('button');
    b.type = 'button'; b.textContent = label; b.setAttribute('aria-expanded', 'false');
    b.addEventListener('click', () => {
      const open = !main.classList.contains(cls);
      main.classList.remove('mission-open', 'controls-open');
      bar.querySelectorAll('button').forEach(x => x.setAttribute('aria-expanded', 'false'));
      if (open) { main.classList.add(cls); b.setAttribute('aria-expanded', 'true'); }
      window.dispatchEvent(new Event('resize'));
    });
    bar.appendChild(b);
  }
  document.querySelector('header').appendChild(bar);
})();