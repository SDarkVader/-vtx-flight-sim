extends Node3D

const BackendBridge = preload("res://runtime/bridge.gd")
const WorldView = preload("res://world/meridian_world.gd")
const AircraftView = preload("res://flight/phantom_view.gd")
const FlightInput = preload("res://flight/flight_input.gd")
const FlightActions = preload("res://flight/flight_actions.gd")
const MeridianBenchmark = preload("res://benchmark/meridian_benchmark.gd")
const CAMERA_NAMES := ["Chase", "Forward", "Meridian", "Close orbit"]
const ORBIT_CAMERA := 3
const ORBIT_START_DISTANCE := 20.0
const ORBIT_MIN_DISTANCE := 12.0
const ORBIT_MAX_DISTANCE := 60.0
const ORBIT_PITCH_LIMIT := PI * 75.0 / 180.0
const FLIGHT_HINTS := "A / L   Landing legs      LT / RT   Collective      LB / RB   Boosters      View / C   Camera      O   Close orbit      Y / F1   All controls"

const INK := Color("#e8f0ee")
const SUBDUED := Color("#a5bab8")
const ACCENT := Color("#94ebd1")
const WARNING := Color("#ffbf80")
const WORLD_HASH := "3333e153ac809f473db60750c57f181207e0378e99e078a872a9a3d854317bed"
const AIRCRAFT_CONFIG := "58d12857e3d38b50deeefa982974f4e54bd37f72823218a3e5c31b9000144ba3"

var bridge = BackendBridge.new()
var world = WorldView.new()
var aircraft = AircraftView.new()
var pilot := FlightInput.new()
var camera := Camera3D.new()
var latest: Dictionary = {}
var world_data: Dictionary = {}
var world_ready := false
var flight_ready := false
var starting := false
var closing := false
var camera_mode := 0
var chase_initialised := false
var chase_run_id: Variant = null
var chase_anchor := Vector3.ZERO
var chase_heading := 0.0
var orbit_initialised := false
var orbit_azimuth := 0.0
var orbit_elevation := 0.0
var orbit_distance := ORBIT_START_DISTANCE
var snapshot_usec := 0
var start_pad_id := -1
var rebase_after_airbrake := false
var launched_usec := 0
var verify_only := false
var control_smoke := false
var benchmark_requested := false
var benchmark_input_path := ""
var benchmark_receipt_path := ""
var receipt_path := ""
var screenshot_path := ""
var receipt_armed := false
var smoke_command_sent := false
var smoke_start_s := -1.0
var ready_frame_count := 0

var status: Label
var instruments: Label
var start_button: Button
var pause_button: Button
var pad_status: Label
var configuration: Label
var help_panel: PanelContainer
var flight_hints: Label


func _ready() -> void:
	launched_usec = Time.get_ticks_usec()
	get_tree().auto_accept_quit = false
	Engine.max_fps = 60
	for arg in OS.get_cmdline_user_args():
		if arg == "--readiness-only":
			verify_only = true
		elif arg == "--control-smoke":
			verify_only = true
			control_smoke = true
		elif arg.begins_with("--receipt="):
			receipt_path = arg.trim_prefix("--receipt=")
		elif arg.begins_with("--screenshot="):
			screenshot_path = arg.trim_prefix("--screenshot=")
		elif arg == "--meridian-benchmark":
			benchmark_requested = true
		elif arg.begins_with("--meridian-benchmark="):
			benchmark_requested = true
			benchmark_input_path = arg.trim_prefix("--meridian-benchmark=")
		elif arg.begins_with("--graphics-receipt="):
			benchmark_receipt_path = arg.trim_prefix("--graphics-receipt=")
	add_child(world)
	add_child(aircraft)
	camera.fov = 48.0
	camera.far = 32000.0
	camera.near = 0.15
	add_child(camera)
	camera.current = true
	camera.position = Vector3(-3830.0, 24.0, 66.0)
	camera.look_at(Vector3(-3885.0, 3.0, 0.0), Vector3.UP)
	create_hud()
	if benchmark_requested:
		start_meridian_benchmark()
		return
	Input.joy_connection_changed.connect(on_pad_connection)
	get_window().focus_exited.connect(on_focus_lost)
	add_child(bridge)
	bridge.ready_to_fly.connect(on_world)
	bridge.view_received.connect(on_view)
	bridge.fault.connect(on_fault)
	bridge.start()
	if verify_only:
		get_tree().create_timer(100.0).timeout.connect(on_readiness_timeout)


