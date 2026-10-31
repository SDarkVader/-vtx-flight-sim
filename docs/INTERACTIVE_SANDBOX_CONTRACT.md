# Physical flight-test world

The environment must be a meaningful navigable 3D world with scale, terrain, obstacles, ground/structure collisions and multiple viable departure and landing surfaces, not a small scripted viewer. Engine choice is Colin's engineering decision; full-screen or standalone access is acceptable.

Aircraft geometry and physical parameters must come from the editable VTX mechanical assembly. Forces and torques follow its actual simulated structure, joints, rotor drives and actuators. Render the physical state, including crashes and destroyed/collided configurations when modelled; do not control physical state with animation.

The proprietor selects any valid departure and destination on the map, with visible reasons why a location is invalid. Flight starts on the ground and ends with actual contact and settling, or failure. Show the four independently commanded and moving rotors and relevant pilot observations/controls.

Do not install a flight-perfect controller as an invisible safeguard. The pilot must learn through interacting with the simulated aircraft. Flight experiments need audit logs: initial conditions, model revision, permitted observations, actions, learning updates, contact events, faults and outcomes.

Reproducibility of physics and replay is required; consistently passing a mission is not. Successful flights cannot be manufactured by adjusting arbitrary physical parameters.

Missing calibration/geometry is a real blocker for the corresponding flightworthiness claim. Interim assumptions, derived bounds and separate sensitivity experiments must be identified, not disguised as known aircraft facts.
