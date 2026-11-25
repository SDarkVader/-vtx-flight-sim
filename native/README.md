# VTX Native Flight

Local Windows x64 G1 development prototype. Extract the complete folder, then run VTX Native Flight.exe. The game starts its own bundled Python/MuJoCo simulator on a private loopback port. It saves into a fresh session under the VTX Native Prototype app data folder. The packaged runtime and game folders stay beside the executable.

## Run the Meridian graphics test

In the Meridian Graphics package, open **Run Meridian Graphics Test.cmd**. It opens the standalone Windows renderer at 1920×1080 and 100% render scale with the Prototype High settings and 60 fps cap. The same westbound route runs twice. The first pass warms up the populated city and the second collects draw intervals and viewport rendering timings. Both passes use the fixed chase camera and a recorded Phantom A10-D. No flight inputs are needed. The benchmark exits after writing the receipt to **%LOCALAPPDATA%\VTX Meridian Graphics**. Run with the window visible for a representative desktop comparison.

The benchmark uses recorded aircraft poses and no running solver. Its timing measures completion of the Godot frame and viewport rendering. A monitor presentation trace and live snapshot delivery and physics metrics require a separate capture.

## Fly with an Xbox One Bluetooth controller

Connect the controller to Windows and bring the game window into focus. At **Ready**, look for the pad name in the footer, centre both sticks, release the triggers and press **Menu**. This starts the Phantom A10-D in VTOL configuration and arms that pad. If you start with Enter or the mouse, click the left stick to arm. **Y** opens the control card. It stays available in flight.

| Action | Xbox One | Keyboard |
| --- | --- | --- |
| Pitch nose up / down | Left stick back / forward | W / S |
| Roll left / right | Left stick left / right | A / D |
| Yaw left / right | Right stick left / right | Q / E |
| Increase / decrease collective | RT / LT, proportional to squeeze | R / F |
| Increase / decrease both boosters | Hold RB / LB | Hold T / Y |
| Retract / extend all four landing legs | A | L |
| Deploy / stow wings and canards | X / D-pad left | G / H |
| Set pods vertical (90°) / forward (0°) | D-pad up / down | 1 / 2 |
| Apply / release all four wheel brakes | D-pad right | K |
| Engage / release ECU airbrake | Hold B for half a second | B |
| Return to attitude mode with direct collective | Right stick click | M |
| Cycle chase, forward, Meridian and close orbit cameras | View | C |
| Close orbit, then move and zoom | — | O, then right-drag / mouse wheel |
| Start / pause or resume | Menu | Enter to start, P to pause or resume |
| Arm a centred pad during a manual flight | Left stick click | F2 |
| Show / hide controls | Y | F1 |
| Close the app | Window close button | Esc |

Pitch, roll and yaw can be combined with collective and paired boosters. Each stick axis has a 15% centre dead zone and scales to full command beyond it. Triggers have a 5% dead zone. At full input the collective changes by 42 percentage points per second and the boosters by 40. Releasing the controls holds the last power demands. Keyboard pitch, roll and yaw retain their original limits.

The landing-leg readout shows the requested position and each measured extension in metres, front left through rear right. Fully extended is 0.52 m. A mixed leg setting goes to full extension on the next press. Wing and pod actions go through the aircraft’s existing control system. The airbrake engages vertical-speed mode, points the pods down and idles the boosters. Click the right stick or press M to return to direct collective.

After a disconnect, focus loss, pause or telemetry interruption, centre the pad and click the left stick to re-arm. The keyboard remains available. The game reads one mapped Xbox or XInput device and shows its name in the footer.

The close orbit starts 20 m from the Phantom and also works while paused. Use the wheel to adjust distance from 12 to 60 m.

## Build developer notes

Use Godot 4.7.2 with its matching verified Windows x64 export template and the verified CPython 3.14.3/MuJoCo 3.17.0 runtime from the VTX preview staging directory. Run build_windows.py with those paths and a new output directory. It exports and bundles an offline executable with the reviewed simulator files. For editor runs, set VTX_NATIVE_BUNDLE_ROOT to an unpacked bundle.

Use --benchmark-data with the verified directory containing world.json, route.json and provenance.json to include the Meridian workload and launcher. The executable also accepts --meridian-benchmark=/absolute/data/path and --graphics-receipt=/absolute/result.json as user arguments after --.

The executable has a readiness-only mode and a headless control smoke mode. Run with an absolute receipt path after the Godot argument separator. The readiness mode checks the native renderer, world and aircraft before an active flight starts. The control smoke starts and briefly exercises an isolated simulator session.
