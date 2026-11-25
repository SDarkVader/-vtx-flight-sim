extends SceneTree
## Run against an imported, isolated native project with --headless --script.

class MockBridge extends RefCounted:
	var patches: Array[Dictionary] = []
	var pending := {}
	var starts := 0
	var allowed := false

	func accepts_controls() -> bool:
		return allowed

	func send_controls(patch: Dictionary) -> void:
		patches.append(patch.duplicate(true))

	func field_in_transit(field: String) -> bool:
		return pending.has(field)

	func start_flight() -> void:
		starts += 1


class TestCockpit extends "res://main.gd":
	func _ready() -> void:
		# Only the native HUD and input code run; do not start scene rendering or a backend.
		bridge.free()
		bridge = MockBridge.new()
		world.free()
		aircraft.free()
		camera.free()
		create_hud()
		set_process(false)
		world_ready = true
		flight_ready = true


var checks: Array[String] = []
var failures: Array[String] = []


func check(passed: bool, name: String) -> void:
	checks.append(name)
	if not passed:
		failures.append(name)
		push_error(name)


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	root.size = Vector2i(1920, 1080)
	var app := TestCockpit.new()
	root.add_child(app)
	var extended := [0.52, 0.52, 0.52, 0.52]
	var command := {"leg_extension_m": extended, "collective": 0.4, "booster_throttle": [0.6, 0.6], "stability_mode": "attitude"}
	var ecu := {"fitted": true, "airbrake": "off"}
	var live := {"run_id": "test-1", "active": true, "paused": false, "mode": "live", "authority": "manual",
		"observation": {"leg_extension_m": [0.31, 0.32, 0.33, 0.34], "wing_state": {"left": "locked", "right": "locked"}},
		"rendering_truth": {"command": command, "phantom": {"transition_ecu": ecu}}}
	app.on_view({"active": false, "mode": "inspection", "run_id": null})
	app.pilot.sample_state(true, 5, {}, {}, {})
	app.handle_action("start_or_pause")
	check(app.bridge.starts == 1 and app.start_pad_id == 5, "Menu starts with the centred controller")
	app.handle_action("start_or_pause")
	check(app.bridge.starts == 1, "Repeated start is ignored while starting")
	app.bridge.allowed = true
	app.on_view(live)
	check(app.pilot.pad_armed == root.has_focus(), "The starting pad only arms if the native window has focus")
	app.pilot.sample_state(true, 5, {}, {}, {})
	app.handle_action("arm_pad")
	app.update_hud()
	check(app.pilot.pad_armed and "Armed" in app.pad_status.text, "In-flight arm is reflected on the HUD")
	check("DOWN" in app.configuration.text and "FL 0.31   FR 0.32   RL 0.33   RR 0.34 m" in app.configuration.text,
			"HUD distinguishes the leg request and four measured extensions")
	app.handle_action("legs")
	check(app.bridge.patches.back() == {"leg_extension_m": [0.0, 0.0, 0.0, 0.0]}, "Leg action uses a four-slider request")
	app.bridge.pending["leg_extension_m"] = true
	var count: int = app.bridge.patches.size()
	app.handle_action("legs")
	check(app.bridge.patches.size() == count, "Pending gear change blocks duplicate toggles")
	app.bridge.pending.clear()

	app.pilot.sample_state(true, 5, {JOY_AXIS_LEFT_X: 0.7, JOY_AXIS_LEFT_Y: 0.6, JOY_AXIS_RIGHT_X: -0.5}, {}, {})
	app.update_controls(0.05)
	check(app.bridge.patches.back().roll > 0 and app.bridge.patches.back().pitch > 0 and app.bridge.patches.back().yaw < 0, "Cockpit sends joint stick inputs")
	app.on_pad_connection(5, false)
	app.update_controls(0.05)
	app.update_hud()
	check(app.bridge.patches.back() == {"roll": 0.0, "pitch": 0.0, "yaw": 0.0} and not app.pilot.pad_armed and "disconnected" in app.pad_status.text,
			"Disconnect neutralizes sticks while retaining both power targets")
	app.pilot.sample_state(true, 5, {JOY_AXIS_LEFT_X: 0.7}, {}, {})
	app.handle_action("arm_pad")
	check(not app.pilot.pad_armed, "A deflected reconnect cannot arm the pad")
	app.pilot.sample_state(true, 5, {}, {}, {})
	app.handle_action("arm_pad")
	app.pilot.sample_state(true, 5, {JOY_AXIS_LEFT_Y: -0.5, JOY_AXIS_TRIGGER_RIGHT: 0.8}, {JOY_BUTTON_RIGHT_SHOULDER: true}, {})
	app.update_controls(0.05)
	app.handle_action("airbrake")
	check(app.rebase_after_airbrake and app.bridge.patches.back() == {"airbrake": "on"}, "Airbrake engagement requests the ECU")
	app.bridge.pending["airbrake"] = true
	app.on_view(live)
	count = app.bridge.patches.size()
	app.update_controls(0.05)
	check(app.rebase_after_airbrake and app.bridge.patches.size() == count, "Held power inputs cannot resend pre-airbrake power while waiting")
	app.bridge.pending.clear()
	command.booster_throttle = [0.0, 0.0]
	command.collective = 0.2
	ecu.airbrake = "on"
	app.on_view(live)
	check(not app.rebase_after_airbrake and is_equal_approx(app.pilot.collective, 0.2) and is_zero_approx(app.pilot.booster), "Pilot demand rebases to the ECU while triggers and bumpers are held")
	app.update_controls(0.05)
	var resumed: Dictionary = app.bridge.patches.back()
	check(float(resumed.collective) < 0.24 and float(resumed.booster_throttle[0]) <= 0.021, "Subsequent held power adjustment starts from ECU demand")
	app.handle_action("camera")
	app.update_hud()
	check(app.camera_mode == 1 and "Camera  Forward" in app.configuration.text, "Camera change is visible in the HUD")
	app.handle_action("help")
	await process_frame
	await process_frame
	var panel: Rect2 = app.help_panel.get_global_rect()
	var viewport := root.get_visible_rect()
	var fits := app.help_panel.visible and viewport.encloses(panel)
	for label: Label in app.help_panel.find_children("*", "Label", true, false):
		fits = fits and panel.encloses(label.get_global_rect()) and label.size.x >= label.get_minimum_size().x
	check(fits and panel.end.y < app.instruments.get_global_rect().position.y, "Help text fits within the 1920×1080 viewport above instruments")
	app.handle_action("help")
	check(not app.help_panel.visible, "Help closes without interrupting controls")
	app.on_focus_lost()
	check(not app.pilot.pad_armed and app.bridge.patches.back().get("pitch") == 0.0, "Focus loss neutralizes pitch and disarms the pad")
	print(JSON.stringify({"passed": failures.is_empty(), "window_focused": root.has_focus(), "checks": checks,
		"failures": failures, "help_panel": str(panel), "viewport": str(viewport)}))
	quit(0 if failures.is_empty() else 1)
