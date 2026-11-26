extends PanelContainer
## Cockpit radio. Plays the player's own music from a folder on this PC; no audio ships with the game.
## It reads no flight data and sends no commands.

const FORWARD_CAMERA := 1
const OUTSIDE_LEVEL := 0.5
const DEGREES_PER_SONG := 30.0
const BUS := &"CockpitRadio"
const DEFAULT_SUBFOLDER := "VTX Audio/Vehicle/Phantom A10-D/Sounds/Radio"
const EXTENSIONS := ["mp3", "mpeg", "ogg", "wav"]

var settings_path := "user://cockpit_radio.cfg"
var folder := ""
var tracks: PackedStringArray = []
var index := -1
var powered := false
var volume := 1.0
var in_cockpit := false

var player := AudioStreamPlayer.new()
var station: Label
var power_button: Button
var body: VBoxContainer
var knob: Knob
var dialog: FileDialog


class Knob extends Control:
	signal turned(steps: int)
	var position_index := 0
	var _last := 0.0
	var _dragged := 0.0
	var _dragging := false

	func _init() -> void:
		custom_minimum_size = Vector2(64, 64)
		focus_mode = Control.FOCUS_NONE
		mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		tooltip_text = "Drag round or scroll to change song"

	func _draw() -> void:
		var centre := size / 2.0
		var radius := minf(size.x, size.y) / 2.0 - 3.0
		draw_circle(centre, radius, Color("#1b3a45"))
		draw_arc(centre, radius, 0.0, TAU, 48, Color("#8cdce6"), 2.0, true)
		var angle := deg_to_rad(position_index * DEGREES_PER_SONG - 90.0)
		draw_line(centre + Vector2.from_angle(angle) * radius * 0.35,
			centre + Vector2.from_angle(angle) * radius * 0.85, Color("#ffca72"), 4.0, true)

	## Feed a drag angle in degrees; one song for each 30 degrees turned.
	func drag_to(angle: float) -> void:
		_dragged += wrapf(angle - _last, -180.0, 180.0)
		_last = angle
		var steps := int(_dragged / DEGREES_PER_SONG)
		if steps != 0:
			_dragged -= steps * DEGREES_PER_SONG
			turned.emit(steps)

	func start_drag(angle: float) -> void:
		_dragging = true
		_last = angle
		_dragged = 0.0

	func _gui_input(event: InputEvent) -> void:
		if event is InputEventMouseButton:
			if event.button_index == MOUSE_BUTTON_LEFT:
				_dragging = false
				if event.pressed:
					start_drag(rad_to_deg((event.position - size / 2.0).angle()))
			elif event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_UP:
				turned.emit(1)
			elif event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
				turned.emit(-1)
			accept_event()
		elif event is InputEventMouseMotion and _dragging:
			drag_to(rad_to_deg((event.position - size / 2.0).angle()))
			accept_event()


static func title_of(path: String) -> String:
	return path.get_file().get_basename().replace("_", " ")


static func step_track(from: int, delta: int, count: int) -> int:
	return posmod(from + delta, count) if count > 0 else -1


static func scan(directory: String) -> PackedStringArray:
	var found := PackedStringArray()
	var access := DirAccess.open(directory)
	if access == null:
		return found
	for file in access.get_files():
		if file.get_extension().to_lower() in EXTENSIONS:
			found.append(directory.path_join(file))
	found.sort()
	return found


static func load_stream(path: String) -> AudioStream:
	var kind := path.get_extension().to_lower()
	if kind == "ogg":
		return AudioStreamOggVorbis.load_from_file(path)
	if kind == "wav":
		return AudioStreamWAV.load_from_file(path)
	var data := FileAccess.get_file_as_bytes(path)
	if data.is_empty():
		return null
	var stream := AudioStreamMP3.new()
	stream.data = data
	return stream if stream.get_length() > 0.0 else null


func _ready() -> void:
	_make_bus()
	add_child(player)
	player.bus = BUS
	player.finished.connect(func() -> void: change(1))
	_make_panel()
	var saved := ConfigFile.new()
	var chosen := ""
	var last := ""
	if saved.load(settings_path) == OK:
		chosen = saved.get_value("radio", "folder", "")
		last = saved.get_value("radio", "track", "")
		volume = clampf(saved.get_value("radio", "volume", 1.0), 0.0, 3.0)
		body.visible = saved.get_value("radio", "open", true)
	if chosen.is_empty():
		chosen = OS.get_system_dir(OS.SYSTEM_DIR_MUSIC).path_join(DEFAULT_SUBFOLDER)
	(body.get_node("Volume") as HSlider).set_value_no_signal(volume)
	use_folder(chosen, last)
	_apply_level()


