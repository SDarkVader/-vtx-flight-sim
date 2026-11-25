extends SceneTree
## Headless radio fixture. No cockpit scene, network, simulator or saved flight.
## Usage: godot --headless --path native --script ../tests/native_cockpit_radio.gd -- --music=<folder>

const Radio = preload("res://radio/cockpit_radio.gd")
var failures: Array[String] = []
var checks := 0


func check(condition: bool, label: String) -> void:
	checks += 1
	if not condition:
		failures.append(label)


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	var music := ""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--music="):
			music = argument.trim_prefix("--music=")
	check(Radio.step_track(0, -1, 15) == 14, "previous wraps")
	check(Radio.step_track(14, 1, 15) == 0, "next wraps")
	check(Radio.step_track(0, 1, 0) == -1, "empty list")
	check(Radio.title_of("C:/m/Where_Iron_Ends.mp3") == "Where Iron Ends", "title")
	var radio: PanelContainer = Radio.new()
	radio.settings_path = "user://radio_fixture.cfg"
	DirAccess.remove_absolute(radio.settings_path)
	root.add_child(radio)
	await process_frame
	radio.use_folder(music, "")
	var count: int = radio.tracks.size()
	check(count > 1, "tracks found")
	var unreadable := 0
	for path in radio.tracks:
		if Radio.load_stream(path) == null:
			unreadable += 1
	check(unreadable == 0, "every track decodes")
	radio.set_power(true)
	await process_frame
	check(radio.powered and radio.player.playing, "plays")
	radio.change(1)
	check(radio.index == 1 and radio.player.playing, "next song plays")
	radio.knob.turned.emit(-2)
	check(radio.index == count - 1, "knob steps back")
	radio.knob.start_drag(0.0)
	radio.knob.drag_to(65.0)
	check(radio.index == 1, "knob drag turns two songs")
	for code in [KEY_PERIOD, KEY_COMMA, KEY_SLASH]:
		var event := InputEventKey.new()
		event.physical_keycode = code
		event.pressed = true
		root.push_input(event)
		await process_frame
	check(radio.index == 1 and not radio.powered, "keys change song and switch off")
	var outside: float = radio.player.volume_db
	radio.set_camera_mode(1)
	check(radio.player.volume_db > outside, "louder in the forward view")
	radio.save()
	var again: PanelContainer = Radio.new()
	again.settings_path = radio.settings_path
	root.add_child(again)
	await process_frame
	check(again.index == 1 and again.folder == music, "remembers folder and song")
	DirAccess.remove_absolute(radio.settings_path)
	print("radio checks %d, failures %s, tracks %d" % [checks, str(failures), count])
	quit(1 if failures.size() else 0)
