# R6 with the fan drive connected through the tilt pivot

This is the repaired geometry state saved on 24 Nov 2026 at the owner's request. It is the r2 model (`airframe-r6-connected-r2.glb`, `0e91bb06…`) plus 12 nodes that connect each fan's transmission. The file `r6-r3-drive-connected.glb` (sha256 `e473b77d…`) is built by `tools/visual_r6/r6_drive_through_pivot.py`.

For each fan:
- the rising spindle is extended to 10 mm past the physics tilt pivot (z 1.98 m);
- a CV joint sits on the pivot: a ball plus a race;
- a nacelle stub shaft runs from the pivot into the bottom of the nacelle gearbox.

**Checks:**
- Every link from the radial shaft to the gearbox touches in every physics pose.
- The connectivity audit (`r3_candidate_audit.json`) matches r2 exactly.

**Status:** saved, not adopted. The cockpit still shows r2, and physics (`model.xml`) is unchanged. The CV geometry is placeholder art, not a real part; see `../DRIVE_REAL_COMPONENTS.md`.
