# VTX Design System Rules & Cockpit Interface Specifications

**Document Version:** 1.0.0 (Unified Three-Panel Runtime & Dual-Environment Release)  
**Target Platform:** WebGL / Three.js Canvas + Vanilla ES Modules + FastAPI / MuJoCo 400Hz Engine  
**Aesthetic Profile:** Aerospace Flight-Test Hangar, Tactical Night-Ops HUD, High-Contrast Telemetry

---

## 1. Design Token Definitions

All design tokens are implemented as native CSS custom properties on `:root` across [`public/workspace-theme.css`](file:///public/workspace-theme.css) and [`public/style.css`](file:///public/style.css).

### 1.1 Color Tokens

The VTX color system is inspired by military test-range control rooms and dark-cockpit avionics. High-luminance accents punctuate ultra-low reflectance carbon-slate backgrounds.

```css
:root {
  /* Surfaces & Backgrounds */
  --bg-deep: #080b0c;          /* Deepest viewport canvas underlay */
  --bg: #0d1112;               /* Standard workspace container background */
  --surface: #101515;          /* Panel cards and drawer surface */
  --surface-hover: #151b1b;    /* Hover state for interactive cards */
  --surface-elevated: #192020; /* Raised modals, dropdown menus, tooltips */
  --surface-alt: #131718;      /* Alternate row / secondary container */

  /* Structural Lines & Borders */
  --line: #293131;             /* Primary hairline border (1px solid) */
  --line-light: #35403a;       /* Focused container border / divider */
  --line-strong: #455149;      /* Active state border */

  /* Functional Accents & Status Indicators */
  --accent: #d4f66a;           /* VTX Neon Lime (Primary brand & active state) */
  --accent-soft: rgba(212, 246, 106, 0.12); /* Selected button glow / hover underlay */
  --accent-secondary: #7cdfcb; /* Tactical Cyan (Instruments, minimap airport bounds) */
  --accent-warning: #ffc88b;   /* Warning Amber (Feathered controls, lease timer) */
  --accent-danger: #ff2211;    /* Alert Red (Impact, stall, lock violation) */
  --accent-sandbox: #ffb74d;   /* Range Orange (Test Sandbox environment badge) */

  /* Typography Colors */
  --text: #e6eded;             /* Primary high-contrast readability */
  --muted: #89958f;            /* Secondary labels, units, and timestamps */
  --dim: #5c6662;              /* Inactive labels and disabled buttons */
}
```

### 1.2 Typography Tokens

Typography separates brand headlines, ergonomic UI labels, and numeric telemetry readouts.

| Role | Font Family | Weights | Usage |
| :--- | :--- | :--- | :--- |
| **Brand & Display** | `'Space Grotesk', system-ui, sans-serif` | `700`, `600` | Cockpit header, vehicle names, modal titles |
| **Interface / Controls** | `'DM Sans', system-ui, sans-serif` | `400`, `500` | Button labels, dropdown items, tooltips, drawer headers |
| **Telemetry & Monospace** | `ui-monospace, SFMono-Regular, Menlo, monospace` | `400`, `700` | Readouts, coordinates, Hz clocks, hash IDs, pilot audits |

```css
:root {
  --font-brand: 'Space Grotesk', system-ui, sans-serif;
  --font-ui: 'DM Sans', system-ui, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, monospace;

  /* Typography Scales */
  --text-xs: 0.6875rem; /* 11px - Telemetry units, micro badges */
  --text-sm: 0.8125rem; /* 13px - Secondary labels, drawer buttons */
  --text-base: 0.9375rem; /* 15px - Body prose, primary controls */
  --text-lg: 1.125rem;  /* 18px - Panel subheadings, modal sections */
  --text-xl: 1.375rem;  /* 22px - Brand titles, modal headers */
}
```

### 1.3 Elevation, Shadows & Spacing

```css
:root {
  /* Spacing Grid */
  --space-2: 0.125rem;  /* 2px */
  --space-4: 0.25rem;   /* 4px */
  --space-8: 0.5rem;    /* 8px */
  --space-12: 0.75rem;  /* 12px */
  --space-16: 1.0rem;   /* 16px */
  --space-24: 1.5rem;   /* 24px */
  --space-32: 2.0rem;   /* 32px */

  /* Radii */
  --radius-sm: 2px;     /* Micro badges, monospace tags */
  --radius-md: 4px;     /* Standard buttons, sliders, input fields */
  --radius-lg: 6px;     /* Panels, drawers, vehicle cards */
  --radius-full: 9999px;/* Status pills, indicator dots */

  /* Shadows */
  --shadow-hud: 0 4px 20px rgba(0, 0, 0, 0.6);
  --shadow-active: 0 0 12px rgba(212, 246, 106, 0.25);
  --shadow-danger: 0 0 12px rgba(255, 34, 17, 0.35);
}
```

---

## 2. Component Library Conventions

The VTX frontend is engineered without bloated frameworks. Components are self-contained Vanilla ES Modules that mount cleanly into the DOM.

### 2.1 Three-Panel Workspace Layout

The application viewport splits into three persistent or toggleable columns:

```
+-------------------------------------------------------------------------------------------------------+
| VTX TOP NAVIGATION BAR: Brand | Nav Tabs | Model Trigger | Environment Switcher | Active Sortie Pill  |
+------------------------------------+----------------------------------+-------------------------------+
| PANEL 1: LIVE COCKPIT              | PANEL 2: FLIGHT TEST DASHBOARD   | PANEL 3: PHYSICS EXPERIMENTS  |
| - 3D Three.js Viewport             | - Embedded IFrame / Route        | - Independent MuJoCo State    |
| - Floating HUD Drawers (Mission,   |   (`/dashboard/`)                | - Configuration Overrides     |
|   Controls, Airport Views)         | - 7 Flight-Test Evidence Gates   | - Batch Telemetry Comparisons |
| - 2D Tactical Minimap (Canvas)     | - Sortie Assessment Ledger       | - Diagnostic Artifacts        |
| - Phantom Fly-By-Wire Sliders      | - Checkpoint Recovery Logs       | - Model Fingerprint Hashes    |
+------------------------------------+----------------------------------+-------------------------------+
```

### 2.2 Environment Selector Group

Located in the top header and synchronized with the `#environment-select` model parameter:

```html
<div class="env-toggle-group" role="group" aria-label="Simulation Environment">
  <button id="env-airport" class="env-toggle-btn active" data-env="main-airport" title="Main Airport (8km x 8km)">
    <span class="env-dot"></span> AIRPORT
  </button>
  <button id="env-sandbox" class="env-toggle-btn" data-env="test-sandbox" title="Test Sandbox (Stage 1 Valley)">
    <span class="env-dot"></span> SANDBOX
  </button>
</div>
```

**Interaction Rules:**
1. Clicking an environment button issues `POST /api/environment` with `{ "environment": "main-airport" | "test-sandbox" }`.
2. **Active Sortie Invariant (HTTP 409):** If an aircraft is airborne or has unrecovered flight telemetry in progress, the backend responds with HTTP 409. The UI immediately displays an alert badge and prevents desynchronization.
3. On switch confirmation, the Three.js 3D scene clears and reloads the active `worldGroup`, swaps the terrain geometry/materials, resets lighting, and signals [`tactical-minimap.js`](file:///public/vtx-env/tactical-minimap.js) to switch bounds and pad coordinates.

### 2.3 Tactical Minimap Component

Implemented in [`public/vtx-env/tactical-minimap.js`](file:///public/vtx-env/tactical-minimap.js). Renders high-precision vector graphics on an HTML5 `<canvas id="tactical-minimap-canvas">`:
- **Main Airport Mode:** Bounds `[-4000, 4000]` m. Renders dual parallel runways (27L/09R), taxiways, aprons, terminal building footprint, and control tower glyph.
- **Test Sandbox Mode:** Bounds `[-500, 500]` m. Renders Stage 1 Valley canyon contours, perimeter safety boundary, river hazard polygon, and elevated rooftop landing pads (Pad A, Pad B, Pad C).
- **Vehicle Reticle:** Draws dynamic aircraft heading vector, ground track trail, velocity arrow, and altitude readout.

### 2.4 Floating HUD Drawers

Implemented in [`public/workspace-panels.js`](file:///public/workspace-panels.js). Three independently toggleable drawers float over the 3D viewport without obscuring center-of-flight sightlines:
1. **Mission HUD (`#mission-hud-drawer`):** Departure / destination point selectors, vehicle selector trigger, mission launch button, abort switch.
2. **Controls HUD (`#controls-hud-drawer`):** Fly-by-wire sliders (collective, tilt, throttle, road drive, DRS stabilator, landing leg extension, wing deployment locks), voice push-to-talk button (`🎙 Voice`).
3. **Airport Views HUD (`#views-hud-drawer`):** Camera presets (Chase, Cockpit 1st-person, Free Orbit, Tower, Runway Threshold).

---

## 3. Frameworks & Libraries

| Domain | Selected Technology | Rationale & Constraint |
| :--- | :--- | :--- |
| **3D Rendering** | Three.js (r128+) + OrbitControls | Hardware-accelerated WebGL 2.0. Native `.glb` PBR material pipeline. |
| **Client UI Architecture** | Pure Vanilla ES Modules (`import`/`export`) | Zero-compile, zero-transpile build step. Direct browser execution and high-cadence DOM updates without virtual DOM overhead. |
| **Simulator Backend** | Python 3.11+, FastAPI, Uvicorn | High-throughput asynchronous HTTP API and WebSocket streaming for telemetric frames. |
| **Physics Kernel** | MuJoCo (`mujoco>=3.1.0`) | 400 Hz rigid/multibody Newton-Euler dynamics, contact friction cones, joint constraints. |
| **Audio / Voice** | Web Speech API | Push-to-talk speech recognition matching a strict command grammar; no LLM in the control loop. |

---

## 4. Asset Management Pipeline

### 4.1 3D Model Assets (`public/assets/`)

1. **Authoritative Master Airframes:**
   - [`public/assets/phantom-a10b-visual.glb`](file:///public/assets/phantom-a10b-visual.glb): Production A10-B vehicle with 7° wing incidence, steered front wheel joints, animated ducted fans, DRS flap, and vectoring booster cowls.
   - [`public/assets/phantom-a10-visual.glb`](file:///public/assets/phantom-a10-visual.glb): High-detail visual pass model with smooth carbon livery and wing cassette detail.
   - [`public/assets/airframe-live.glb`](file:///public/assets/airframe-live.glb): Legacy R6 Argon test airframe.
2. **CAD Fallback:** Passing `?cad=1` in the cockpit URL dynamically switches the loader to raw mechanical CAD meshes for structural inspection.

### 4.2 Procedural Shaders & Environment Textures

- Airport runways, tarmac thresholds, centerlines, and runway lighting are rendered via custom procedural canvas shaders in [`public/vtx-env/`](file:///public/vtx-env/).
- Terrain heightfields use dynamic normal generation and distance-based level-of-detail (LOD) fog.
- Thruster exhaust effects utilize point-light bloom and particle trails tied directly to simulated mass flow and Newton thrust.

---

## 5. Iconography & Tactical Status Indicators

VTX utilizes a minimalist vector and Unicode iconography system to minimize asset dependencies and guarantee crisp rendering at high DPI:

```
[▲] Pitch Up / Climb       [▼] Pitch Down / Descent
[◀] Roll Left / Steer L     [▶] Roll Right / Steer R
[◆] Active Sortie In Progress
[●] Grounded / Standby
[🎙] Voice Command Active (Flashing Amber on listening)
[⛶] Free Roam Camera
[⚙] Engineering / Configuration Overrides
[✓] Pre-flight Check Passed
[✕] System Fault / Stall Warning
```

### Status Lamp Component (`.vtx-lamp`)

```css
.vtx-lamp {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--dim);
  transition: all 0.2s ease;
}

.vtx-lamp.live {
  background: var(--accent);
  box-shadow: 0 0 8px var(--accent);
}

.vtx-lamp.alert {
  background: var(--accent-danger);
  box-shadow: 0 0 8px var(--accent-danger);
  animation: vtx-pulse 1s infinite alternate;
}

@keyframes vtx-pulse {
  from { opacity: 0.4; }
  to { opacity: 1.0; }
}
```

---

## 6. Styling Approach & Code Snippets

### 6.1 Scoped Class Namespaces

- `.workspace-*`: Main application layout, top navigation, and responsive panels.
- `.hud-*`: Overlay drawers, floating flight cards, minimap wrappers.
- `.ctrl-*`: Fly-by-wire sliders, toggle levers, and command buttons.
- `.env-*`: World environment toggle buttons and status badges.
- `.gauge-*`: Dial instruments, numeric airspeed/altitude HUD readouts.

### 6.2 Responsive Panel Stacking

Desktop displays maintain a 3-column split view. Viewports below 800px gracefully stack into a single scrollable tactile interface:

```css
.workspace-container {
  display: grid;
  grid-template-columns: minmax(420px, 1.4fr) minmax(360px, 1.1fr) minmax(340px, 1fr);
  height: calc(100vh - 48px);
  width: 100vw;
  overflow: hidden;
  background: var(--bg-deep);
}

@media (max-width: 1200px) {
  .workspace-container {
    grid-template-columns: 1fr 1fr;
  }
  #experiments-column {
    display: none; /* Accessible via top tab toggle */
  }
}

@media (max-width: 800px) {
  .workspace-container {
    display: flex;
    flex-direction: column;
    height: auto;
    overflow-y: auto;
  }
  .workspace-column {
    min-height: 480px;
    border-bottom: 1px solid var(--line);
  }
}
```

### 6.3 Environment Selection Dispatch Pattern

```javascript
// public/app.js - Environment switching integration
async function switchEnvironment(targetEnv) {
  try {
    const res = await fetch('/api/environment', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ environment: targetEnv })
    });
    
    if (res.status === 409) {
      const data = await res.json();
      showToastAlert(`Cannot switch world: Active sortie in progress (${data.detail})`, 'danger');
      return;
    }
    
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    
    // Update active UI button states
    document.querySelectorAll('.env-toggle-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.env === data.environment);
    });
    
    // Swap 3D world meshes and update tactical minimap
    await loadSimulationWorld(data.environment);
    tacticalMinimap.setEnvironment(data.environment);
    showToastAlert(`Simulation world switched to ${data.environment.toUpperCase()}`, 'success');
  } catch (err) {
    console.error('Environment switch failed:', err);
    showToastAlert('Failed to switch simulation world', 'danger');
  }
}
```

---

## 7. Project File Structure

```
vtx-three-panel-20261110/
├── public/
│   ├── index.html                # Single-origin cockpit entrypoint
│   ├── app.js                    # Cockpit bootstrap, 3D render loop, environment coordination
│   ├── workspace-theme.css       # Core design tokens, dark cockpit themes, responsive grid
│   ├── style.css                 # Legacy controls styling and gauge layouts
│   ├── workspace-panels.js       # Mission, Controls, and Airport Views drawer management
│   ├── model-selector.js         # Aircraft selection modal and variant switcher
│   ├── phantom-controls.js       # Phantom fly-by-wire sliders and voice HUD
│   ├── vtx-env/
│   │   ├── tactical-minimap.js   # 2D Canvas radar with dual-environment projection
│   │   ├── airport-world.js      # Main Airport 3D terrain, runways, towers, and lighting
│   │   ├── sandbox-world.js      # Test Sandbox Stage 1 Valley terrain and obstacle meshes
│   │   └── light-pool.js         # Dynamic vehicle thrust and landing light manager
│   └── assets/                   # Binary 3D models (.glb) and vehicle textures
├── src/vtx/
│   ├── live_server.py            # FastAPI server, /api/environment, telemetry websockets
│   ├── world.py                  # MuJoCo world generator (Airport vs. Sandbox heightfields)
│   ├── aircraft.py               # Multibody kinematics and MuJoCo XML builders
│   ├── aero.py                   # Blade element momentum & wing aerodynamic polar equations
│   └── dashboard_site.py         # Unified 3-panel dashboard server mount
├── docs/                         # Flight records, engineering contracts, and pilot specs
├── evidence/                     # Authenticated sortie logs, black-box data, and test renders
├── DESIGN_SYSTEM_RULES.md        # This specification
└── README.md                     # Game overview, pilot guide, devlog, and architecture blueprint
```
