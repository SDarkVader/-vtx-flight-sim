# Cockpit radio: adding it to a Windows build

**Status: a development component, not yet part of the game.** Headless checks pass. It has not been launched inside the full application, so its position on screen and its sound are unchecked. No music is included.

## Bring it in

The whole radio is one commit, `6e710bd`, made on top of `6e4edee` (`codex/vtx-native-windows-update-20261125`).

```powershell
git cherry-pick 6e710bd
```

If your build has moved on and `native/main.gd` conflicts, copy this folder and make these four edits to `main.gd`:

1. Next to the other preloads:

   ```gdscript
   const CockpitRadio = preload("res://radio/cockpit_radio.gd")
   ```

2. Next to the other HUD variables:

   ```gdscript
   var radio: PanelContainer
   ```

3. In `create_hud()`, just before `make_controls_panel(hud)`:

   ```gdscript
   # Not part of the graphics or readiness checks.
   if not (benchmark_requested or verify_only):
   	radio = CockpitRadio.new()
   	hud.add_child(radio)
   	radio.add_theme_stylebox_override("panel", tray_style())
   	radio.set_anchors_and_offsets_preset(Control.PRESET_CENTER_RIGHT, Control.PRESET_MODE_MINSIZE, 22)
   	radio.grow_horizontal = Control.GROW_DIRECTION_BEGIN
   	radio.grow_vertical = Control.GROW_DIRECTION_BOTH
   ```

4. In `set_camera_mode()`, after `camera_mode = mode`:

   ```gdscript
   if is_instance_valid(radio):
   	radio.set_camera_mode(mode)
   ```

## Check it

With Godot 4.7.2, import the project once, then run the headless fixture against any folder holding at least two songs:

```powershell
godot --headless --path native --editor --import
```

```powershell
godot --headless --audio-driver Dummy --path native --script "$PWD\tests\native_cockpit_radio.gd" -- "--music=C:\path\to\songs"
```

## Using it

- Music comes from `Music\VTX Audio\Vehicle\Phantom A10-D\Sounds\Radio` when that exists; **Music folder** picks any other. MP3, OGG and WAV play.
- Drag or scroll the knob to change song. Comma and full stop step through songs; slash switches on and off.
- It is louder in the Forward camera view.
- The folder chooser takes window focus, so use it before a flight.
- No Xbox controller bindings yet.

## Vehicle sound

Nothing here adds vehicle sound. The design work and the rules that drive each sound from flight data are in [`tools/sound-studio`](https://github.com/SDarkVader/-vtx-flight-sim/tree/claude/sound-studio-dev-20261125/tools/sound-studio) on the development branch.
