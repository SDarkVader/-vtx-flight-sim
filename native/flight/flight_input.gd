extends RefCounted
## Maps the standard Xbox layout to the pinned Phantom's manual pilot commands.

const STICK_DEADZONE := 0.15
const TRIGGER_DEADZONE := 0.05
const COLLECTIVE_RATE := 0.42
const BOOSTER_RATE := 0.40
const AIRBRAKE_HOLD_S := 0.50
const RATE_STEP_LIMIT_S := 0.10

const BUTTON_ACTIONS := {
	JOY_BUTTON_A: "legs", JOY_BUTTON_X: "deploy_wings", JOY_BUTTON_Y: "help",
	JOY_BUTTON_BACK: "camera", JOY_BUTTON_START: "start_or_pause",
	JOY_BUTTON_LEFT_STICK: "arm_pad", JOY_BUTTON_RIGHT_STICK: "manual_collective",
	JOY_BUTTON_DPAD_LEFT: "stow_wings",
	JOY_BUTTON_DPAD_UP: "pods_vertical", JOY_BUTTON_DPAD_DOWN: "pods_forward",
	JOY_BUTTON_DPAD_RIGHT: "brakes",
}
const KEY_ACTIONS := {
	KEY_ENTER: "start", KEY_P: "pause", KEY_ESCAPE: "close", KEY_C: "camera",
	KEY_F1: "help", KEY_F2: "arm_pad", KEY_L: "legs", KEY_B: "airbrake",
	KEY_G: "deploy_wings", KEY_H: "stow_wings", KEY_1: "pods_vertical",
	KEY_2: "pods_forward", KEY_K: "brakes", KEY_M: "manual_collective",
}
const AXIS_KEYS := [KEY_W, KEY_S, KEY_D, KEY_A, KEY_E, KEY_Q, KEY_R, KEY_F, KEY_T, KEY_Y]
const PAD_AXES := [
	JOY_AXIS_LEFT_X, JOY_AXIS_LEFT_Y, JOY_AXIS_RIGHT_X,
	JOY_AXIS_TRIGGER_LEFT, JOY_AXIS_TRIGGER_RIGHT,
]

var pad_id := -1
var pad_name := ""
var pad_ready := false
var pad_armed := false
var collective := 0.0
var booster := 0.0

var _focused := false
var _axes: Dictionary = {}
var _buttons: Dictionary = {}
var _keys: Dictionary = {}
var _button_down: Dictionary = {}
var _key_down: Dictionary = {}
var _last_axes: Dictionary = {}
var _hold_time := 0.0
var _hold_fired := false


func poll(focused: bool) -> void:
	var devices := Input.get_connected_joypads()
	var selected := pad_id
	if not devices.has(selected):
		selected = -1
		for id in devices:
			var raw_name: String = Input.get_joy_info(id).get("raw_name", "")
			if is_xbox_mapping(Input.is_joy_known(id), Input.get_joy_name(id), raw_name):
				selected = id
				break
	var axes := {}
	var buttons := {}
	var keys := {}
	if selected >= 0 and focused:
		for axis in PAD_AXES:
			axes[axis] = Input.get_joy_axis(selected, axis)
		for button in BUTTON_ACTIONS:
			if Input.is_joy_button_pressed(selected, button):
				buttons[button] = true
		for button in [JOY_BUTTON_B, JOY_BUTTON_LEFT_SHOULDER, JOY_BUTTON_RIGHT_SHOULDER]:
			if Input.is_joy_button_pressed(selected, button):
				buttons[button] = true
	if focused:
		for key in AXIS_KEYS:
			if Input.is_key_pressed(key):
				keys[key] = true
	sample_state(focused, selected, axes, buttons, keys)
	pad_name = Input.get_joy_name(selected) if selected >= 0 else ""


static func is_xbox_mapping(known: bool, mapped_name: String, raw_name: String) -> bool:
	var names := (mapped_name + " " + raw_name).to_lower().replace("x-box", "xbox")
	return known and ("xbox" in names or "xinput" in names)


func sample_state(focused: bool, device_id: int, axes: Dictionary, buttons: Dictionary, keys: Dictionary) -> void:
	if device_id != pad_id or focused != _focused:
		disarm_pad()
		_button_down.clear()
		_key_down.clear()
	pad_id = device_id
	_focused = focused
	_axes = axes
	_buttons = buttons
	_keys = keys
	if not pad_ready and focused and device_id >= 0 and buttons.is_empty() and _axes_centered():
		pad_ready = true
	if not buttons.get(JOY_BUTTON_B, false):
		_reset_hold()


func notify_disconnect(device: int, connected: bool) -> void:
	if device == pad_id and not connected:
		sample_state(_focused, -1, {}, {}, _keys)
		pad_name = ""


func arm_pad() -> bool:
	if not pad_ready or not _axes_centered():
		return false
	# Either button can be the pilot's intentional arming gesture.
	for button in _buttons:
		if button != JOY_BUTTON_LEFT_STICK and button != JOY_BUTTON_START:
			return false
	pad_armed = true
	return true


func disarm_pad() -> void:
	pad_armed = false
	pad_ready = false
	_reset_hold()


func _axes_centered() -> bool:
	for axis in PAD_AXES:
		if axis == JOY_AXIS_TRIGGER_LEFT or axis == JOY_AXIS_TRIGGER_RIGHT:
			if _trigger(axis) > 0.0:
				return false
		elif _stick(axis) != 0.0:
			return false
	return true


