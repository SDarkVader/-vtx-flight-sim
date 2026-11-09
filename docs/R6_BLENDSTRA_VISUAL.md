# R6 Blendstra visual integration

The supplied Blendstra project `dde793df-08cb-4ccd-9faa-e088dadc4382`, version
`version_c94fd5e07c9787a4dd3f90f51cb80184186bad4c33a0edba0e62479571498393`,
is the visual reference for the current R6. Its exported model is retained at
`assets/reference/r6-blendstra-reference.glb` (SHA-256
`58ff9950622f7a3fce63aa3c1e9fc50cefe717e42506fb5bebfd25dea06a727c`).

`tools/rig_blendstra_r6.py` builds the browser derivative from that export and
the existing simulator rig. All 691 supplied meshes are included. Of these,
667 share stable part IDs with the existing R6 visual derivative; their
physical-body assignments and blade pitch axes are copied by ID. Eight duct
decorations follow their nacelles, and 16 other source-only meshes follow the
airframe. The previously supplied simulator derivative contains 64 meshes
whose IDs do not appear in the Blendstra export. The two visual assemblies are
therefore related but not identical.

The existing R6 ledger and MuJoCo model continue to define mass, collisions,
actuation and physics. The source-only visual pieces do not add physical mass
or collision geometry. The local rendering finish applies dark carbon and
glazing, white outer ducts and checker livery; the exported source band is
positioned on the lower rim to match the supplied screenshots. The simulator
asset and scripted traffic both use the rigged visual derivative.

The browser pass showed the model on the stand, the scripted training aircraft
moving on its route, and the four ducts following simulated nacelle motion in
an isolated engine-off ground test. The same test showed unpowered nacelle
feedback drifting away from the requested tilt, so it is evidence of visual
articulation, not of powered control tracking or flight handling.
