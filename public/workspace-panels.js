(() => {
 const main = document.querySelector('main');
 const bar = document.createElement('div');
 bar.className = 'workspace-tabs';
 bar.setAttribute('role','group');
 bar.setAttribute('aria-label','Cockpit panels');
 for (const [label, cls, selector] of [['Mission','mission-open','.mission-panel'],['Controls','controls-open','.controls-panel']]) {
   const panel = document.querySelector(selector);
   const id = label.toLowerCase() + '-drawer';
   panel.id = id;
   const button = document.createElement('button');
   button.type = 'button';
   button.textContent = label;
   button.setAttribute('aria-controls', id);
   button.setAttribute('aria-expanded', 'false');
   button.addEventListener('click', () => {
     const open = main.classList.toggle(cls);
     button.setAttribute('aria-expanded', String(open));
     window.dispatchEvent(new Event('resize'));
   });
   bar.appendChild(button);
 }
 const airport = document.createElement('button');
 airport.type = 'button'; airport.textContent = 'Airport views'; airport.setAttribute('aria-expanded','false');
 airport.addEventListener('click', () => {
   const panel = document.getElementById('ride-controls'); if (!panel) return;
   const open = panel.style.display === 'none'; panel.style.display = open ? 'flex' : 'none';
   airport.setAttribute('aria-expanded', String(open)); window.dispatchEvent(new Event('resize'));
 });
 bar.appendChild(airport);
 const link = document.createElement('a');
 link.className = 'workspace-dashboard-link';
 link.href = '/dashboard/';
 link.textContent = 'Flight test dashboard';
 bar.appendChild(link);
 document.querySelector('header').appendChild(bar);
 document.getElementById('models').addEventListener('click', () => {
   if (!main.classList.contains('mission-open')) bar.querySelector('button').click();
 });
 document.addEventListener('DOMContentLoaded', () => {
   const footer = document.querySelector('footer');
   if (footer && footer.parentElement === main) main.after(footer);
 });
})();