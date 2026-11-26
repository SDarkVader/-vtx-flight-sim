extends SceneTree
## Read one real solver snapshot, measure all four native GLB legs and sample the pilot action.

const AircraftView := preload("res://flight/phantom_view.gd")
const FlightActions := preload("res://flight/flight_actions.gd")
const FlightInput := preload("res://flight/flight_input.gd")
const CORNERS := ["FL", "FR", "RL", "RR"]


func _initialize() -> void:
	call_deferred("_probe")


func _probe() -> void:
	var args := OS.get_cmdline_user_args()
	var view: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var aircraft := AircraftView.new()
	root.add_child(aircraft)
	var slides := {}
	for node: Node3D in aircraft.find_children("*", "Node3D", true, false):
		var extras: Dictionary = node.get_meta("extras", {})
		var key: String = extras.get("phantom_joint", "")
		if key in ["leg_FL", "leg_FR", "leg_RL", "leg_RR"]:
			var axis: Array = extras["axis_parent"]
			var feet := node.find_children("LEG_*_SHOCK_FOOT", "MeshInstance3D", false, false)
			if feet.size() != 1 or (feet[0] as MeshInstance3D).mesh == null:
				push_error("Missing the pinned foot mesh for " + key)
				quit(1)
				return
			var foot := feet[0] as MeshInstance3D
			slides[key] = {
				"foot": foot, "slider": node, "rest": node.transform * foot.position,
				"q_rest": extras["q_rest"],
				"axis": Vector3(axis[0], axis[1], axis[2]).normalized()
			}
	aircraft.update_from_view(view, 0.0)
	if not aircraft.pose_ready or not aircraft.articulation_ready or slides.size() != 4:
		push_error("The pinned Phantom did not load all four leg sliders.")
		quit(1)
		return
	var rendered := []
	for corner in CORNERS:
		var slide: Dictionary = slides["leg_" + corner]
		# Compare the actual mesh center in its slider parent's frame, independent of aircraft pose.
		var delta: Vector3 = slide.slider.transform * slide.foot.position - slide.rest
		if delta.slide(slide.axis).length() > 0.00001:
			push_error("The leg moved across its authored slide axis: " + corner)
			quit(1)
			return
		rendered.append(delta.dot(slide.axis) + float(slide.q_rest))
	var input := FlightInput.new()
	input.sample_state(true, 1, {}, {}, {})
	var pad := InputEventJoypadButton.new()
	pad.device = 1
	pad.button_index = JOY_BUTTON_A
	pad.pressed = true
	var keyboard := InputEventKey.new()
	keyboard.physical_keycode = KEY_L
	keyboard.pressed = true
	if not input.arm_pad():
		push_error("Could not arm the centered fixture controller.")
		quit(1)
		return
	var action: String = input.action_for_event(pad)
	if action != "legs" or input.action_for_event(keyboard) != action or input.action_for_event(pad) != "":
		push_error("Expected one landing-leg action per press on Xbox A or keyboard L.")
		quit(1)
		return
	var result := {
		"rendered_slider_plus_oleo_m": rendered,
		"patch": FlightActions.configuration_patch(action, view),
	}
	var output := FileAccess.open(args[1], FileAccess.WRITE)
	if output == null:
		quit(1)
		return
	output.store_string(JSON.stringify(result, "\t") + "\n")
	output.close()
	quit(0)
