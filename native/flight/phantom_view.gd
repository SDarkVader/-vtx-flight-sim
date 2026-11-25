extends Node3D
## The native view uses the A10-D's pinned visual asset and MuJoCo telemetry.

const VISUAL := preload("res://flight/phantom-a10b-visual.glb")
const VARIANT := "phantom-a10d"
const VISUAL_URI := "/assets/phantom-a10b-visual.glb"
const CONFIG_SHA256 := "58d12857e3d38b50deeefa982974f4e54bd37f72823218a3e5c31b9000144ba3"
# The GLB is authored X-forward, Y-north, Z-up, matching the backend neutral rig.
# Godot's world uses East, Up, -North. This is a proper rotation.
const WORLD_FROM_VTX := Basis(Vector3.RIGHT, Vector3.FORWARD, Vector3.UP)
const WHEEL_PARTS := ["AMBER_RING", "CLOSED_TYRE", "STRUCTURAL_DISK"]

class Joint:
	var node: Node3D
	var axis: Vector3
	var rest_position: Vector3
	var rest_rotation: Quaternion
	var rest_value: float
	var slides: bool

	func apply(value: float) -> void:
		var displacement := value - rest_value
		if slides:
			node.position = rest_position + axis * displacement
		else:
			node.quaternion = Quaternion(axis, displacement) * rest_rotation

class Wheel:
	var suspension: Node3D
	var steering: Node3D
	var spin: Node3D
	var axle: Vector3

const asset_sha256 := "45364301f2950ca57e5b34ac73d29b0abe11471dd82f0fe0e5068da70418a93e"
var articulation_ready := false
var pose_ready := false
var _joints: Dictionary[String, Joint] = {}
var _wheels: Dictionary[String, Wheel] = {}
var _drs: Joint
var _run_id := ""
var _snapshot_time := -1.0
var _from := Transform3D.IDENTITY
var _target := Transform3D.IDENTITY
var _elapsed := 0.0
var _duration := 0.0


func _ready() -> void:
	visible = false
	var model := VISUAL.instantiate() as Node3D
	add_child(model)
	for child in model.find_children("*", "Node3D", true, false):
		var node := child as Node3D
		var extras: Dictionary = node.get_meta("extras", {})
		var key: String = extras.get("phantom_joint", "")
		if node.name == &"VTX_VISUAL_DRS_HINGE":
			_drs = _bind_joint(node, extras)
		if key.is_empty():
			continue
		var joint := _bind_joint(node, extras)
		if joint == null or _joints.has(key):
			push_error("Invalid Phantom GLB joint metadata: " + key)
			return
		_joints[key] = joint
		if key.begins_with("pod_"):
			var wheel := _bind_wheel(node, key)
			if wheel != null:
				_wheels[key] = wheel
	var airframe := model.find_child("airframe", true, false) as Node3D
	articulation_ready = airframe != null and _joints.size() == 28 and _wheels.size() == 4
	if not articulation_ready:
		push_error("The Phantom asset is missing its airframe, 28 joints or four tyre pivots.")


func update_from_view(view: Dictionary, delta: float) -> void:
	var truth: Dictionary = view.get("rendering_truth", {})
	var provenance: Dictionary = truth.get("provenance", {})
	if not articulation_ready or truth.get("variant") != VARIANT \
			or truth.get("config_sha256") != CONFIG_SHA256 \
			or provenance.get("render_asset") != VISUAL_URI:
		visible = false
		pose_ready = false
		return
	var bodies: Dictionary = truth.get("body_poses", {})
	var origin: Dictionary = bodies.get("airframe", {})
	var coordinates: Array = origin.get("position", [])
	var orientation: Array = origin.get("quaternion_wxyz", [])
	if coordinates.size() != 3 or orientation.size() != 4:
		return

	var position_vtx := _vector(coordinates)
	var rotation_vtx := _quaternion(orientation)
	if not position_vtx.is_finite() or not rotation_vtx.is_finite() \
			or rotation_vtx.length_squared() <= 0.000001:
		return
	var target := Transform3D(
		WORLD_FROM_VTX * Basis(rotation_vtx.normalized()), WORLD_FROM_VTX * position_vtx
	)
	var simulated_time: float = truth.get("t_s", 0.0)
	var run_id := str(view.get("run_id", ""))
	var snap: bool = not pose_ready or run_id != _run_id or simulated_time < _snapshot_time \
			or view.get("paused", false) or not view.get("active", false)
	if not pose_ready or run_id != _run_id or simulated_time != _snapshot_time or not target.is_equal_approx(_target):
		var motion_scale := maxf(0.01, float(view.get("time_scale", 1.0)))
		_from = global_transform
		_target = target
		_elapsed = 0.0
		_duration = 0.0 if snap else clampf((simulated_time - _snapshot_time) / motion_scale, 0.025, 0.14)
		_run_id = run_id
		_snapshot_time = simulated_time
		_apply_joints(truth, bodies)
	if snap:
		_duration = 0.0
	_elapsed += maxf(0.0, delta)
	if _duration <= 0.0:
		global_transform = _target
	else:
		global_transform = _from.interpolate_with(_target, clampf(_elapsed / _duration, 0.0, 1.0))
	pose_ready = true
	visible = true


