# A10-C measured suspension schematic

The owner requested a clearly identified schematic tied to measured suspension.
This separate overlay depicts the model's front suspension slides with cyan
datums/guides and orange moving carriers. It is a diagram, not recovered actuator
hardware or a structural design. It adds no mass, collision shape, force or
aircraft trajectory.

The cockpit's **Suspension schematic** button is off by default. Enable it
only when inspecting the physical reference; the normal authored aircraft
view remains clear. The cyan/orange graphics are not structural mounts on the
visible B model. Engineering reports the reference/visual offsets separately.

## Files

- Editable Blender master: `assets/derived/phantom-a10c-suspension-schematic.blend`.
- Browser derivative: `public/assets/phantom-a10c-suspension-schematic.glb`.
- Generator: `tools/phantom/build_suspension_schematic.py`.
- Standalone preview: `assets/derived/phantom-a10c-suspension-schematic.png`.

The current GLB SHA-256 is
`c571a3bcbcebd67651c5f202e566a9762460cc7819da20feb3f99de1e08466e5`.
The per-candidate descriptor in
[`inputs/flight_revisions.json`](../../inputs/flight_revisions.json) records it;
the browser verifies fetched bytes before parsing. A missing or changed asset
is reported rather than replaced.

The preview uses an illustrative selected slide of -0.20 m. It is not a recorded
flight state. The master and GLB retain a zero-displacement rest pose.

The original `phantom-a10b-visual.glb` and previous provisional
`phantom-a10c-parts.blend/.glb` are preserved. The overlay is loaded separately;
it is not merged into or substituted for the original flown visual.

## Physical basis and presentation choices

The recorded A10-C model places `pod_FL` at `[1.54,+1.25,0.61]` m and `pod_FR` at
`[1.54,-1.25,0.61]` m in the airframe. Each wheel body starts at pod-local zero;
`pod_FL_susp` and `pod_FR_susp` slide along pod-local +Z. Physical FL is positive
Y. Original B mesh names use a different side naming convention; use the
`phantom_joint` mapping, not the mesh name.

These datum origins and axes are from the recorded model. The graphic dimensions
below are selected only for legibility:

| Graphic | Cosmetic dimensions |
| --- | --- |
| Guide | z -0.36 to +0.14 m; x offset +0.12 m |
| Datum ring | radius 0.075 m |
| Carrier ring | radius 0.055 m |
| Display offset | pod-local y ±0.115 m, plus 0.012 m for orange graphics |
| Tick spacing | 0.10 m; ticks are a ruler, not physical travel stops |
| Connection indicator | unit-Z mesh scaled to measured displacement |

The model provides no actuator rod or upper/lower structural hardpoints. The
schematic does not claim them. It does not display `nose_lift_m` as measured rod
travel; that value controls the suspension spring-seat reference and remains a
separate readout.

The B visual's authored pod datum is y ±1.04 m, z 0.42 m; the recorded physical
pod datum is y ±1.25 m, z 0.61 m. The authored tyre radius is approximately
0.36 m while the physical collider radius is 0.55 m. Enlarging and relocating
only the visible wheels to those collision values disrupted the assembly fit
and failed cockpit acceptance. The authored geometry is restored; this
optional reference continues to show the measured physical datums without
claiming that they coincide with the visible hardware.

## Runtime node contract

Root: `VTX_A10C_SUSPENSION_SCHEMATIC`.

For each physical side `FL` / `FR`:

- `VTX_SCHEMATIC_<side>_POD`: nominal pod origin, with `source_body` and
  `source_joint` extras. Runtime expresses the measured pod world pose in the
  measured airframe frame and assigns that local position/rotation. This follows
  the physical pod even when the aircraft and pod rotate.
- `VTX_SCHEMATIC_<side>_CARRIER`: local +Z displacement from the measured
  wheel-to-pod displacement projected onto pod-local +Z. Both positions and the
  pod quaternion come from the same body-pose snapshot. `q_rest=0`; missing or
  inconsistent measurements mean unavailable. The separately measured suspension
  joint value remains in Engineering because it can be one 400 Hz integration
  step newer than the body poses.
- `VTX_SCHEMATIC_<side>_CONNECTOR`: graphical displacement line with a unit-Z
  child mesh spanning z 0..1. For measured body displacement `d`, set its local z
  to `min(0,d)` and z scale to `abs(d)`,
  and hide at zero. Its source asset starts at zero z scale.
- `GUIDE`, `DATUM`, `DATUM_CROSS`, and `TICK_*` are fixed reference graphics.

Use measured pod/wheel state from the same timestamp; never drive this overlay
from a command or the spring-seat target. Keep it hidden until its identity and
required state are available. Live cockpit verification is a separate required
check. The off → on → off control and missing/stale status behavior were checked
in the actual cockpit on 15 November. The restored normal view and fully
deployed canards/wings were inspected after the wheel-size correction; owner
flight acceptance remains separate.

## Rebuild

```text
blender --background --python tools/phantom/build_suspension_schematic.py
```

The script creates only these new named schematic outputs. The lightweight GLB
contains no cameras or lights; the editable master retains an inspection camera.