func _stick(axis: int) -> float:
	var raw := clampf(float(_axes.get(axis, 0.0)), -1.0, 1.0)
	return signf(raw) * maxf(absf(raw) - STICK_DEADZONE, 0.0) / (1.0 - STICK_DEADZONE)


func _trigger(axis: int) -> float:
	return clampf((float(_axes.get(axis, 0.0)) - TRIGGER_DEADZONE) / (1.0 - TRIGGER_DEADZONE), 0.0, 1.0)


func _key_axis(positive: Key, negative: Key) -> float:
	if not _focused:
		return 0.0
	return float(_keys.get(positive, false)) - float(_keys.get(negative, false))


func _collective_rate() -> float:
	var pad := _trigger(JOY_AXIS_TRIGGER_RIGHT) - _trigger(JOY_AXIS_TRIGGER_LEFT) if pad_armed else 0.0
	return clampf(pad + _key_axis(KEY_R, KEY_F), -1.0, 1.0)


func _booster_rate() -> float:
	var pad := 0.0
	if pad_armed:
		pad = float(_buttons.get(JOY_BUTTON_RIGHT_SHOULDER, false)) - float(_buttons.get(JOY_BUTTON_LEFT_SHOULDER, false))
	return clampf(pad + _key_axis(KEY_T, KEY_Y), -1.0, 1.0)


func reset_demands(collective_value := 0.0, booster_value := 0.0) -> void:
	set_power_targets(collective_value, booster_value)
	_last_axes.clear()


func resample_owned_axes() -> void:
	# A pending centre command can be discarded when telemetry stops or the sortie pauses.
	for field in _last_axes:
		_last_axes[field] = null


func set_power_targets(collective_value: float, booster_value: float) -> void:
	collective = clampf(collective_value, 0.0, 1.0)
	booster = clampf(booster_value, 0.0, 1.0)


func sync_demands(command: Dictionary) -> void:
	if command.has("collective") and is_zero_approx(_collective_rate()):
		collective = clampf(float(command.collective), 0.0, 1.0)
	var pair: Array = command.get("booster_throttle", [])
	if pair.size() == 2 and is_zero_approx(_booster_rate()):
		booster = clampf((float(pair[0]) + float(pair[1])) * 0.5, 0.0, 1.0)


func get_axis_patch(delta: float) -> Dictionary:
	var patch := {}
	# Godot reports stick back/down as positive Y. The aircraft accepts +pitch nose-up.
	_add_axis(patch, "pitch", JOY_AXIS_LEFT_Y, _key_axis(KEY_W, KEY_S) * 0.34)
	_add_axis(patch, "roll", JOY_AXIS_LEFT_X, _key_axis(KEY_D, KEY_A) * 0.46)
	_add_axis(patch, "yaw", JOY_AXIS_RIGHT_X, _key_axis(KEY_E, KEY_Q) * 0.40)
	# A delayed frame must not turn a short press into seconds of extra thrust.
	var step := clampf(delta, 0.0, RATE_STEP_LIMIT_S)
	var previous_collective := snappedf(collective, 0.001)
	var previous_booster := snappedf(booster, 0.001)
	collective = clampf(collective + _collective_rate() * COLLECTIVE_RATE * step, 0.0, 1.0)
	booster = clampf(booster + _booster_rate() * BOOSTER_RATE * step, 0.0, 1.0)
	if not is_equal_approx(previous_collective, snappedf(collective, 0.001)):
		patch.collective = snappedf(collective, 0.001)
	if not is_equal_approx(previous_booster, snappedf(booster, 0.001)):
		var target := snappedf(booster, 0.001)
		patch.booster_throttle = [target, target]
	return patch


func _add_axis(patch: Dictionary, field: String, axis: int, keyboard: float) -> void:
	var value := snappedf(clampf(keyboard + (_stick(axis) if pad_armed else 0.0), -1.0, 1.0), 0.001)
	var previous: Variant = _last_axes.get(field, 0.0)
	if previous == null or not is_equal_approx(value, float(previous)):
		patch[field] = value
		_last_axes[field] = value


func action_for_event(event: InputEvent) -> String:
	if not _focused:
		return ""
	if event is InputEventKey:
		var key: Key = event.physical_keycode
		if not event.pressed:
			_key_down.erase(key)
		elif not event.echo and not _key_down.has(key) and KEY_ACTIONS.has(key):
			_key_down[key] = true
			return KEY_ACTIONS[key]
	if event is InputEventJoypadButton and pad_ready and event.device == pad_id:
		var button: int = event.button_index
		if not event.pressed:
			_button_down.erase(button)
			if button == JOY_BUTTON_B:
				_reset_hold()
		elif not _button_down.has(button) and BUTTON_ACTIONS.has(button):
			_button_down[button] = true
			var action: String = BUTTON_ACTIONS[button]
			if pad_armed or action in ["help", "camera", "arm_pad", "start_or_pause"]:
				return action
	return ""


func drain_hold_action(delta: float) -> String:
	if pad_armed and _buttons.get(JOY_BUTTON_B, false) and not _hold_fired:
		_hold_time += clampf(delta, 0.0, RATE_STEP_LIMIT_S)
		if _hold_time >= AIRBRAKE_HOLD_S - 0.000001:
			_hold_fired = true
			return "airbrake"
	return ""


func _reset_hold() -> void:
	_hold_time = 0.0
	_hold_fired = false
