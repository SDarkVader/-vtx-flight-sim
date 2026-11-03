# Recovered Argon flight-control source

These files are recovered unchanged in content from Git commit `063ff3d` (apart from text encoding) to preserve the actual controller used for the recorded trials. They are historical test scripts, not a reusable stability-control implementation. Do not run them as a default: they initiate missions, contain scripted flight profiles, and target a different server port and historical clearance convention. Extract and test the control laws against the current R6 gimbal, sensors and actuator limits before integration.
