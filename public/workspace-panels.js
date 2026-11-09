(() => {
 const main = document.querySelector('main');
 const cockpit = document.createElement('section');
 cockpit.className = 'cockpit-workspace';
 cockpit.id = 'cockpit-workspace';
 cockpit.setAttribute('aria-label', 'Live cockpit');
 while (main.firstChild) cockpit.appendChild(main.firstChild);
 main.appendChild(cockpit);
 const bar = document.createElement('div');
 bar.className = 'workspace-tabs';
 bar.setAttribute('role','group');
 bar.setAttribute('aria-label','Cockpit panels');
 const airportPanel = document.createElement('aside');
 airportPanel.className = 'airport-panel';
 airportPanel.innerHTML = '<div class="section-label">03 / AIRPORT</div><h2>Airport views</h2>';
 cockpit.appendChild(airportPanel);
 for (const [label, cls, selector] of [['Mission','mission-open','.mission-panel'],['Controls','controls-open','.controls-panel'],['Airport views','airport-open','.airport-panel']]) {
   const panel = cockpit.querySelector(selector);
   const id = cls.replace('-open', '-drawer');
   panel.id = id;
   const button = document.createElement('button');
   button.type = 'button';
   button.textContent = label;
   button.setAttribute('aria-controls', id);
   button.setAttribute('aria-expanded', 'false');
   button.addEventListener('click', () => {
     const open = cockpit.classList.toggle(cls);
     button.setAttribute('aria-expanded', String(open));
     window.dispatchEvent(new Event('resize'));
   });
   bar.appendChild(button);
 }
 const pages = document.createElement('div');
 pages.className = 'workspace-pages';
 pages.setAttribute('role', 'group');
 pages.setAttribute('aria-label', 'Visible workspace pages');
 for (const [label, id, url, panel] of [
   ['Live cockpit', 'cockpit-workspace', null, cockpit],
   ['Flight test dashboard', 'dashboard-workspace', '/dashboard/', null],
   ['Physics experiments', 'experiments-workspace', '/experiments/', null]
 ]) {
   let page = panel;
   if (!page) {
     page = document.createElement('section');
     page.className = 'embedded-workspace';
     page.id = id;
     page.hidden = true;
     const frame = document.createElement('iframe');
     frame.title = label;
     frame.dataset.src = url;
     page.appendChild(frame);
     main.appendChild(page);
   }
   const button = document.createElement('button');
   button.type = 'button';
   button.textContent = label;
   button.setAttribute('aria-controls', id);
   button.setAttribute('aria-pressed', String(!page.hidden));
   button.addEventListener('click', () => {
     page.hidden = !page.hidden;
     if (!page.hidden && url) {
       const frame = page.querySelector('iframe');
       if (!frame.getAttribute('src')) frame.src = frame.dataset.src;
     }
     button.setAttribute('aria-pressed', String(!page.hidden));
     window.dispatchEvent(new Event('resize'));
   });
   pages.appendChild(button);
 }
 document.querySelector('header').appendChild(bar);
 document.querySelector('header').appendChild(pages);
 document.getElementById('models').addEventListener('click', () => {
   if (cockpit.hidden) pages.querySelector('button').click();
   if (!cockpit.classList.contains('mission-open')) bar.querySelector('button').click();
 });
 document.addEventListener('DOMContentLoaded', () => {
   const footer = document.querySelector('footer');
   if (footer && footer.parentElement === main) main.after(footer);
 });
})();