func start_meridian_benchmark() -> void:
	bridge.free()
	if benchmark_input_path.is_empty():
		benchmark_input_path = OS.get_executable_path().get_base_dir().path_join("benchmark-data")
	if benchmark_receipt_path.is_empty():
		var output_folder := OS.get_environment("LOCALAPPDATA").path_join("VTX Meridian Graphics")
		if not output_folder.is_absolute_path():
			output_folder = ProjectSettings.globalize_path("user://graphics")
		DirAccess.make_dir_recursive_absolute(output_folder)
		var stamp := Time.get_datetime_string_from_system().replace(":", "-")
		benchmark_receipt_path = output_folder.path_join("meridian-%s-%d.json" % [stamp, OS.get_process_id()])
	var benchmark := MeridianBenchmark.new()
	add_child(benchmark)
	benchmark.start.call_deferred(self, benchmark_input_path, benchmark_receipt_path)


func create_hud() -> void:
	var hud := CanvasLayer.new()
	add_child(hud)

	var header := PanelContainer.new()
	hud.add_child(header)
	header.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	header.offset_left = 22
	header.offset_right = -22
	header.offset_top = 20
	header.add_theme_stylebox_override("panel", tray_style())
	var header_row := HBoxContainer.new()
	header_row.add_theme_constant_override("separation", 20)
	header.add_child(header_row)
	header_row.add_child(make_label("VTX  /  VADERLAND 33.1", 25, ACCENT))
	header_row.add_child(make_label("PHANTOM A10-D", 17, INK))
	status = make_label("Starting the local physics runtime", 17, SUBDUED)
	status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header_row.add_child(status)
	start_button = Button.new()
	start_button.focus_mode = Control.FOCUS_NONE
	start_button.text = "Start flight"
	start_button.disabled = true
	start_button.pressed.connect(start_flight)
	header_row.add_child(start_button)
	pause_button = Button.new()
	pause_button.focus_mode = Control.FOCUS_NONE
	pause_button.text = "Pause"
	pause_button.disabled = true
	pause_button.pressed.connect(toggle_pause)
	header_row.add_child(pause_button)
	var help_button := Button.new()
	help_button.focus_mode = Control.FOCUS_NONE
	help_button.text = "Controls   Y / F1"
	help_button.pressed.connect(toggle_help)
	header_row.add_child(help_button)

	var footer := PanelContainer.new()
	hud.add_child(footer)
	footer.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	footer.offset_left = 22
	footer.offset_right = -22
	footer.offset_top = -150
	footer.offset_bottom = -21
	footer.add_theme_stylebox_override("panel", tray_style())
	var controls := VBoxContainer.new()
	controls.add_theme_constant_override("separation", 6)
	footer.add_child(controls)
	instruments = make_label("ALT  —     AIRSPEED  —     V/S  —", 22, INK)
	controls.add_child(instruments)
	configuration = make_label("Landing legs   —", 19, INK)
	controls.add_child(configuration)
	pad_status = make_label("Checking for an Xbox controller", 17, ACCENT)
	controls.add_child(pad_status)
	flight_hints = make_label(FLIGHT_HINTS, 16, SUBDUED)
	controls.add_child(flight_hints)
	make_controls_panel(hud)
	if benchmark_requested or verify_only:
		start_button.hide()
		pause_button.hide()
		help_button.hide()
		if benchmark_requested:
			status.text = "Loading the Meridian graphics replay"
			instruments.text = "Fixed chase camera"
			configuration.text = "Warm-up and measured repeat"
			pad_status.hide()
			flight_hints.hide()
		else:
			flight_hints.text = "Readiness check in progress"


