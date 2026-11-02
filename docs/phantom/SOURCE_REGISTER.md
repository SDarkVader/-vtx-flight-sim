# Phantom technical documents and evidence register (P0)

**Purpose:** source-backed reading list for implementing a **simulated** two-seat high-speed VTOL/rolling-takeoff craft. An external document can justify equations or suggest a candidate hardware envelope; it never proves that *our* model has that component or rating.

Labels: **SOURCE_VERIFIED** = primary source was found; **SOURCE_EXTERNAL** = evidence for a different machine; **CALCULATED_ASSUMPTION** = derived from stated synthetic inputs; **UNKNOWN** = must be modelled or measured; **NOT_SELECTED** = not approved or procured.

## Primary documents to keep

| ID | Subject / direct source | How used / status |
| --- | --- | --- |
| S01 | [EASA SC-VTOL Issue 2, structures and operational envelope](https://www.easa.europa.eu/en/downloads/139946/en) | **SOURCE_VERIFIED**: design envelope, structural control inputs, aeroelasticity, gust/load cases and systems/structure interaction are comprehensive modelling prompts. **Caution:** this regulatory special condition is not automatically applicable to 400 mph design: SC-VTOL Issue 2 defines Vno up to 250 KCAS for its type-applicability boundary; this is a *simulation research guide*, not a compliance claim. |
| S02 | [NASA F/A-18 / X-53 Active Aeroelastic Wing project](https://www.nasa.gov/reference/active-aeroelastic-wing/) | **SOURCE_VERIFIED / EXTERNAL**: flight-tested deliberate wing twist and independently controlled leading-edge flaps for roll authority. Demonstrates why compliance and aileron reversal deserve modelling; does not supply Phantom aeroelastic limits. |
| S03 | [SKF steel/PTFE spherical plain bearing manufacturer catalogue (PDF)](https://www.skf.com/binaries/pub12/Images/0901d19680154a05-06116_1-EN_tcm_12-122020.pdf) | **SOURCE_VERIFIED / NOT_SELECTED**: e.g. GEH 50 TXE-2LS, 50×90×56 mm, basic radial dynamic 695 kN, static 1,160 kN; GE 80 TXE-2LS, 80×120×55 mm, C 1,140 kN / C0 1,900 kN. These are *bearing ratings*, not root-assembly safe loads. |
| S04 | [RBC Aerospace spherical plain bearing catalogue](https://www.rbcbearings.com/Engineering/Spherical-Plain-Bearings), [AS81820 type technical PDF](https://www.rbcbearings.com/pdfs/aero/Plain/018_050/SB_M81820_4%20_1.pdf) | **SOURCE_VERIFIED / NOT_SELECTED**: aerospace bearing family, oscillating radial/limit ratings and axial limits depend on **dash number** and actual installation. Needs supplier selection; manufacturer engineering consultation for high loaded root. |
| S05 | [Curtiss-Wright rotary geared Power Hinge actuators](https://actuation.curtisswright.com/en-gb/aerospace-products/aerospace-actuators/rotary-geared-actuators) | **SOURCE_VERIFIED / NOT_SELECTED**: manufacturer lists wing-fold and leading/trailing-edge flap applications. Bespoke part number/torque-speed, thermal, backlash and dimensions need request. |
| S06 | [Safran TG600 / Aura Aero official announcement (27 July 2026)](https://www.safran-group.com/pressroom/safran-signs-agreement-aura-aero-develop-turbogenerator-propulsion-system-era-hybrid-electric-2026-07-27-0) | **SOURCE_VERIFIED / EXTERNAL**: two 600 kW turbogenerators for a 19-seat aircraft; proves commercial existence of relevant power class, **not** installation compatibility with Phantom. |
| S07 | [EASA special condition electric/hybrid propulsion guidance](https://www.easa.europa.eu/en/domains/rotorcraft-vtol/VTOL) | **SOURCE_VERIFIED / GUIDE**: refer to SC E-19 electric/hybrid systems documents from EASA VTOL library for hazard/fault categories. Does not produce our specific DC bus or battery ratings. |
| S08 | [Static and Dynamic Aeroelastic Analysis of Structural Wing Fold Hinges, AIAA DOI 10.2514/6.2004-1754](https://doi.org/10.2514/6.2004-1754) | **LITERATURE**: compliant structural wing-fold hinges affect flutter and divergence. Need coupled dynamic model and real hinge stiffness rather than unsupported free pivot. |
| S09 | [Multibody Dynamic Aeroelastic Simulation of a Folding Wing Aircraft, DOI 10.2514/6.2006-2135](https://doi.org/10.2514/6.2006-2135) | **LITERATURE**: multibody wing-fold state and flexible structures can be coupled to aerodynamics and flight controls. |
| S10 | [Aileron Reversal of Nonuniform and Swept Composite Aircraft Wings, DOI 10.2514/1.C031212](https://doi.org/10.2514/1.C031212) | **LITERATURE**: swept carbon-composite bending/twist may reduce/reverse control effectiveness. |
| S11 | [VTX proprietary physics/research baseline](../PHYSICS_AND_RESEARCH_BASELINE.md), [live pilot contract](../LIVE_FLY_BY_WIRE_PILOT_CONTRACT.md) | **ACTUAL_REPO_SOURCES**: mass/energy ledger, no free lifts, angular momentum, honest failure, human/Colin control parity. Preserve original airframe. |
| S12 | [Current Phantom engineering investigation](https://app.notion.com/p/40c59e49d35c8105b78de2af8c276039), [Blendstra A8 pinned](https://blendstra.com/studio?workspace=wsp_816786f2f8ced68922a0d7b529616880cf8b6f22&project=b77e9377-f1b3-4177-ba4e-c1af1d4ed8b2&version=version_a5589426caea8f9c2a6b690671aa8a9387ceff32eaef358186236dbd4de18752) | **ACTUAL_PROJECT_SOURCES**: shape, root objections, 2 occupants, dual-mode take-off, user intent. CAD is a reference and contains wing clipping; actual area/CG/wing-pivot response not validated. |

## Manufacturer information needed **only if exact hardware will be selected**

- Wing root: actual spar lock/gimbal drawing, joint load directions, **oscillating** bearing radial and axial ratings, ultimate and fatigue, pin shear/bending, composite bonded-metal insert details, bolt spacing, housing stiffness, allowable deflection, service cycle and misalignment; supplier load rating must exceed **the actual operating and failure envelope**, not our assumed 12g sketch alone.
- Wing actuation, flaps/ailerons: torque-speed-continuous vs peak curves, travel, temperature, backlash, dynamic stiffness, fail-safe/lock states, 3D STEP, control loop and power supply.
- Power plant / HV: shaft-power vs spool vs fuel flow, generator efficiency, DC voltage/current limits, buffer energy and discharge map, motor torque-speed curve, propulsor thrust vs power/airspeed, radiator and inverter thermal maps, fuel path and rear-nozzle power balance.
- Aerodynamics: actual aerodynamic section, chord/span, airfoil polars vs Reynolds/Mach, control hinge-moment coefficient derivatives, pressure distributions, pitching moments, stall/post-stall behaviour, flap delta-CL/CD, aeroelastic modal parameters.
- Cooling: inlet total pressure recovery, duct area vs flow, cooling core pressure drop, temperature, heat extraction, downwash/hover recirculation. A painted/uncapped port isn't tested cooling.

## Rig-only substitute rules

When a specific manufacturer curve isn't available, put a **labelled synthetic response** in a versioned parameter file with actual numerical cap, response, rate, energy and thermal accounting. Mark it `SYNTHETIC_UNVALIDATED` and record what evidence would supersede it. That permits experimentation in a game; it doesn't permit claiming a real airframe/hardware can perform the manoeuvre.

## Source acquisition check

Links above are official manufacturer, agency and research-publisher pages. Save references as links or locally obtained PDFs with publisher/title/retrieval date and copyright provenance; **do not** redistribute proprietary manufacturer documents into the public game bundle. No complete hardware/CFD catalogue has been supplied, and no final wing, bearing or generator has been selected.
