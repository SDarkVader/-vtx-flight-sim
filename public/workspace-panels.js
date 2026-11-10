(() => {
 const main = document.querySelector('main');
 const cockpit = document.createElement('section');
 cockpit.className = 'cockpit-workspace';
 cockpit.id = 'cockpit-workspace';
 cockpit.setAttribute('aria-label', 'Live cockpit');
 while (main.firstChild) cockpit.appendChild(main.firstChild);
 main.appendChild(cockpit);

 // Ensure the central live 3D view (#cockpit-workspace / #viewport) can NEVER be hidden
 Object.defineProperty(cockpit, 'hidden', {
   get() { return false; },
   set() { cockpit.removeAttribute('hidden'); },
   configurable: true
 });

 const viewport = cockpit.querySelector('#viewport');
 const missionPanel = cockpit.querySelector('.mission-panel');
 const controlsPanel = cockpit.querySelector('.controls-panel');
 const airportPanel = document.createElement('aside');
 airportPanel.className = 'airport-panel';
 airportPanel.innerHTML = '<div class="section-label">03 / AIRPORT</div><h2>Airport views</h2>';

 // Build Left Dock, Left Resizer, Central Viewport, Right Resizer, Right Dock
 const leftDock = document.createElement('div');
 leftDock.id = 'left-dock';
 leftDock.className = 'side-dock side-dock-left';
 leftDock.hidden = true;

 const leftResizer = document.createElement('div');
 leftResizer.id = 'left-resizer';
 leftResizer.className = 'dock-resizer dock-resizer-left';
 leftResizer.title = 'Drag to resize left panel';
 leftResizer.setAttribute('role', 'separator');
 leftResizer.setAttribute('aria-orientation', 'vertical');
 leftResizer.hidden = true;

 const rightResizer = document.createElement('div');
 rightResizer.id = 'right-resizer';
 rightResizer.className = 'dock-resizer dock-resizer-right';
 rightResizer.title = 'Drag to resize right panel';
 rightResizer.setAttribute('role', 'separator');
 rightResizer.setAttribute('aria-orientation', 'vertical');
 rightResizer.hidden = true;

 const rightDock = document.createElement('div');
 rightDock.id = 'right-dock';
 rightDock.className = 'side-dock side-dock-right';
 rightDock.hidden = true;

 // Dashboard and Experiments workspaces live inside Left/Right docks (never replacing the central viewport)
 const dashboardPage = document.createElement('section');
 dashboardPage.className = 'embedded-workspace';
 dashboardPage.id = 'dashboard-workspace';
 dashboardPage.hidden = true;
 const dashboardFrame = document.createElement('iframe');
 dashboardFrame.title = 'Flight test dashboard';
 dashboardFrame.dataset.src = '/dashboard/';
 dashboardPage.appendChild(dashboardFrame);

 const experimentsPage = document.createElement('section');
 experimentsPage.className = 'embedded-workspace';
 experimentsPage.id = 'experiments-workspace';
 experimentsPage.hidden = true;
 const experimentsFrame = document.createElement('iframe');
 experimentsFrame.title = 'Physics experiments';
 experimentsFrame.dataset.src = '/experiments/';
 experimentsPage.appendChild(experimentsFrame);

 missionPanel.id = 'mission-drawer';
 controlsPanel.id = 'controls-drawer';
 airportPanel.id = 'airport-drawer';

 leftDock.append(missionPanel, dashboardPage);
 rightDock.append(controlsPanel, airportPanel, experimentsPage);
 cockpit.replaceChildren(leftDock, leftResizer, viewport, rightResizer, rightDock);

 const bar = document.createElement('div');
 bar.className = 'workspace-tabs';
 bar.setAttribute('role', 'group');
 bar.setAttribute('aria-label', 'Cockpit panels');

 const pages = document.createElement('div');
 pages.className = 'workspace-pages';
 pages.setAttribute('role', 'group');
 pages.setAttribute('aria-label', 'Visible workspace pages');

 const panelButtons = new Map();

 function syncDockState() {
   const leftOpen = cockpit.classList.contains('mission-open') || !dashboardPage.hidden;
   const rightOpen = cockpit.classList.contains('controls-open') || cockpit.classList.contains('airport-open') || !experimentsPage.hidden;
   leftDock.hidden = !leftOpen;
   leftResizer.hidden = !leftOpen;
   rightDock.hidden = !rightOpen;
   rightResizer.hidden = !rightOpen;
   cockpit.classList.toggle('left-dock-open', leftOpen);
   cockpit.classList.toggle('right-dock-open', rightOpen);
   for (const [key, btn] of panelButtons.entries()) {
     if (key === 'mission-open' || key === 'controls-open' || key === 'airport-open') {
       btn.setAttribute('aria-expanded', String(cockpit.classList.contains(key)));
     } else if (key === 'dashboard-workspace') {
       btn.setAttribute('aria-pressed', String(!dashboardPage.hidden));
     } else if (key === 'experiments-workspace') {
       btn.setAttribute('aria-pressed', String(!experimentsPage.hidden));
     } else if (key === 'cockpit-workspace') {
       btn.setAttribute('aria-pressed', 'true');
     }
   }
   window.dispatchEvent(new Event('resize'));
 }

 // Left & Right panel toggles:
 // Left dock hosts either Mission OR Flight test dashboard (mutually exclusive on left so it stays compact)
 // Right dock hosts Controls, Airport views, or Physics experiments (compact right dock)
 for (const [label, cls, id] of [
   ['Mission', 'mission-open', 'mission-drawer'],
   ['Controls', 'controls-open', 'controls-drawer'],
   ['Airport views', 'airport-open', 'airport-drawer']
 ]) {
   const button = document.createElement('button');
   button.type = 'button';
   button.textContent = label;
   button.setAttribute('aria-controls', id);
   button.setAttribute('aria-expanded', 'false');
   button.addEventListener('click', () => {
     const willOpen = !cockpit.classList.contains(cls);
     if (cls === 'mission-open' && willOpen) {
       dashboardPage.hidden = true;
     }
     if ((cls === 'controls-open' || cls === 'airport-open') && willOpen) {
       experimentsPage.hidden = true;
       if (cls === 'controls-open') cockpit.classList.remove('airport-open');
       if (cls === 'airport-open') cockpit.classList.remove('controls-open');
     }
     cockpit.classList.toggle(cls, willOpen);
     syncDockState();
   });
   panelButtons.set(cls, button);
   bar.appendChild(button);
 }

 // Workspace page buttons:
 // "Live cockpit" resets to the default 360° pinned vehicle view (closes all side panels, never hides #cockpit-workspace!)
 // "Flight test dashboard" opens in Left Dock
 // "Physics experiments" opens in Right Dock (or Left if preferred, while keeping center live view visible)
 const liveBtn = document.createElement('button');
 liveBtn.type = 'button';
 liveBtn.textContent = '360° Live View';
 liveBtn.title = 'Pin 360° live vehicle view and collapse side panels';
 liveBtn.setAttribute('aria-controls', 'cockpit-workspace');
 liveBtn.setAttribute('aria-pressed', 'true');
 liveBtn.addEventListener('click', () => {
   cockpit.classList.remove('mission-open', 'controls-open', 'airport-open');
   dashboardPage.hidden = true;
   experimentsPage.hidden = true;
   syncDockState();
   window.dispatchEvent(new CustomEvent('vtx-recenter-vehicle'));
 });
 panelButtons.set('cockpit-workspace', liveBtn);
 pages.appendChild(liveBtn);

 for (const [label, id, page, side] of [
   ['Flight test dashboard', 'dashboard-workspace', dashboardPage, 'left'],
   ['Physics experiments', 'experiments-workspace', experimentsPage, 'right']
 ]) {
   const button = document.createElement('button');
   button.type = 'button';
   button.textContent = label;
   button.setAttribute('aria-controls', id);
   button.setAttribute('aria-pressed', 'false');
   button.addEventListener('click', () => {
     const willOpen = page.hidden;
     page.hidden = !willOpen;
     if (willOpen) {
       const frame = page.querySelector('iframe');
       if (!frame.getAttribute('src')) frame.src = frame.dataset.src;
       if (side === 'left') {
         cockpit.classList.remove('mission-open');
       } else {
         cockpit.classList.remove('controls-open', 'airport-open');
       }
     }
     syncDockState();
   });
   panelButtons.set(id, button);
   pages.appendChild(button);
 }

 // Manual drag-resize support for Left and Right docks + automatic window-size clamping
 function clampSideWidths() {
   const totalW = cockpit.clientWidth || window.innerWidth;
   const minCenter = Math.max(380, Math.round(totalW * 0.42));
   const maxPerSide = Math.max(210, Math.floor((totalW - minCenter) / 2));
   for (const [prop, fallback] of [['--left-dock-w', 290], ['--right-dock-w', 280]]) {
     const current = parseFloat(cockpit.style.getPropertyValue(prop));
     if (Number.isFinite(current)) {
       cockpit.style.setProperty(prop, `${Math.max(200, Math.min(maxPerSide, current))}px`);
     } else {
       cockpit.style.setProperty(prop, `${Math.min(fallback, maxPerSide)}px`);
     }
   }
 }

 function attachResizer(handle, side) {
   let activePointer = null;
   handle.addEventListener('pointerdown', (e) => {
     e.preventDefault();
     activePointer = e.pointerId;
     handle.setPointerCapture(e.pointerId);
     handle.classList.add('dragging');
     document.body.classList.add('resizing-panels');
   });
   handle.addEventListener('pointermove', (e) => {
     if (activePointer !== e.pointerId) return;
     const rect = cockpit.getBoundingClientRect();
     const minCenter = Math.max(380, Math.round(rect.width * 0.42));
     const otherWidth = side === 'left'
       ? (rightDock.hidden ? 0 : rightDock.getBoundingClientRect().width)
       : (leftDock.hidden ? 0 : leftDock.getBoundingClientRect().width);
     const maxAllowed = Math.max(210, Math.min(Math.floor(rect.width * 0.36), rect.width - otherWidth - minCenter));
     const rawWidth = side === 'left' ? (e.clientX - rect.left) : (rect.right - e.clientX);
     const clamped = Math.max(200, Math.min(maxAllowed, Math.round(rawWidth)));
     cockpit.style.setProperty(side === 'left' ? '--left-dock-w' : '--right-dock-w', `${clamped}px`);
     window.dispatchEvent(new Event('resize'));
   });
   const stopDrag = (e) => {
     if (activePointer === null || (e.pointerId !== undefined && e.pointerId !== activePointer)) return;
     activePointer = null;
     handle.classList.remove('dragging');
     document.body.classList.remove('resizing-panels');
     window.dispatchEvent(new Event('resize'));
   };
   handle.addEventListener('pointerup', stopDrag);
   handle.addEventListener('pointercancel', stopDrag);
   handle.addEventListener('lostpointercapture', stopDrag);
   handle.addEventListener('dblclick', () => {
     cockpit.style.setProperty(side === 'left' ? '--left-dock-w' : '--right-dock-w', side === 'left' ? '290px' : '280px');
     clampSideWidths();
     window.dispatchEvent(new Event('resize'));
   });
 }

 attachResizer(leftResizer, 'left');
 attachResizer(rightResizer, 'right');
 window.addEventListener('resize', clampSideWidths);
 clampSideWidths();
 syncDockState();

 document.querySelector('header').appendChild(bar);
 document.querySelector('header').appendChild(pages);
 document.getElementById('models').addEventListener('click', () => {
   if (!cockpit.classList.contains('mission-open')) {
     panelButtons.get('mission-open')?.click();
   }
 });
 document.addEventListener('DOMContentLoaded', () => {
   const footer = document.querySelector('footer');
   if (footer && footer.parentElement === main) main.after(footer);
 });
})();