func make_controls_panel(hud: CanvasLayer) -> void:
	help_panel = PanelContainer.new()
	hud.add_child(help_panel)
	help_panel.position = Vector2(22, 96)
	help_panel.add_theme_stylebox_override("panel", tray_style())
	var rows := VBoxContainer.new()
	rows.add_theme_constant_override("separation", 8)
	help_panel.add_child(rows)
	rows.add_child(make_label("Flight controls", 24, ACCENT))
	var grid := GridContainer.new()
	grid.columns = 3
	grid.add_theme_constant_override("h_separation", 28)
	grid.add_theme_constant_override("v_separation", 3)
	rows.add_child(grid)
	for row in [
		["Action", "Xbox One", "Keyboard"],
		["Start flight", "Menu (arms a centred pad)", "Enter"],
		["Arm pad during flight", "Left stick click", "F2"],
		["Pitch up / down", "Left stick back / forward", "W / S"],
		["Roll left / right", "Left stick left / right", "A / D"],
		["Yaw left / right", "Right stick left / right", "Q / E"],
		["Collective ↑ / ↓", "RT / LT", "R / F"],
		["Paired boosters ↑ / ↓", "RB / LB", "T / Y"],
		["Retract / extend landing legs", "A", "L"],
		["Deploy / stow wings and canards", "X / D-pad left", "G / H"],
		["Pods vertical / forward", "D-pad up / down", "1 / 2"],
		["Wheel brakes on / off", "D-pad right", "K"],
		["ECU airbrake on / off", "Hold B for ½ second", "B"],
		["Return to direct collective", "Right stick click", "M"],
		["Cycle camera", "View", "C"],
		["Close orbit", "—", "O, then right-drag / wheel"],
		["Pause / resume", "Menu", "P"],
		["Show / hide controls", "Y", "F1"],
		["Close application", "—", "Esc"],
	]:
		for cell in row:
			grid.add_child(make_label(cell, 17, ACCENT if row[0] == "Action" else INK))
	rows.add_child(make_label("Release thrust controls to keep their setting. Centre the pad before arming.", 15, SUBDUED))
	help_panel.hide()


func toggle_help() -> void:
	help_panel.visible = not help_panel.visible


func tray_style() -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = Color(0.025, 0.058, 0.075, 0.90)
	box.border_color = Color(0.30, 0.47, 0.50, 0.55)
	box.set_border_width_all(1)
	box.set_corner_radius_all(8)
	box.content_margin_left = 18
	box.content_margin_right = 18
	box.content_margin_top = 11
	box.content_margin_bottom = 11
	return box


func make_label(text: String, font_size: int, tint: Color) -> Label:
	var item := Label.new()
	item.text = text
	item.add_theme_font_size_override("font_size", font_size)
	item.add_theme_color_override("font_color", tint)
	return item


func on_world(payload: Dictionary) -> void:
	world_data = payload
	if str(payload.get("version")) != "33.1" or payload.get("displayed_world_sha256") != WORLD_HASH:
		on_fault("Vaderland world identity differs from the reviewed 33.1 world")
		return
	status.text = "Building Meridian from surveyed terrain and scenery"
	build_world.call_deferred()


func build_world() -> void:
	world_ready = world.build(world_data)
	if not world_ready:
		on_fault("The native terrain and city could not be built")
		return
	status.text = "Waiting for the first Phantom pose"