func _bind_joint(node: Node3D, extras: Dictionary) -> Joint:
	var axis: Array = extras.get("axis_parent", [])
	var kind: String = extras.get("joint_type", "")
	if axis.size() != 3 or not extras.has("q_rest") or kind not in ["slide", "hinge"]:
		return null
	var joint := Joint.new()
	joint.node = node
	joint.axis = _vector(axis).normalized()
	joint.rest_value = float(extras["q_rest"])
	joint.rest_position = node.position
	joint.rest_rotation = node.quaternion
	joint.slides = kind == "slide"
	return joint


func _bind_wheel(pod: Node3D, key: String) -> Wheel:
	var cad := str(pod.name).trim_prefix("JOINT_WHEEL_POD_")
	var tyre := pod.find_child("WHEEL_%s_CLOSED_TYRE" % cad, true, false) as Node3D
	if tyre == null:
		return null
	var wheel := Wheel.new()
	wheel.suspension = Node3D.new()
	wheel.suspension.name = "MeasuredSuspension"
	pod.add_child(wheel.suspension)
	wheel.steering = Node3D.new()
	wheel.steering.name = "MeasuredSteering"
	wheel.suspension.add_child(wheel.steering)
	wheel.spin = Node3D.new()
	wheel.spin.name = "MeasuredWheelSpin"
	wheel.steering.add_child(wheel.spin)
	wheel.axle = Vector3.UP if key.ends_with("L") else Vector3.DOWN

	for suffix in WHEEL_PARTS:
		var part := pod.find_child("WHEEL_%s_%s" % [cad, suffix], true, false) as Node3D
		if part != null:
			part.reparent(wheel.spin, true)
	var spokes := pod.find_child("VTX_VISUAL_WHEEL_%s_VTX_ALLOY_SPOKES" % cad, true, false) as Node3D
	if spokes != null:
		spokes.reparent(wheel.spin, true)
	return wheel


func _apply_joints(truth: Dictionary, bodies: Dictionary) -> void:
	var phantom: Dictionary = truth.get("phantom", {})
	var values: Dictionary = phantom.get("joints", {})
	for key in _joints:
		if not values.has(key):
			continue
		var value: float = values[key]
		if key.begins_with("leg_"):
			value += float(values.get(key + "_oleo", 0.0))
		_joints[key].apply(value)
	for key in _wheels:
		_apply_wheel(_wheels[key], key, values, bodies)
	var drs: Variant = phantom.get("drs_deg")
	if _drs != null and drs != null:
		# The authored stabilator already contains the browser rig's six-degree rest tilt.
		_drs.apply(deg_to_rad(float(drs) - 6.0))


func _apply_wheel(wheel: Wheel, key: String, values: Dictionary, bodies: Dictionary) -> void:
	var spin_key := key + "_wheel"
	wheel.suspension.visible = values.has(key + "_susp") and values.has(spin_key)
	if not wheel.suspension.visible:
		return
	wheel.suspension.position.z = float(values[key + "_susp"])
	wheel.steering.quaternion = Quaternion(Vector3.BACK, float(values.get(key + "_steer", 0.0)))
	wheel.spin.quaternion = Quaternion(wheel.axle, fposmod(float(values[spin_key]), TAU))

	var pod_pose: Dictionary = bodies.get(key, {})
	var wheel_pose: Dictionary = bodies.get(spin_key, {})
	var pod_orientation: Array = pod_pose.get("quaternion_wxyz", [])
	var wheel_orientation: Array = wheel_pose.get("quaternion_wxyz", [])
	if pod_orientation.size() != 4 or wheel_orientation.size() != 4:
		return
	# Read steer and spin from the same measured pair of body orientations.
	# This avoids combining joint angles from a different integration step.
	var relative := _quaternion(pod_orientation).normalized().inverse() \
		* _quaternion(wheel_orientation).normalized()
	var spin := Quaternion(0.0, relative.y, 0.0, relative.w)
	if spin.length_squared() <= 0.000001:
		return
	spin = spin.normalized()
	var steer := (relative * spin.inverse()).normalized()
	if Vector2(steer.x, steer.y).length() <= 0.00001:
		wheel.spin.quaternion = spin
		wheel.steering.quaternion = steer


static func _vector(value: Array) -> Vector3:
	return Vector3(float(value[0]), float(value[1]), float(value[2]))


static func _quaternion(value: Array) -> Quaternion:
	return Quaternion(float(value[1]), float(value[2]), float(value[3]), float(value[0]))
