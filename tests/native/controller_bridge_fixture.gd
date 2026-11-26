extends SceneTree
## Run by check_controller_bridge.py. The parent owns the ephemeral test receiver.
## Exercise the shipping manual HTTP command path without creating a cockpit or backend.

const NativeMain = preload("res://main.gd")

class BenchBridge extends "res://runtime/bridge.gd":
	var sampled_usec: int
	var sample_to_post_ms: Array[float] = []
	var supply_snapshots := true

	func use_receiver(port: int, token: String, run_id: String) -> bool:
		# The shipping liveness check requires a child process on Unix.
		_pid = OS.create_process(OS.get_environment("BENCH_PYTHON"), ["-c", "import time; time.sleep(60)"])
		if _pid == -1:
			return false
		_port = port
		_token = token
		_ready = true
		_world = {"id": "vaderland-33"}
		last_view = {"active": true, "paused": false, "authority": "manual", "mode": "live", "run_id": run_id}
		_last_snapshot_msec = Time.get_ticks_msec()
		_command_request = _new_request()
		_command_request.request_completed.connect(_on_command)
		_command_request.request_completed.connect(receive_truth)
		return true

	func _exit_tree() -> void:
		super._exit_tree()
		if _pid != -1 and OS.is_process_running(_pid):
			OS.kill(_pid)
			_pid = -1

	func _poll_views(now: int) -> void:
		if supply_snapshots:
			_last_snapshot_msec = now

	func _send(path: String, value: Dictionary) -> void:
		sample_to_post_ms.append((Time.get_ticks_usec() - sampled_usec) / 1000.0)
		super._send(path, value)

	func receive_truth(_result: int, code: int, _headers_in: PackedStringArray, body: PackedByteArray) -> void:
		if code == 200:
			# The bench passes back the post-step snapshot for state-dependent configuration actions.
			last_view.rendering_truth = JSON.parse_string(body.get_string_from_utf8())["bench_truth"]
			view_received.emit(last_view)

var bridge := BenchBridge.new()
var main := NativeMain.new()
var pilot = main.pilot

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	root.add_child(bridge)
	if not bridge.use_receiver(int(OS.get_environment("BENCH_PORT")), OS.get_environment("BENCH_TOKEN"), OS.get_environment("BENCH_RUN")):
		fail("Could not start the fixture liveness process")
		return
	# Leave main detached. Its UI and input methods can run without invoking _ready/startup.
	main.bridge.free()
	main.bridge = bridge
	for child in [main.camera, main.aircraft, main.world]:
		main.add_child(child)
	main.create_hud()
	main.latest = bridge.last_view
	main.flight_ready = true
	bridge.view_received.connect(main.on_view)
	bridge.fault.connect(fail)
	create_timer(30.0).timeout.connect(fail.bind("Controller command bench timed out"))
	if not check_guards():
		fail("An input guard accepted a control command")
		return
	pilot.reset_demands()
	pilot.sample_state(true, 2, {}, {}, {})
	if not pilot.arm_pad():
		push_error("Could not arm neutral injected pad")
		quit(1)
		return

	await send_samples(2, {JOY_AXIS_LEFT_X: 0.70, JOY_AXIS_LEFT_Y: 0.60, JOY_AXIS_RIGHT_X: 0.55, JOY_AXIS_TRIGGER_RIGHT: 0.80}, {JOY_BUTTON_RIGHT_SHOULDER: true}, {}, 40)
	await send_samples(2, {}, {}, {}, 1)
	await send_samples(2, {JOY_AXIS_LEFT_X: -0.70, JOY_AXIS_LEFT_Y: -0.60, JOY_AXIS_RIGHT_X: -0.55, JOY_AXIS_TRIGGER_LEFT: 0.80}, {JOY_BUTTON_LEFT_SHOULDER: true}, {}, 10)
	await send_samples(-1, {}, {}, {}, 1)
	await send_samples(-1, {}, {}, {KEY_W: true, KEY_A: true, KEY_E: true, KEY_R: true, KEY_Y: true}, 12)
	await send_samples(-1, {}, {}, {}, 1)
	pilot.sample_state(true, 2, {}, {}, {})
	if not pilot.arm_pad():
		fail("Could not re-arm neutral pad")
		return
	bridge.sampled_usec = Time.get_ticks_usec()
	pilot.sample_state(true, 2, {}, {JOY_BUTTON_B: true}, {})
	for frame in 30:
		main.update_controls(1.0 / 60.0)
	await bridge._command_request.request_completed
	pilot.sample_state(true, 2, {}, {}, {})
	for button in [JOY_BUTTON_RIGHT_STICK, JOY_BUTTON_X, JOY_BUTTON_DPAD_LEFT, JOY_BUTTON_DPAD_DOWN, JOY_BUTTON_DPAD_UP, JOY_BUTTON_DPAD_RIGHT]:
		bridge.sampled_usec = Time.get_ticks_usec()
		var event := InputEventJoypadButton.new()
		event.device = 2
		event.button_index = button
		event.pressed = true
		main.handle_action(pilot.action_for_event(event))
		await bridge._command_request.request_completed
		event.pressed = false
		pilot.action_for_event(event)
	await send_samples(2, {JOY_AXIS_TRIGGER_LEFT: 1.0}, {JOY_BUTTON_RIGHT_SHOULDER: true}, {}, 12)
	for button in [JOY_BUTTON_BACK, JOY_BUTTON_Y]:
		var event := InputEventJoypadButton.new()
		event.device = 2
		event.button_index = button
		event.pressed = true
		main.handle_action(pilot.action_for_event(event))
	if main.camera_mode != 1 or not main.help_panel.visible:
		fail("View/Y failed to change the camera or show controls")
		return
	await check_dropped_release(true)
	await check_dropped_release(false)
	print(JSON.stringify({"sample_to_post_ms": bridge.sample_to_post_ms}))
	main.free()
	quit()