func on_view(view: Dictionary) -> void:
	var changed_run: bool = latest.get("run_id") != view.get("run_id")
	var changed_authority: bool = latest.get("authority") != view.get("authority")
	if snapshot_usec and Time.get_ticks_usec() - snapshot_usec > BackendBridge.CONTROL_FRESHNESS_MSEC * 1000:
		start_pad_id = -1
		pilot.disarm_pad()
		pilot.resample_owned_axes()
	latest = view
	snapshot_usec = Time.get_ticks_usec()
	var is_active: bool = latest.get("active", false)
	var command: Dictionary = latest.get("rendering_truth", {}).get("command", {})
	if changed_run or changed_authority:
		pilot.reset_demands()
		rebase_after_airbrake = false
		if not (starting and start_pad_id == pilot.pad_id and start_pad_id >= 0 \
				and get_window().has_focus() and FlightActions.manual_flight(view) and pilot.arm_pad()):
			pilot.disarm_pad()
		start_pad_id = -1
	if FlightActions.manual_flight(view):
		sync_power(command, changed_run or changed_authority)
	elif pilot.pad_armed and (is_active or not starting):
		pilot.disarm_pad()
	if view.get("paused", false):
		pilot.resample_owned_axes()
	if is_active:
		starting = false
	if flight_ready and not verify_only:
		start_button.disabled = is_active or starting
		pause_button.disabled = not is_active
		pause_button.text = "Resume" if latest.get("paused", false) else "Pause"


func sync_power(command: Dictionary, changed_run: bool) -> void:
	var pair: Array = command.get("booster_throttle", [])
	if pair.size() != 2 or not command.has("collective"):
		return
	if changed_run or (rebase_after_airbrake and not bridge.field_in_transit("airbrake")):
		pilot.set_power_targets(float(command.collective), (float(pair[0]) + float(pair[1])) * 0.5)
		rebase_after_airbrake = false
	elif not rebase_after_airbrake:
		var settled := {}
		for field in ["collective", "booster_throttle"]:
			if not bridge.field_in_transit(field):
				settled[field] = command[field]
		pilot.sync_demands(settled)


func _process(delta: float) -> void:
	if benchmark_requested:
		return
	if not verify_only:
		pilot.poll(get_window().has_focus())
	if latest.is_empty() or closing:
		return
	aircraft.update_from_view(latest, delta)
	if world_ready:
		world.set_simulation_time(float(latest.get("scenery_time_s", 0.0)))
	update_camera(delta)
	update_hud()
	if world_ready and aircraft.pose_ready and aircraft.articulation_ready and not flight_ready:
		var truth: Dictionary = latest.get("rendering_truth", {})
		if truth.get("variant") != "phantom-a10d" or truth.get("config_sha256") != AIRCRAFT_CONFIG:
			on_fault("The first native pose differs from the approved Phantom A10-D")
			return
		flight_ready = true
		start_button.disabled = verify_only
	if flight_ready and verify_only and not receipt_armed:
		ready_frame_count += 1
		if ready_frame_count == 8 and not control_smoke:
			camera_mode = 2
		if ready_frame_count >= 22:
			readiness_test()
	if flight_ready and not verify_only:
		if bridge.accepts_controls():
			update_controls(delta)
		elif latest.get("active", false) and latest.get("authority") == "manual":
			if pilot.pad_armed:
				pilot.disarm_pad()
			pilot.resample_owned_axes()


