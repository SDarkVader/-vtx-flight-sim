extends Node3D

const BackendBridge = preload("res://runtime/bridge.gd")
const WorldView = preload("res://world/meridian_world.gd")
const AircraftView = preload("res://flight/phantom_view.gd")

const INK := Color("#e8f0ee")
const SUBDUED := Color("#a5bab8")
const ACCENT := Color("#94ebd1")
const WARNING := Color("#ffbf80")
const WORLD_HASH := "3333e153ac809f473db60750c57f181207e0378e99e078a872a9a3d854317bed"
const AIRCRAFT_CONFIG := "58d12857e3d38b50deeefa982974f4e54bd37f72823218a3e5c31b9000144ba3"

var bridge = BackendBridge.new()
var world = WorldView.new()
var aircraft = AircraftView.new()
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
var snapshot_usec := 0
var control_elapsed := 0.0
var collective := 0.0
var booster := 0.0
var last_control: Dictionary = {}
var launched_usec := 0
var verify_only := false
var control_smoke := false
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
	add_child(bridge)
	bridge.ready_to_fly.connect(on_world)
	bridge.view_received.connect(on_view)
	bridge.fault.connect(on_fault)
	bridge.start()
	if verify_only:
		get_tree().create_timer(100.0).timeout.connect(on_readiness_timeout)


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
	start_button.text = "Start flight"
	start_button.disabled = true
	start_button.pressed.connect(start_flight)
	header_row.add_child(start_button)
	pause_button = Button.new()
	pause_button.text = "Pause"
	pause_button.disabled = true
	pause_button.pressed.connect(toggle_pause)
	header_row.add_child(pause_button)

	var footer := PanelContainer.new()
	hud.add_child(footer)
	footer.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	footer.offset_left = 22
	footer.offset_right = -22
	footer.offset_top = -124
	footer.offset_bottom = -21
	footer.add_theme_stylebox_override("panel", tray_style())
	var controls := VBoxContainer.new()
	controls.add_theme_constant_override("separation", 6)
	footer.add_child(controls)
	instruments = make_label("ALT  —     AIRSPEED  —     V/S  —", 22, INK)
	controls.add_child(instruments)
	var hints := make_label("Enter  Start flight     R/F  Collective     W/S  Pitch     A/D  Roll     Q/E  Yaw     G  Deploy wings     1/2  Pod angle     T/Y  Boosters     C  Camera", 16, SUBDUED)
	controls.add_child(hints)
	if verify_only:
		hints.text = "Readiness check in progress"
		start_button.hide()
		pause_button.hide()


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
	latest = view
	snapshot_usec = Time.get_ticks_usec()
	var is_active: bool = latest.get("active", false)
	if is_active:
		starting = false
	if flight_ready and not verify_only:
		start_button.disabled = is_active or starting
		pause_button.disabled = not is_active
		pause_button.text = "Resume" if latest.get("paused", false) else "Pause"


func _process(delta: float) -> void:
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
	if flight_ready and not verify_only and latest.get("active", false) and not latest.get("paused", false):
		update_controls(delta)


func update_camera(delta: float) -> void:
	if not aircraft.pose_ready:
		chase_initialised = false
		return
	var target: Vector3 = aircraft.global_position
	var forward: Vector3 = aircraft.global_basis.x.slide(Vector3.UP).normalized()
	if forward.length_squared() < 0.1:
		forward = Vector3.RIGHT
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


func update_hud() -> void:
	if not world_ready:
		return
	var obs: Dictionary = latest.get("observation", {})
	var velocity: Array = obs.get("velocity_world_m_s", [0.0, 0.0, 0.0])
	var alt: float = obs.get("baro_m", 0.0)
	var speed: float = obs.get("airspeed_m_s", 0.0)
	var vertical: float = float(velocity[2]) if velocity.size() > 2 else 0.0
	instruments.text = "ALT  %.1f m     AIRSPEED  %.1f m/s     V/S  %+.1f m/s     COLLECTIVE  %.0f%%     BOOSTERS  %.0f%%" % [
		alt, speed, vertical, collective * 100.0, booster * 100.0
	]
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
		status.text = "Ready  ·  Enter to start"
		status.modulate = ACCENT


func start_flight() -> void:
	if not flight_ready or starting or latest.get("active", false):
		return
	starting = true
	collective = 0.0
	booster = 0.0
	last_control.clear()
	start_button.disabled = true
	bridge.start_flight()


func toggle_pause() -> void:
	if flight_ready and latest.get("active", false):
		bridge.pause(not latest.get("paused", false))


func axis(positive: Key, negative: Key) -> float:
	if not get_window().has_focus():
		return 0.0
	return float(Input.is_key_pressed(positive)) - float(Input.is_key_pressed(negative))


func update_controls(delta: float) -> void:
	collective = clampf(collective + axis(KEY_R, KEY_F) * 0.42 * delta, 0.0, 1.0)
	booster = clampf(booster + axis(KEY_T, KEY_Y) * 0.4 * delta, 0.0, 1.0)
	control_elapsed += delta
	if control_elapsed < 0.08:
		return
	control_elapsed = 0.0
	var patch := {
		"pitch": axis(KEY_W, KEY_S) * 0.34,
		"roll": axis(KEY_D, KEY_A) * 0.46,
		"yaw": axis(KEY_E, KEY_Q) * 0.40,
		"collective": snappedf(collective, 0.01),
		"booster_throttle": [snappedf(booster, 0.01), snappedf(booster, 0.01)],
	}
	if patch != last_control:
		bridge.send_controls(patch)
		last_control = patch


func _unhandled_key_input(event: InputEvent) -> void:
	if closing or verify_only or not (event is InputEventKey) or not event.pressed or event.echo:
		return
	match event.physical_keycode:
		KEY_ENTER:
			start_flight()
		KEY_P:
			toggle_pause()
		KEY_C:
			camera_mode = (camera_mode + 1) % 3
			chase_initialised = false
		KEY_G:
			if latest.get("active", false):
				bridge.send_controls({"wing": "deploy", "canard_fold": "deployed"})
		KEY_1, KEY_2:
			if latest.get("active", false):
				var degrees := 90.0 if event.physical_keycode == KEY_1 else 0.0
				bridge.send_controls({"pod_tilt_deg": [degrees, degrees, degrees, degrees]})
		KEY_ESCAPE:
			request_close()


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
	bridge.quit()
	await get_tree().process_frame
	get_tree().quit(exit_code)