func send_samples(device: int, axes: Dictionary, buttons: Dictionary, keys: Dictionary, count: int) -> void:
	bridge.sampled_usec = Time.get_ticks_usec()
	for frame in count:
		pilot.sample_state(true, device, axes, buttons, keys)
		main.update_controls(1.0 / 60.0)
	await bridge._command_request.request_completed

func check_dropped_release(paused: bool) -> void:
	pilot.sample_state(true, 2, {}, {}, {})
	if not pilot.arm_pad():
		fail("Could not prepare the dropped-release check")
		return
	await send_samples(2, {JOY_AXIS_LEFT_Y: 0.7, JOY_AXIS_LEFT_X: -0.6, JOY_AXIS_RIGHT_X: 0.5}, {}, {}, 1)
	# The pilot lets go just as a pause or snapshot outage drops the queued neutral command.
	pilot.sample_state(true, 2, {}, {}, {})
	main.update_controls(1.0 / 60.0)
	var valid := bridge.last_view.duplicate()
	if paused:
		bridge.last_view = valid.merged({"paused": true}, true)
		main.on_view(bridge.last_view)
	else:
		bridge.supply_snapshots = false
		bridge._last_snapshot_msec -= bridge.CONTROL_FRESHNESS_MSEC + 1
		main.snapshot_usec -= (bridge.CONTROL_FRESHNESS_MSEC + 1) * 1000
	bridge._process(0)
	if not bridge._pending_controls.is_empty():
		fail("Pending controls survived loss of a fresh manual view")
		return
	bridge.supply_snapshots = true
	bridge.last_view = valid
	bridge._last_snapshot_msec = Time.get_ticks_msec()
	main.on_view(valid)
	if pilot.pad_armed:
		fail("Pad remained armed through pause or snapshot outage")
		return
	await send_samples(2, {}, {}, {}, 1)

func check_guards() -> bool:
	var valid := bridge.last_view.duplicate()
	for invalid in [{"paused": true}, {"authority": "colin"}, {"active": false}, {"mode": "preview"}, {"run_id": ""}]:
		bridge.last_view = valid.merged(invalid, true)
		bridge.send_controls({"yaw": 0.9})
		if not bridge._pending_controls.is_empty():
			return false
	bridge.last_view = valid
	bridge.send_controls({"leg_extension_m": [0.0, 0.0, 0.0, 0.0]})
	# A fresh buffered view after a render stall must not flush a stale gear command.
	bridge._last_snapshot_msec -= bridge.CONTROL_FRESHNESS_MSEC + 1
	bridge._process(0)
	if not bridge._pending_controls.is_empty() or not bridge._command_path.is_empty():
		return false
	bridge._last_snapshot_msec -= bridge.CONTROL_FRESHNESS_MSEC + 1
	bridge.send_controls({"yaw": 0.9})
	bridge._last_snapshot_msec = Time.get_ticks_msec()
	return bridge._pending_controls.is_empty()

func fail(message: String) -> void:
	push_error(message)
	quit(1)