func update_camera(delta: float) -> void:
	if not aircraft.pose_ready:
		chase_initialised = false
		return
	var target: Vector3 = aircraft.global_position
	if camera_mode == ORBIT_CAMERA and orbit_initialised:
		update_orbit_camera(target)
		return
	var forward: Vector3 = aircraft.global_basis.x.slide(Vector3.UP).normalized()
	if forward.length_squared() < 0.1:
		forward = Vector3.RIGHT
	if camera_mode == ORBIT_CAMERA:
		orbit_azimuth = atan2(forward.z, forward.x) + deg_to_rad(155.0)
		orbit_elevation = deg_to_rad(16.0)
		orbit_distance = ORBIT_START_DISTANCE
		orbit_initialised = true
		update_orbit_camera(target)
		return
	if camera_mode == 1:
		chase_initialised = false
		camera.position = target + forward * 2.4 + Vector3.UP * 2.1
		camera.look_at(camera.position + forward * 60.0, Vector3.UP)
		return
	if camera_mode == 2:
		chase_initialised = false
		camera.position = Vector3(1489.0, 410.0, -3166.0)
		camera.look_at(Vector3(-120.0, 155.0, -2850.0), Vector3.UP)
		return

	var run_id: Variant = latest.get("run_id")
	var heading := atan2(forward.z, forward.x)
	if chase_initialised and run_id == chase_run_id:
		var blend := 1.0 - exp(-7.0 * delta)
		chase_anchor = chase_anchor.lerp(target, blend)
		chase_heading = lerp_angle(chase_heading, heading, blend)
	else:
		chase_anchor = target
		chase_heading = heading
		chase_run_id = run_id
		chase_initialised = true

	# Anchor the eye and aim together so vertical motion cannot pitch the horizon.
	var chase_forward := Vector3(cos(chase_heading), 0.0, sin(chase_heading))
	var chase_right := chase_forward.cross(Vector3.UP)
	camera.position = chase_anchor - chase_forward * 45.0 + chase_right * 10.0 + Vector3.UP * 17.0
	camera.look_at(chase_anchor + chase_forward * 13.0 + Vector3.UP * 1.1, Vector3.UP)


func update_orbit_camera(target: Vector3) -> void:
	var focus := target + Vector3.UP * 0.6
	var horizontal_distance := cos(orbit_elevation) * orbit_distance
	var eye := focus + Vector3(
		cos(orbit_azimuth) * horizontal_distance,
		sin(orbit_elevation) * orbit_distance,
		sin(orbit_azimuth) * horizontal_distance,
	)
	if world_ready:
		eye.y = maxf(eye.y, world.terrain_height_at(eye) + 0.55)
	camera.position = eye
	camera.look_at(focus, Vector3.UP)


func set_camera_mode(mode: int) -> void:
	if camera_mode == mode:
		return
	camera_mode = mode
	chase_initialised = false
	orbit_initialised = false
	if is_instance_valid(flight_hints):
		flight_hints.text = FLIGHT_HINTS
		if camera_mode == ORBIT_CAMERA:
			flight_hints.text += "      Right-drag   Orbit      Wheel   Zoom"


func update_hud() -> void:
	if not world_ready:
		return
	var obs: Dictionary = latest.get("observation", {})
	var velocity: Array = obs.get("velocity_world_m_s", [0.0, 0.0, 0.0])
	var alt: float = obs.get("baro_m", 0.0)
	var speed: float = obs.get("airspeed_m_s", 0.0)
	var vertical: float = float(velocity[2]) if velocity.size() > 2 else 0.0
	var truth: Dictionary = latest.get("rendering_truth", {})
	var command: Dictionary = truth.get("command", {})
	var pair: Array = command.get("booster_throttle", [0.0, 0.0])
	instruments.text = "ALT  %.1f m     AIRSPEED  %.1f m/s     V/S  %+.1f m/s     COLLECTIVE  %.0f%%     BOOSTERS  %.0f%%" % [
		alt, speed, vertical, float(command.get("collective", 0.0)) * 100.0, (float(pair[0]) + float(pair[1])) * 50.0
	]
	var leg_demand: Array = command.get("leg_extension_m", [])
	var leg_actual: Array = obs.get("leg_extension_m", [])
	var gear_text := "Landing legs   —"
	if leg_demand.size() == 4 and leg_actual.size() == 4:
		var target := "DOWN" if float(leg_demand.min()) >= 0.519 else ("UP" if float(leg_demand.max()) <= 0.001 else "PARTIAL")
		gear_text = "Legs requested %s     FL %.2f   FR %.2f   RL %.2f   RR %.2f m" % [
			target, leg_actual[0], leg_actual[1], leg_actual[2], leg_actual[3]]
	var wings: Dictionary = obs.get("wing_state", {})
	var ecu: Dictionary = truth.get("phantom", {}).get("transition_ecu", {})
	configuration.text = "%s      Wings  %s / %s      Airbrake  %s      Mode  %s      Camera  %s" % [
		gear_text, wings.get("left", "—"), wings.get("right", "—"), ecu.get("airbrake", "—"),
		command.get("stability_mode", "—"), CAMERA_NAMES[camera_mode]]
	if pilot.pad_id < 0:
		pad_status.text = "Keyboard ready   ·   Xbox pad disconnected"
	elif pilot.pad_armed:
		pad_status.text = "%s   ·   Armed" % pilot.pad_name
	elif latest.get("active", false):
		pad_status.text = "%s   ·   Centre sticks, release controls, then click left stick to arm" % pilot.pad_name
	else:
		pad_status.text = "%s   ·   Centre sticks and press Menu to start" % pilot.pad_name
	if not flight_ready:
		return
	var age_ms := (Time.get_ticks_usec() - snapshot_usec) / 1000.0
	if age_ms > 2000.0:
		status.text = "Snapshot delayed  ·  %.0f ms" % age_ms
		status.modulate = WARNING
	elif latest.get("active", false):
		status.text = "PAUSED" if latest.get("paused", false) else "LIVE  ·  %.2f s" % float(obs.get("t_s", 0.0))
		status.modulate = INK
	else:
		status.text = "Ready  ·  Menu / Enter to start"
		status.modulate = ACCENT


