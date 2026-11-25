# VTX Native Flight

Local Windows x64 G1 development prototype. Extract the complete folder, then run VTX Native Flight.exe. The game starts its own bundled Python/MuJoCo simulator on a private loopback port. It saves into a fresh session under the VTX Native Prototype app data folder. The packaged runtime and game folders stay beside the executable.

## Flight controls

| Key | Control |
| --- | --- |
| Enter | Start the Phantom A10-D in VTOL configuration |
| R / F | Increase / decrease collective |
| W / S | Pitch |
| A / D | Roll |
| Q / E | Yaw |
| G | Deploy wings and canards |
| 1 / 2 | Pod angle 90° / 0° |
| T / Y | Increase / decrease boosters |
| C | Chase, forward view and Meridian overview |
| P | Pause / resume |
| Esc | Close the app and its local simulator |

Allow the cockpit to report Ready before starting flight. Increase collective gradually and use the vertical speed instrument when lifting from the runway. The solver uses the reviewed Phantom A10-D and Vaderland 33.1 source. The native renderer reconstructs surveyed terrain, structures and streets and supplies a dusk presentation. The build is a prototype for native readiness and flight tests. The full visual port and performance certification are later milestones.

## Build developer notes

Use Godot 4.7.2 with its matching verified Windows x64 export template and the verified CPython 3.14.3/MuJoCo 3.17.0 runtime from the VTX preview staging directory. Run build_windows.py with those paths and a new output directory. It exports and bundles an offline executable with the reviewed simulator files. For editor runs, set VTX_NATIVE_BUNDLE_ROOT to an unpacked bundle.

The executable has a readiness-only mode and a headless control smoke mode. Run with an absolute receipt path after the Godot argument separator. The readiness mode checks the native renderer, world and aircraft before an active flight starts. The control smoke starts and briefly exercises an isolated simulator session.
