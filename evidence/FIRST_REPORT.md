# Initial source and engineering report — 31 October 2026

Retrieved the GitHub contracts at `47f45f4`, read every linked mission, physics,
live fly-by-wire, map, world and transfer contract, and preserved their bytes
during selective starter import. The user's latest instructions supersede old
instructions in the handoff. See `source/handoff_verification.json`.

The handoff's outer manifest verifies all 10 listed files. The inner starter
manifest verifies all 27 listed files. Imported source, tests, inputs, source art,
historical PDFs and configuration; retained older contracts inside the original
archive only. The ZIP supplies a snapshot, not the Git bundle/history at e768250.
Executed its tests unchanged: **31 passed**. These are numerical and selection
checks, not flight evidence.

Retrieved the exact editable Blendstra P0-V4A master (15,174,512 bytes, SHA-256
`2db9abd64ba9b7078e6e539ba4c6b9177e58e335a085a8ea213b5ffa6e987e35`)
and GLB (10,554,920 bytes, SHA-256
`17c99a9d9b31b4075bf71d4d5575e2176e8e4d9f5afb3a923058e29311170727`).
Retrieved all 46 private engineering review entries, including the six canonical
literature records. Their data and limitations are preserved locally. No newly
obtained full-text papers or supplier component qualifications are claimed.

Read the supplied P0-V1 performance and costing PDFs as historical evidence.
The supplied P0-V4 algebra model explicitly rejects missing calibration; the urban
reference is kinematics, not a flight controller. Neither drives the live plant.
The supplied concept images are visual ideas, not dimensional or aerodynamic proof.

The source contains 823 objects and 11 subsystem roots. Its V4 allocation fields
give [132,163,91,88,35,128,48,28,27,42,61] kg = **843 kg empty allocation**.
170 kg occupants and 60/110 kg fuel give **1,073/1,123 kg** scenario masses.
Old mass fields coexist and are not the current ledger. These are allocations,
not physical weighing or material-volume-derived masses.

Source geometry provides rotor pivots at (±2.6,0,2.31), (0,±2.6,2.31) m,
orthogonal X/Y tilt rigs, separate spin shafts, actual blade meshes, diagonal
fuel cells (authored inner radius .18 m, length .48 m), and six .35 m contact
feet at radius 1.9 m. Fuel geometric volume ~195.43 L; 85% usability and
.8 kg/L density are assumptions. Contact stroke .25 m is a design target.
Native Blender 4.3.2 warns the master was written by a newer version; the
original is preserved and derivative exports need correspondence checks.

Actual component masses, internal distribution, rotor inertia, airfoil polars,
pitch/RPM/inflow maps, turbine installed power and transient response, shaft/CV
ratings, joint/laminate strengths, gear spring/damper curves, fuel slosh and
usable capacity remain **CALIBRATION_BLOCKED**. The saved design contains
gearbox and joint envelopes, not a manufactured transmission.

At this report's checkpoint, implementation consists of verified source import,
source inventory tooling, provenance records and the unchanged numerical starter.
No live aircraft dynamics, flight world, successful takeoff or learned VTX pilot
is claimed at this checkpoint. Subsequent implementation and real attempts must
be recorded separately with their explicit assumptions and failures.