func start_flight(from_pad := false) -> void:
	if not flight_ready or starting or latest.get("active", false):
		return
	starting = true
	start_pad_id = pilot.pad_id if from_pad and pilot.arm_pad() else -1
	start_button.disabled = true
	bridge.start_flight()


func toggle_pause() -> void:
	if flight_ready and latest.get("active", false):
		bridge.pause(not latest.get("paused", false))


func update_controls(delta: float) -> void:
	var patch := pilot.get_axis_patch(delta)
	if rebase_after_airbrake:
		patch.erase("collective")
		patch.erase("booster_throttle")
	if not patch.is_empty():
		bridge.send_controls(patch)
	if pilot.drain_hold_action(delta) == "airbrake":
		handle_action("airbrake")


func _input(event: InputEvent) -> void:
	if closing or benchmark_requested or verify_only or not get_window().has_focus():
		return
	if (event is InputEventJoypadButton and event.pressed) \
			or (event is InputEventKey and event.physical_keycode == KEY_F2 and event.pressed):
		pilot.poll(true)
	var action := pilot.action_for_event(event)
	if not action.is_empty():
		get_viewport().set_input_as_handled()
		handle_action(action)


func _unhandled_input(event: InputEvent) -> void:
	if closing or benchmark_requested or verify_only or camera_mode != ORBIT_CAMERA or not orbit_initialised:
		return
	if event is InputEventMouseMotion and event.button_mask & MOUSE_BUTTON_MASK_RIGHT:
		orbit_azimuth = wrapf(orbit_azimuth - event.screen_relative.x * 0.006, -PI, PI)
		orbit_elevation = clampf(orbit_elevation + event.screen_relative.y * 0.006, -ORBIT_PITCH_LIMIT, ORBIT_PITCH_LIMIT)
		get_viewport().set_input_as_handled()
	elif event is InputEventMouseButton and event.pressed:
		var wheel_scale := pow(0.82, event.factor if event.factor > 0.0 else 1.0)
		match event.button_index:
			MOUSE_BUTTON_WHEEL_UP:
				orbit_distance = maxf(ORBIT_MIN_DISTANCE, orbit_distance * wheel_scale)
				get_viewport().set_input_as_handled()
			MOUSE_BUTTON_WHEEL_DOWN:
				orbit_distance = minf(ORBIT_MAX_DISTANCE, orbit_distance / wheel_scale)
				get_viewport().set_input_as_handled()


