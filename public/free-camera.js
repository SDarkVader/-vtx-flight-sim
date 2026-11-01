// Free Roam Camera Controller for Vader's Taxis Flight Simulator.
// Replaces the centered/anchored orbit with full 6-DOF free flight navigation
// and smooth mobile pinch-to-zoom, touch-to-look, and two-finger pan across the entire world.

import * as THREE from 'three';

export function createFreeCamera(camera, renderer, viewport, setCameraMode) {
  let active = false;
  let yaw = 0;       // horizontal look angle (rad)
  let pitch = 0;     // vertical look angle (rad)
  const pos = new THREE.Vector3();
  const forward = new THREE.Vector3();
  const right = new THREE.Vector3();
  const up = new THREE.Vector3(0, 0, 1);

  // Active keyboard inputs
  const keys = new Set();
  const touchNav = { fwd: 0, back: 0, left: 0, right: 0, up: 0, down: 0, boost: 1 };

  // Pointer drag state for mouse
  let isDragging = false;
  let lastPointerX = 0;
  let lastPointerY = 0;

  // Speeds
  const BASE_SPEED = 24;   // m/s normal flight
  const FAST_SPEED = 72;   // m/s turbo flight (Shift held)
  const ROTATE_SPEED = 0.0035;

  // Touch state
  let touch1 = null;
  let touch2 = null;
  let initialDistance = 0;
  let initialMidpoint = { x: 0, y: 0 };
  let initialYaw = 0;
  let initialPitch = 0;

  // -------------------------------------------------------------------------
  // On-screen Free Roam HUD container (Desktop + Mobile responsive)
  // -------------------------------------------------------------------------
  const hud = document.createElement('div');
  hud.id = 'free-cam-hud';
  hud.style.cssText = `
    position: absolute;
    bottom: 46px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(14, 18, 24, 0.92);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(56, 189, 248, 0.5);
    border-radius: 10px;
    padding: 8px 14px;
    display: none;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    z-index: 120;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
    font-size: 12px;
    color: #e0f2fe;
    box-shadow: 0 8px 24px rgba(0,0,0,0.65);
    pointer-events: auto;
    max-width: 95vw;
    width: auto;
    user-select: none;
    -webkit-user-select: none;
  `;

  // Top header row inside HUD
  const topRow = document.createElement('div');
  topRow.style.cssText = 'display: flex; align-items: center; gap: 10px; flex-wrap: wrap; justify-content: center;';

  const badge = document.createElement('span');
  badge.style.cssText = 'color: #38bdf8; font-weight: bold; letter-spacing: 1px; font-size: 11px;';
  badge.textContent = '🕹️ FREE ROAM CAMERA';
  topRow.appendChild(badge);

  const hints = document.createElement('span');
  hints.style.cssText = 'color: #94a3b8; font-size: 11px;';
  hints.textContent = '1-finger: Look · Pinch: Zoom/Fly · 2-finger: Pan';
  topRow.appendChild(hints);

  const exitBtn = document.createElement('button');
  exitBtn.type = 'button';
  exitBtn.textContent = 'Exit to Chase';
  exitBtn.style.cssText = `
    background: #0369a1;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: bold;
    cursor: pointer;
  `;
  exitBtn.onclick = (e) => {
    e.stopPropagation();
    if (setCameraMode) setCameraMode('chase');
  };
  topRow.appendChild(exitBtn);

  hud.appendChild(topRow);

  // Landmark teleport row
  const lmContainer = document.createElement('div');
  lmContainer.style.cssText = 'display: flex; gap: 6px; flex-wrap: wrap; justify-content: center;';

  const landmarks = [
    { name: 'Stand 1', pos: [-55, 485, 12], target: [-30, 480, 5] },
    { name: 'Tower', pos: [-70, 575, 46], target: [0, 400, 10] },
    { name: 'Runway 26', pos: [380, 0, 14], target: [0, 0, 2] },
    { name: 'Volcano Portal', pos: [-30, 125, 12], target: [-30, 158, 9] },
    { name: 'Basement Platform 3', pos: [-44, 218, 4.5], target: [-54, 222, 3.2] },
    { name: 'Sky-Whale', pos: [-26, 210, 24], target: [-8, 225, 26] },
  ];

  landmarks.forEach(lm => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = lm.name;
    btn.style.cssText = `
      background: #1e293b;
      color: #7dd3fc;
      border: 1px solid #334155;
      border-radius: 4px;
      padding: 4px 9px;
      font-size: 11px;
      cursor: pointer;
    `;
    btn.onmouseenter = () => btn.style.background = '#334155';
    btn.onmouseleave = () => btn.style.background = '#1e293b';
    btn.onclick = (e) => {
      e.stopPropagation();
      teleport(lm.pos, lm.target);
    };
    lmContainer.appendChild(btn);
  });
  hud.appendChild(lmContainer);

  // Mobile Touch Navigation Flight D-Pad (visible on mobile / touch devices)
  const isTouchDevice = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
  const touchNavRow = document.createElement('div');
  touchNavRow.id = 'touch-nav-row';
  touchNavRow.style.cssText = `
    display: ${isTouchDevice ? 'flex' : 'none'};
    gap: 8px;
    align-items: center;
    justify-content: center;
    margin-top: 4px;
    flex-wrap: wrap;
  `;

  function makeTouchBtn(txt, onPress, onRelease) {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = txt;
    b.style.cssText = `
      background: #0f172a;
      color: #f8fafc;
      border: 1px solid #475569;
      border-radius: 6px;
      padding: 6px 14px;
      font-size: 13px;
      font-weight: bold;
      touch-action: none;
      user-select: none;
      -webkit-user-select: none;
    `;
    const start = (e) => { e.preventDefault(); e.stopPropagation(); b.style.background = '#38bdf8'; b.style.color = '#000'; onPress(); };
    const end = (e) => { e.preventDefault(); e.stopPropagation(); b.style.background = '#0f172a'; b.style.color = '#f8fafc'; onRelease(); };
    b.addEventListener('pointerdown', start);
    b.addEventListener('pointerup', end);
    b.addEventListener('pointercancel', end);
    return b;
  }

  touchNavRow.appendChild(makeTouchBtn('▲ Fwd', () => touchNav.fwd = 1, () => touchNav.fwd = 0));
  touchNavRow.appendChild(makeTouchBtn('▼ Back', () => touchNav.back = 1, () => touchNav.back = 0));
  touchNavRow.appendChild(makeTouchBtn('◀ Left', () => touchNav.left = 1, () => touchNav.left = 0));
  touchNavRow.appendChild(makeTouchBtn('▶ Right', () => touchNav.right = 1, () => touchNav.right = 0));
  touchNavRow.appendChild(makeTouchBtn('⤊ Up', () => touchNav.up = 1, () => touchNav.up = 0));
  touchNavRow.appendChild(makeTouchBtn('⤋ Down', () => touchNav.down = 1, () => touchNav.down = 0));
  touchNavRow.appendChild(makeTouchBtn('⚡ Turbo', () => touchNav.boost = 3, () => touchNav.boost = 1));

  hud.appendChild(touchNavRow);
  viewport.appendChild(hud);

  function updateLookVectors() {
    const cp = Math.cos(pitch);
    forward.set(
      Math.sin(yaw) * cp,
      Math.cos(yaw) * cp,
      Math.sin(pitch)
    ).normalize();
    right.set(Math.cos(yaw), -Math.sin(yaw), 0).normalize();
  }

  function teleport(targetPos, lookAtPos) {
    pos.set(...targetPos);
    camera.position.copy(pos);
    if (lookAtPos) {
      const dir = new THREE.Vector3(...lookAtPos).sub(pos).normalize();
      yaw = Math.atan2(dir.x, dir.y);
      pitch = Math.asin(THREE.MathUtils.clamp(dir.z, -0.99, 0.99));
    }
    updateLookVectors();
    camera.up.set(0, 0, 1);
    camera.lookAt(pos.clone().add(forward));
  }

  function activate(currentAimTarget) {
    active = true;
    hud.style.display = 'flex';
    touchNavRow.style.display = (('ontouchstart' in window) || (navigator.maxTouchPoints > 0) || (innerWidth <= 800)) ? 'flex' : 'none';

    pos.copy(camera.position);

    if (currentAimTarget) {
      const dir = currentAimTarget.clone().sub(pos).normalize();
      yaw = Math.atan2(dir.x, dir.y);
      pitch = Math.asin(THREE.MathUtils.clamp(dir.z, -0.99, 0.99));
    } else {
      const worldDir = new THREE.Vector3();
      camera.getWorldDirection(worldDir);
      yaw = Math.atan2(worldDir.x, worldDir.y);
      pitch = Math.asin(THREE.MathUtils.clamp(worldDir.z, -0.99, 0.99));
    }
    updateLookVectors();
  }

  function deactivate() {
    active = false;
    hud.style.display = 'none';
    keys.clear();
    Object.keys(touchNav).forEach(k => { if (k !== 'boost') touchNav[k] = 0; else touchNav.boost = 1; });
    isDragging = false;
    touch1 = null;
    touch2 = null;
  }

  const dom = renderer.domElement;

  // -------------------------------------------------------------------------
  // Mouse / Pointer Controls
  // -------------------------------------------------------------------------
  dom.addEventListener('pointerdown', (e) => {
    if (!active) return;
    if (e.pointerType === 'touch') return; // Handled by touch events below
    isDragging = true;
    lastPointerX = e.clientX;
    lastPointerY = e.clientY;
    dom.setPointerCapture(e.pointerId);
  });

  dom.addEventListener('pointermove', (e) => {
    if (!active || !isDragging || e.pointerType === 'touch') return;
    const dx = e.clientX - lastPointerX;
    const dy = e.clientY - lastPointerY;
    lastPointerX = e.clientX;
    lastPointerY = e.clientY;

    if (e.buttons === 2 || e.buttons === 4) {
      // Pan
      const panSpeed = 0.08;
      pos.addScaledVector(right, -dx * panSpeed);
      pos.addScaledVector(up, dy * panSpeed);
    } else {
      // First person look around
      yaw -= dx * ROTATE_SPEED;
      pitch = THREE.MathUtils.clamp(pitch - dy * ROTATE_SPEED, -Math.PI * 0.48, Math.PI * 0.48);
      updateLookVectors();
    }
  });

  for (const ev of ['pointerup', 'pointercancel', 'lostpointercapture']) {
    dom.addEventListener(ev, (e) => {
      if (active && e.pointerType !== 'touch') isDragging = false;
    });
  }

  // Wheel: fly forward / backward
  dom.addEventListener('wheel', (e) => {
    if (!active) return;
    e.preventDefault();
    const zoomDelta = -Math.sign(e.deltaY) * (keys.has('ShiftLeft') || keys.has('ShiftRight') ? 14 : 5);
    pos.addScaledVector(forward, zoomDelta);
  }, { passive: false });

  // -------------------------------------------------------------------------
  // Mobile Touch Gestures: Pinch to Zoom & Fly, 1-finger Look, 2-finger Pan
  // -------------------------------------------------------------------------
  dom.addEventListener('touchstart', (e) => {
    if (!active) return;
    if (e.touches.length === 1) {
      touch1 = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      touch2 = null;
      initialYaw = yaw;
      initialPitch = pitch;
    } else if (e.touches.length === 2) {
      touch1 = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      touch2 = { x: e.touches[1].clientX, y: e.touches[1].clientY };
      initialDistance = Math.hypot(touch2.x - touch1.x, touch2.y - touch1.y);
      initialMidpoint = { x: (touch1.x + touch2.x) / 2, y: (touch1.y + touch2.y) / 2 };
    }
  }, { passive: true });

  dom.addEventListener('touchmove', (e) => {
    if (!active) return;
    if (e.touches.length === 1 && touch1) {
      // Single finger drag: look around in 360 degrees
      const dx = e.touches[0].clientX - touch1.x;
      const dy = e.touches[0].clientY - touch1.y;
      yaw = initialYaw - dx * 0.005;
      pitch = THREE.MathUtils.clamp(initialPitch - dy * 0.005, -Math.PI * 0.48, Math.PI * 0.48);
      updateLookVectors();
    } else if (e.touches.length === 2 && touch1 && touch2) {
      const cur1 = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      const cur2 = { x: e.touches[1].clientX, y: e.touches[1].clientY };
      const curDist = Math.hypot(cur2.x - cur1.x, cur2.y - cur1.y);
      const curMid = { x: (cur1.x + cur2.x) / 2, y: (cur1.y + cur2.y) / 2 };

      // Pinch to Zoom / Fly:
      // Fingers spreading apart = zoom in / fly forward
      // Fingers pinching together = zoom out / fly backward
      const distDelta = curDist - initialDistance;
      const flyFactor = (touchNav.boost > 1) ? 0.28 : 0.12;
      pos.addScaledVector(forward, distDelta * flyFactor);
      initialDistance = curDist;

      // Two-finger pan: translates camera across view
      const panX = curMid.x - initialMidpoint.x;
      const panY = curMid.y - initialMidpoint.y;
      const panSpeed = 0.06;
      pos.addScaledVector(right, -panX * panSpeed);
      pos.addScaledVector(up, panY * panSpeed);
      initialMidpoint = curMid;
    }
  }, { passive: true });

  dom.addEventListener('touchend', (e) => {
    if (!active) return;
    if (e.touches.length === 1) {
      touch1 = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      touch2 = null;
      initialYaw = yaw;
      initialPitch = pitch;
    } else if (e.touches.length === 0) {
      touch1 = null;
      touch2 = null;
    }
  }, { passive: true });

  // -------------------------------------------------------------------------
  // Keyboard Navigation
  // -------------------------------------------------------------------------
  window.addEventListener('keydown', (e) => {
    if (!active) return;
    if (/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
    if (document.querySelector('dialog[open]')) return;

    if (['KeyW', 'KeyS', 'KeyA', 'KeyD', 'KeyQ', 'KeyE', 'KeyC', 'Space', 'ShiftLeft', 'ShiftRight',
         'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'PageUp', 'PageDown'].includes(e.code)) {
      keys.add(e.code);
      e.preventDefault();
    }
  });

  window.addEventListener('keyup', (e) => {
    if (active) keys.delete(e.code);
  });

  window.addEventListener('blur', () => {
    keys.clear();
  });

  // Called each frame from animate()
  function update(dt) {
    if (!active) return;

    const isFast = keys.has('ShiftLeft') || keys.has('ShiftRight') || touchNav.boost > 1;
    const speed = (isFast ? FAST_SPEED : BASE_SPEED) * dt;

    // Keyboard inputs
    if (keys.has('KeyW') || keys.has('ArrowUp')) pos.addScaledVector(forward, speed);
    if (keys.has('KeyS') || keys.has('ArrowDown')) pos.addScaledVector(forward, -speed);
    if (keys.has('KeyD') || keys.has('ArrowRight')) pos.addScaledVector(right, speed);
    if (keys.has('KeyA') || keys.has('ArrowLeft')) pos.addScaledVector(right, -speed);
    if (keys.has('Space') || keys.has('KeyE') || keys.has('PageUp')) pos.addScaledVector(up, speed);
    if (keys.has('KeyC') || keys.has('KeyQ') || keys.has('PageDown')) pos.addScaledVector(up, -speed);

    // On-screen touch D-Pad inputs
    if (touchNav.fwd) pos.addScaledVector(forward, speed);
    if (touchNav.back) pos.addScaledVector(forward, -speed);
    if (touchNav.right) pos.addScaledVector(right, speed);
    if (touchNav.left) pos.addScaledVector(right, -speed);
    if (touchNav.up) pos.addScaledVector(up, speed);
    if (touchNav.down) pos.addScaledVector(up, -speed);

    // Keep camera slightly above terrain floor
    if (pos.z < 0.8) pos.z = 0.8;

    updateLookVectors();
    camera.position.copy(pos);
    camera.up.set(0, 0, 1);
    camera.lookAt(pos.clone().add(forward));
  }

  function zoom(factor) {
    if (!active) return;
    const step = (factor < 1 ? 8 : -8);
    pos.addScaledVector(forward, step);
  }

  return {
    get isActive() { return active; },
    activate,
    deactivate,
    update,
    zoom,
    teleport,
    get position() { return pos; },
    get yaw() { return yaw; },
    get pitch() { return pitch; }
  };
}