## Cabin speaker: band-limited so it sits with the engines.
func _make_bus() -> void:
	if AudioServer.get_bus_index(BUS) >= 0:
		return
	AudioServer.add_bus()
	var bus := AudioServer.bus_count - 1
	AudioServer.set_bus_name(bus, BUS)
	var low := AudioEffectHighPassFilter.new()
	low.cutoff_hz = 140.0
	var high := AudioEffectLowPassFilter.new()
	high.cutoff_hz = 7000.0
	AudioServer.add_bus_effect(bus, low)
	AudioServer.add_bus_effect(bus, high)
	AudioServer.add_bus_effect(bus, AudioEffectHardLimiter.new())


func _button(text: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.focus_mode = Control.FOCUS_NONE
	button.pressed.connect(action)
	return button


func _make_panel() -> void:
	custom_minimum_size = Vector2(300, 0)
	var rows := VBoxContainer.new()
	add_child(rows)
	rows.add_child(_button("Radio", func() -> void:
		body.visible = not body.visible
		reset_size()
		save()))
	body = VBoxContainer.new()
	body.add_theme_constant_override("separation", 8)
	rows.add_child(body)
	station = Label.new()
	station.name = "Station"
	station.custom_minimum_size = Vector2(280, 46)
	station.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	station.add_theme_color_override("font_color", Color("#ffca72"))
	body.add_child(station)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 10)
	body.add_child(row)
	power_button = _button("Off  /", func() -> void: set_power(not powered))
	row.add_child(power_button)
	row.add_child(_button("<  ,", func() -> void: change(-1)))
	knob = Knob.new()
	knob.turned.connect(change)
	row.add_child(knob)
	row.add_child(_button(".  >", func() -> void: change(1)))
	var slider := HSlider.new()
	slider.name = "Volume"
	slider.max_value = 3.0
	slider.step = 0.05
	slider.focus_mode = Control.FOCUS_NONE
	slider.tooltip_text = "Radio volume"
	slider.value_changed.connect(func(value: float) -> void:
		volume = value
		_apply_level()
		save())
	body.add_child(slider)
	body.add_child(_button("Music folder…", choose_folder))


func choose_folder() -> void:
	if dialog == null:
		dialog = FileDialog.new()
		dialog.access = FileDialog.ACCESS_FILESYSTEM
		dialog.file_mode = FileDialog.FILE_MODE_OPEN_DIR
		dialog.use_native_dialog = true
		dialog.title = "Choose your music folder"
		dialog.dir_selected.connect(func(path: String) -> void:
			use_folder(path, "")
			save())
		add_child(dialog)
	dialog.current_dir = folder
	dialog.popup_centered(Vector2i(900, 600))


func use_folder(path: String, last: String) -> void:
	set_power(false)
	folder = path
	tracks = scan(path)
	index = tracks.find(last)
	if index < 0 and not tracks.is_empty():
		index = 0
	player.stream = null
	_show()


func set_power(on: bool) -> void:
	powered = on and not tracks.is_empty()
	power_button.text = "On  /" if powered else "Off  /"
	if not powered:
		player.stream_paused = true
		return
	if player.stream == null:
		_start()
	elif player.stream_paused:
		player.stream_paused = false


func change(delta: int) -> void:
	if tracks.is_empty():
		return
	index = step_track(index, delta, tracks.size())
	player.stop()
	player.stream = null
	_show()
	if powered:
		_start()
	save()


func _start() -> void:
	var stream := load_stream(tracks[index])
	if stream == null:
		station.text = "That file would not play: " + title_of(tracks[index])
		return
	player.stream = stream
	player.stream_paused = false
	player.play()


func _show() -> void:
	if tracks.is_empty():
		station.text = "No music found. Choose a folder."
	else:
		station.text = "%d/%d  %s" % [index + 1, tracks.size(), title_of(tracks[index])]
	knob.position_index = maxi(index, 0)
	knob.queue_redraw()


func set_camera_mode(mode: int) -> void:
	var cockpit := mode == FORWARD_CAMERA
	if cockpit != in_cockpit:
		in_cockpit = cockpit
		_apply_level()


func _apply_level() -> void:
	var level := volume * (1.0 if in_cockpit else OUTSIDE_LEVEL)
	player.volume_db = linear_to_db(maxf(level, 0.0001))


func save() -> void:
	var config := ConfigFile.new()
	config.set_value("radio", "folder", folder)
	config.set_value("radio", "track", tracks[index] if index >= 0 else "")
	config.set_value("radio", "volume", volume)
	config.set_value("radio", "open", body.visible)
	config.save(settings_path)


## Comma and full stop change song, slash switches on and off. None are flight keys.
func _unhandled_key_input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not event.pressed or event.echo or not is_visible_in_tree():
		return
	match event.physical_keycode:
		KEY_COMMA:
			change(-1)
		KEY_PERIOD:
			change(1)
		KEY_SLASH:
			set_power(not powered)
		_:
			return
	get_viewport().set_input_as_handled()