func handle_action(action: String) -> void:
	match action:
		"start_or_pause":
			if latest.get("active", false):
				toggle_pause()
			else:
				start_flight(true)
		"start":
			start_flight()
		"pause":
			toggle_pause()
		"arm_pad":
			if flight_ready and bridge.accepts_controls():
				pilot.arm_pad()
		"camera":
			set_camera_mode((camera_mode + 1) % CAMERA_NAMES.size())
		"orbit_camera":
			set_camera_mode(ORBIT_CAMERA)
		"help":
			toggle_help()
		"close":
			request_close()
		_:
			if not flight_ready or not bridge.accepts_controls():
				return
			var patch := FlightActions.configuration_patch(action, latest)
			if patch.is_empty():
				return
			# Read the authoritative toggle state again after the previous press is applied.
			for field in ["leg_extension_m", "brake", "airbrake"]:
				if patch.has(field) and bridge.field_in_transit(field):
					return
			bridge.send_controls(patch)
			if patch.get("airbrake") == "on":
				rebase_after_airbrake = true


func on_pad_connection(device: int, connected: bool) -> void:
	pilot.notify_disconnect(device, connected)
	if not connected and device == start_pad_id:
		start_pad_id = -1


func on_focus_lost() -> void:
	start_pad_id = -1
	pilot.poll(false)
	if not verify_only and flight_ready and bridge.accepts_controls():
		update_controls(0.0)


func readiness_test() -> void:
	if control_smoke:
		if not latest.get("active", false):
			start_flight()
			return
		var obs: Dictionary = latest.get("observation", {})
		var t_s: float = obs.get("t_s", 0.0)
		if not smoke_command_sent:
			smoke_start_s = t_s
			smoke_command_sent = true
			bridge.send_controls({"collective": 0.12})
			return
		var truth: Dictionary = latest.get("rendering_truth", {})
		var command: Dictionary = truth.get("command", {})
		if t_s < smoke_start_s + 0.15 or absf(float(command.get("collective", 0.0)) - 0.12) > 0.001:
			return
	write_receipt(true, "")


func write_receipt(passed: bool, detail: String) -> void:
	if receipt_armed:
		return
	receipt_armed = true
	var obs: Dictionary = latest.get("observation", {})
	var driver := RenderingServer.get_video_adapter_name()
	var viewport_size := get_viewport().get_visible_rect().size
	var output := {
		"passed": passed,
		"detail": detail,
		"startup_s": (Time.get_ticks_usec() - launched_usec) / 1000000.0,
		"mode": "headless_control_smoke" if control_smoke else "native_readiness",
		"driver": driver,
		"display": DisplayServer.get_name(),
		"viewport": [int(viewport_size.x), int(viewport_size.y)],
		"graphics": {"preset": "Prototype High", "scale": 1.0, "frame_cap": Engine.max_fps},
		"world_sha256": world_data.get("displayed_world_sha256"),
		"world_version": world_data.get("version"),
		"world_stats": world.stats,
		"aircraft_config": latest.get("rendering_truth", {}).get("config_sha256"),
		"aircraft_asset_sha256": aircraft.asset_sha256,
		"physics_identity": bridge.runtime_identity,
		"session_path": bridge.session_path,
		"control_smoke_passed": control_smoke and passed,
		"physics_time_s": obs.get("t_s"),
	}
	if not receipt_path.is_empty():
		var file := FileAccess.open(receipt_path, FileAccess.WRITE)
		if file:
			file.store_string(JSON.stringify(output, "\t") + "\n")
			file.close()
		else:
			push_error("Could not write readiness receipt")
			passed = false
	print(JSON.stringify(output))
	if passed and not screenshot_path.is_empty() and DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		var image := get_viewport().get_texture().get_image()
		if image.save_png(screenshot_path) != OK:
			push_warning("Could not save the native readiness screenshot.")
	request_close(0 if passed else 1)


func on_readiness_timeout() -> void:
	if not receipt_armed:
		write_receipt(false, "Readiness timed out before world, pose or controls were verified")


func on_fault(message: String) -> void:
	status.text = message
	status.modulate = WARNING
	if verify_only:
		write_receipt(false, message)


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		request_close()


func request_close(exit_code: int = 0) -> void:
	if closing:
		return
	closing = true
	if not benchmark_requested:
		bridge.quit()
	await get_tree().process_frame
	get_tree().quit(exit_code)
