extends SceneTree
## Headless input fixture. No cockpit scene, network, saved flight or virtual device.

const FlightInput = preload("res://flight/flight_input.gd")
var controls = FlightInput.new()
var failures: Array[String] = []
var checks := 0


func check(condition: bool, label: String) -> void:
	checks += 1
	if not condition:
		failures.append(label)
		push_error(label)


func near(actual: Variant, expected: float, label: String) -> void:
	check(actual != null and absf(float(actual) - expected) < 0.00001, label)


func button(index: JoyButton, pressed := true, device_id := 3) -> String:
	var event := InputEventJoypadButton.new()
	event.button_index = index
	event.device = device_id
	event.pressed = pressed
	return controls.action_for_event(event)


func key(code: Key, pressed := true, echo := false) -> String:
	var event := InputEventKey.new()
	event.physical_keycode = code
	event.pressed = pressed
	event.echo = echo
	return controls.action_for_event(event)


func _initialize() -> void:
	check(FlightInput.is_xbox_mapping(true, "Xbox Wireless Controller", ""), "Standard Bluetooth mapping name is eligible")
	check(FlightInput.is_xbox_mapping(true, "XInput Controller", ""), "Windows XInput mapping name is eligible")
	check(FlightInput.is_xbox_mapping(true, "Gamepad", "Microsoft X-Box One pad"), "SDL raw Xbox name is eligible")
	check(not FlightInput.is_xbox_mapping(true, "vJoy Device", "Virtual Joystick"), "Mapped unrelated joystick is excluded")
	check(not FlightInput.is_xbox_mapping(false, "Xbox Wireless Controller", ""), "Device without a standard mapping is excluded")
	var axes := {
		JOY_AXIS_LEFT_X: 0.575, JOY_AXIS_LEFT_Y: 0.3625, JOY_AXIS_RIGHT_X: -0.7875,
		JOY_AXIS_TRIGGER_RIGHT: 0.525, JOY_AXIS_TRIGGER_LEFT: 0.2875,
	}
	controls.sample_state(true, 3, axes, {JOY_BUTTON_RIGHT_SHOULDER: true}, {})
	check(not controls.arm_pad(), "Held controls at connection must not arm the pad")
	check(controls.get_axis_patch(0.1).is_empty(), "Connected pad must be inert before arming")
	controls.sample_state(true, 3, {}, {}, {})
	check(key(KEY_ENTER) == "start", "Keyboard Enter can start with a disarmed pad")
	key(KEY_ENTER, false)
	check(button(JOY_BUTTON_A).is_empty(), "Disarmed pad cannot issue legs action")
	button(JOY_BUTTON_A, false)
	check(button(JOY_BUTTON_START) == "start_or_pause", "Parked Menu works before arming")
	button(JOY_BUTTON_START, false)
	check(controls.arm_pad(), "Centered pad can be explicitly armed")
	controls.sample_state(true, 3, axes, {JOY_BUTTON_RIGHT_SHOULDER: true}, {})
	var patch: Dictionary = controls.get_axis_patch(0.1)
	check(patch.size() == 5, "Joint sample includes all five control channels")
	near(patch.get("pitch"), 0.25, "Pull back for proportional nose-up pitch")
	near(patch.get("roll"), 0.5, "Moving the left stick to the right banks right")
	near(patch.get("yaw"), -0.75, "Left deflection on right thumb yaws left")
	near(patch.get("collective"), 0.011, "Analog triggers independently subtract as held rates")
	near(patch.booster_throttle[0], 0.04, "Right bumper raises both boosters")
	check(patch.booster_throttle[0] == patch.booster_throttle[1], "Common booster pair matches")
	controls.sample_state(true, 3, {JOY_AXIS_LEFT_X: -1, JOY_AXIS_LEFT_Y: -1, JOY_AXIS_RIGHT_X: 1}, {}, {})
	patch = controls.get_axis_patch(0.016)
	check(patch == {"pitch": -1.0, "roll": -1.0, "yaw": 1.0}, "Forward, left bank and nose right reach full demand together")
	controls.sample_state(true, 3, {JOY_AXIS_LEFT_X: 0.149, JOY_AXIS_TRIGGER_RIGHT: 0.049}, {}, {})
	patch = controls.get_axis_patch(0.016)
	check(patch == {"pitch": 0.0, "roll": 0.0, "yaw": 0.0}, "Deadzone drift neutralizes former axes without a thrust command")
	check(controls.get_axis_patch(0.1).is_empty(), "Idle centered pad sends nothing")
	near(controls.collective, 0.0105, "Collective retained on release")
	near(controls.booster, 0.04, "Boosters retained on release")
	controls.sync_demands({"collective": 0.55, "booster_throttle": [0.0, 0.0]})
	controls.sample_state(true, 3, {JOY_AXIS_TRIGGER_LEFT: 1}, {JOY_BUTTON_LEFT_SHOULDER: true}, {})
	patch = controls.get_axis_patch(0.1)
	near(patch.get("collective"), 0.508, "LT decreases from the latest authoritative collective")
	check(not patch.has("booster_throttle"), "LB respects zero boost after ECU change")
	controls.sample_state(true, 3, {JOY_AXIS_TRIGGER_LEFT: 1, JOY_AXIS_TRIGGER_RIGHT: 1},
			{JOY_BUTTON_LEFT_SHOULDER: true, JOY_BUTTON_RIGHT_SHOULDER: true}, {})
	check(controls.get_axis_patch(0.1).is_empty(), "Opposite triggers and bumpers cancel")
	controls.sample_state(true, 3, {}, {}, {})
	controls.sync_demands({"collective": 0.99, "booster_throttle": [0.99, 0.99]})
	controls.sample_state(true, 3, {JOY_AXIS_TRIGGER_RIGHT: 1}, {JOY_BUTTON_RIGHT_SHOULDER: true}, {})
	patch = controls.get_axis_patch(0.1)
	check(patch == {"collective": 1.0, "booster_throttle": [1.0, 1.0]}, "Power is limited to full demand")
	check(controls.get_axis_patch(0.1).is_empty(), "Held at limit does not repeat commands")
	for index in FlightInput.BUTTON_ACTIONS:
		var expected: String = FlightInput.BUTTON_ACTIONS[index]
		check(button(index) == expected, "Mapped button press: " + expected)
		check(button(index).is_empty(), "Holding does not repeat: " + expected)
		check(button(index, false).is_empty(), "Release is silent: " + expected)
	check(button(JOY_BUTTON_A, true, 1).is_empty(), "Unselected device cannot command the aircraft")
	controls.sample_state(true, 3, {}, {JOY_BUTTON_B: true}, {})
	check(button(JOY_BUTTON_B).is_empty(), "A tap does not engage the airbrake")
	for frame in 4:
		check(controls.drain_hold_action(0.1).is_empty(), "Airbrake hold is below threshold")
	check(controls.drain_hold_action(0.1) == "airbrake", "Half-second hold triggers airbrake")
	check(controls.drain_hold_action(0.1).is_empty(), "Airbrake action fires once per hold")
	button(JOY_BUTTON_B, false)
	check(controls.drain_hold_action(0.01).is_empty(), "A quick re-press starts a new airbrake hold")
	controls.sample_state(true, 3, {JOY_AXIS_RIGHT_X: 0.575}, {}, {KEY_W: true})
	patch = controls.get_axis_patch(0.016)
	near(patch.get("yaw"), 0.5, "Pad yaw works alongside keyboard")
	near(patch.get("pitch"), 0.34, "W retains the native keyboard pitch demand")
	controls.notify_disconnect(3, false)
	patch = controls.get_axis_patch(0.016)
	check(patch == {"yaw": 0.0}, "Disconnect immediately releases pad yaw and keeps keyboard pitch")
	near(controls.booster, 1.0, "Disconnect preserves booster setting")
	controls.sample_state(true, 3, {JOY_AXIS_RIGHT_X: 1}, {}, {})
	check(not controls.arm_pad(), "Axis held over disconnect cannot re-arm")
	patch = controls.get_axis_patch(0.016)
	check(patch == {"pitch": 0.0}, "Keyboard release still neutralizes pitch")
	controls.sample_state(true, 3, {}, {}, {})
	check(not controls.pad_armed and controls.get_axis_patch(0.016).is_empty(), "Reconnected pad remains unarmed until instructed")
	check(controls.arm_pad(), "Explicit centered re-arm succeeds")
	controls.sample_state(true, 3, {JOY_AXIS_LEFT_Y: -1}, {}, {KEY_E: true})
	controls.get_axis_patch(0.016)
	controls.sample_state(false, 3, {JOY_AXIS_LEFT_Y: -1}, {}, {KEY_E: true})
	patch = controls.get_axis_patch(0.016)
	check(patch == {"pitch": 0.0, "yaw": 0.0}, "Focus loss neutralizes both input sources")
	check(button(JOY_BUTTON_Y).is_empty() and key(KEY_C).is_empty(), "Background input cannot invoke actions")
	controls.sample_state(true, -1, {}, {}, {KEY_S: true, KEY_A: true, KEY_Q: true, KEY_F: true, KEY_Y: true})
	patch = controls.get_axis_patch(0.1)
	check(patch.size() == 5, "Keyboard-only sample preserves all five channels")
	near(patch.get("roll"), -0.46, "Keyboard roll limit")
	near(patch.get("pitch"), -0.34, "Keyboard pitch limit")
	near(patch.get("yaw"), -0.40, "Keyboard yaw limit")
	near(patch.get("collective"), 0.958, "F reduces collective at its existing rate")
	near(patch.booster_throttle[1], 0.96, "Y reduces boosters at their existing rate")
	for code in FlightInput.KEY_ACTIONS:
		var expected: String = FlightInput.KEY_ACTIONS[code]
		check(key(code) == expected, "Keyboard equivalent: " + expected)
		check(key(code, true, true).is_empty(), "OS repeat is silent: " + expected)
		check(key(code, false).is_empty(), "Key release is silent: " + expected)
	print(JSON.stringify({"test": "injected_godot_input", "checks": checks, "failures": failures}))
	quit(0 if failures.is_empty() else 1)
