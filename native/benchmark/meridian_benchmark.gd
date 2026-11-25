extends Node
## Replays retained Phantom views through the native renderer with no simulator process.

const WORLD_SHA := "3333e153ac809f473db60750c57f181207e0378e99e078a872a9a3d854317bed"
const AIRFRAME_CONFIG_SHA := "58d12857e3d38b50deeefa982974f4e54bd37f72823218a3e5c31b9000144ba3"

var _host: Node
var _output_path: String
var _world_seed := 0
var _route: Dictionary
var _frames: Array
var _duration_s := 0.0
var _viewport_rid: RID
var _pass := 0
var _finished := false
var _endpoint_drawn := false
var _started_usec := 0
var _previous_draw_usec := 0
var _elapsed_s := 0.0
var _frame_index := 0
var _previous_index := -1
var _draw_count := 0
var _distinct_samples := 0
var _first_position := Vector3.ZERO
var _startup_s := 0.0
var _warmup: Dictionary
var _samples: Array[Dictionary] = []


func start(host: Node, input_path: String, output_path: String) -> void:
	_host = host
	_output_path = output_path
	set_process(false)
	_host.status.text = "Loading Meridian graphics"
	if DisplayServer.get_name() == "headless":
		_finish("The Meridian graphics benchmark requires the native graphical renderer.")
		return
	_route = _read_object(input_path.path_join("route.json"))
	var world := _read_object(input_path.path_join("world.json"))
	_world_seed = int(world.get("seed", 0))
	if world.get("id") != "vaderland-33" or str(world.get("version", "")) != "33.1" \
			or world.get("displayed_world_sha256") != WORLD_SHA or _world_seed != 41031:
		_finish("Benchmark world.json must contain the pinned Vaderland 33.1 world.")
		return
	if not _load_route():
		_finish("Benchmark route.json must contain the pinned Phantom A10-D replay with ordered frames.")
		return
	if not _host.world.build(world):
		_finish("The native renderer could not build the Meridian scene.")
		return
	for count in ["terrain_tiles", "road_count", "structure_count", "traffic_count", "lamp_count"]:
		if int(_host.world.stats.get(count, 0)) <= 0:
			_finish("The native Meridian scene is missing " + count + ".")
			return
	if not _host.aircraft.articulation_ready:
		_finish("The native Phantom A10-D articulation is unavailable.")
		return
	_viewport_rid = _host.get_viewport().get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(_viewport_rid, true)
	RenderingServer.frame_post_draw.connect(_on_frame_post_draw)
	get_tree().create_timer(_duration_s * 2.0 + 60.0, true, false, true).timeout.connect(_on_timeout)
	_begin_pass()
	set_process(not _finished)


func _read_object(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var decoded: Variant = JSON.parse_string(file.get_as_text())
	return decoded if decoded is Dictionary else {}


func _load_route() -> bool:
	if int(_route.get("schema_version", 0)) != 1 or str(_route.get("route_id", "")).is_empty() \
			or _route.get("world_sha256") != WORLD_SHA or _route.get("airframe_config_sha256") != AIRFRAME_CONFIG_SHA \
			or not _route.get("frames") is Array:
		return false
	_frames = _route["frames"]
	_duration_s = float(_route.get("duration_s", 0.0))
	if _frames.size() < 2 or not is_finite(_duration_s) or _duration_s <= 0.0:
		return false
	var previous_s := -1.0
	for frame in _frames:
		if not frame is Dictionary or not frame.get("view") is Dictionary:
			return false
		var timestamp := float(frame.get("t_s", -1.0))
		var view: Dictionary = frame["view"]
		if not is_finite(timestamp) or timestamp < 0.0 or timestamp <= previous_s \
				or timestamp > _duration_s + 0.000001 or not view.get("rendering_truth") is Dictionary:
			return false
		var truth: Dictionary = view["rendering_truth"]
		if truth.get("variant") != "phantom-a10d" or truth.get("config_sha256") != AIRFRAME_CONFIG_SHA:
			return false
		previous_s = timestamp
	return is_zero_approx(float(_frames[0]["t_s"])) and absf(_duration_s - previous_s) <= 0.25


func _begin_pass() -> void:
	_host.status.text = "Meridian graphics · warm-up" if _pass == 0 else "Meridian graphics · measured pass"
	_endpoint_drawn = false
	_started_usec = 0
	_previous_draw_usec = 0
	_elapsed_s = 0.0
	_frame_index = 0
	_previous_index = -1
	_draw_count = 0
	_distinct_samples = 0
	_host.set("chase_initialised", false)
	_apply_pose(0.0)
	_first_position = _host.aircraft.global_position


func _process(delta: float) -> void:
	if _endpoint_drawn:
		if _pass == 0:
			_warmup = _pass_receipt()
			_pass = 1
			_begin_pass()
		else:
			_finish("")
		return
	if _started_usec == 0:
		return
	_elapsed_s = minf(_duration_s, (Time.get_ticks_usec() - _started_usec) / 1_000_000.0)
	while _frame_index + 1 < _frames.size() and float(_frames[_frame_index + 1]["t_s"]) <= _elapsed_s + 0.000001:
		_frame_index += 1
	_apply_pose(delta)


func _apply_pose(delta: float) -> void:
	var view: Dictionary = _frames[_frame_index]["view"]
	_host.latest = view
	_host.aircraft.update_from_view(view, delta)
	if not _host.aircraft.pose_ready:
		_finish("The renderer rejected a recorded Phantom pose.")
		return
	_host.world.set_simulation_time(float(view.get("scenery_time_s", view["rendering_truth"]["t_s"])))
	_host.update_camera(delta)


func _on_frame_post_draw() -> void:
	if _finished or _endpoint_drawn:
		return
	var now := Time.get_ticks_usec()
	if _started_usec == 0:
		_started_usec = now
		if _pass == 0:
			_startup_s = (now - int(_host.launched_usec)) / 1_000_000.0
	_draw_count += 1
	var repeated := _frame_index == _previous_index
	if not repeated:
		_distinct_samples += 1
	_previous_index = _frame_index
	if _pass == 1:
		var source_frame: Dictionary = _frames[_frame_index]
		var view: Dictionary = source_frame["view"]
		_samples.append({
			"draw_usec": now - _started_usec,
			"interval_ms": null if _previous_draw_usec == 0 else (now - _previous_draw_usec) / 1000.0,
			"route_s": _elapsed_s,
			"snapshot_index": _frame_index,
			"snapshot_age_in_replay_ms": maxf(0.0, _elapsed_s - float(source_frame["t_s"])) * 1000.0,
			"snapshot_repeated": repeated,
			"recorded_sim_s": view["rendering_truth"]["t_s"],
			"recorded_scenery_s": view.get("scenery_time_s", view["rendering_truth"]["t_s"]),
			"viewport_cpu_ms": _positive_time(RenderingServer.viewport_get_measured_render_time_cpu(_viewport_rid)),
			"viewport_gpu_ms": _positive_time(RenderingServer.viewport_get_measured_render_time_gpu(_viewport_rid)),
			"objects": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME),
			"draw_calls": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
			"primitives": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),
		})
	_previous_draw_usec = now
	_endpoint_drawn = _elapsed_s >= _duration_s


func _positive_time(value: float) -> Variant:
	return value if is_finite(value) and value > 0.0 else null


func _pass_receipt() -> Dictionary:
	var last_position: Vector3 = _host.aircraft.global_position
	return {
		"route_completed": _endpoint_drawn and _frame_index == _frames.size() - 1,
		"wall_s": (_previous_draw_usec - _started_usec) / 1_000_000.0,
		"draw_callbacks": _draw_count,
		"source_snapshots": _frames.size(),
		"distinct_snapshots_drawn": _distinct_samples,
		"source_snapshots_skipped": _frames.size() - _distinct_samples,
		"repeated_snapshot_draws": _draw_count - _distinct_samples,
		"first_position_east_north_altitude_m": [_first_position.x, -_first_position.z, _first_position.y],
		"last_position_east_north_altitude_m": [last_position.x, -last_position.z, last_position.y],
	}


func _distribution(key: String) -> Dictionary:
	var values: Array[float] = []
	var over_33_ms := 0
	var over_50_ms := 0
	for sample in _samples:
		var value: Variant = sample[key]
		if value == null:
			continue
		values.append(float(value))
		if value > 33.0:
			over_33_ms += 1
		if value > 50.0:
			over_50_ms += 1
	if values.is_empty():
		return {"count": 0}
	values.sort()
	var count := values.size()
	var stats := {
		"count": count,
		"p50": values[ceili(count * 0.50) - 1],
		"p95": values[ceili(count * 0.95) - 1],
		"p99": values[ceili(count * 0.99) - 1],
		"max": values[-1],
	}
	if key == "interval_ms":
		stats["over_33_ms"] = over_33_ms
		stats["over_50_ms"] = over_50_ms
	return stats


func _on_timeout() -> void:
	_finish("Timed out waiting for the graphics replay to complete both passes.")


func _finish(problem: String) -> void:
	if _finished:
		return
	_finished = true
	set_process(false)
	if RenderingServer.frame_post_draw.is_connected(_on_frame_post_draw):
		RenderingServer.frame_post_draw.disconnect(_on_frame_post_draw)
	if _viewport_rid.is_valid():
		RenderingServer.viewport_set_measure_render_time(_viewport_rid, false)
	var viewport := _host.get_viewport()
	var window_px := DisplayServer.window_get_size()
	var viewport_px := viewport.get_texture().get_size()
	var method := RenderingServer.get_current_rendering_method()
	var driver := RenderingServer.get_current_rendering_driver_name()
	var measured := _pass_receipt() if _pass == 1 else {}
	var interval := _distribution("interval_ms")
	if problem.is_empty() and (not _warmup.get("route_completed", false) \
			or not measured.get("route_completed", false) or int(interval.get("count", 0)) < 2):
		problem = "The graphics replay did not complete both traversals with valid native draw timings."
	var world: Dictionary = _host.world.stats.duplicate()
	world["world_seed"] = _world_seed
	var receipt := {
		"passed": problem.is_empty(),
		"problem": problem,
		"mode": "native_windows_renderer_only_replay",
		"mode_limits": "Godot frame-post-draw cadence and viewport timing. Display presentation, live snapshot transport and live physics were not exercised.",
		"route_id": _route.get("route_id"),
		"prepared_route_duration_s": _duration_s,
		"world": world,
		"aircraft": {"variant": "phantom-a10d", "config_sha256": AIRFRAME_CONFIG_SHA, "visual_sha256": _host.aircraft.asset_sha256},
		"graphics": {
			"adapter": RenderingServer.get_video_adapter_name(),
			"driver": driver,
			"method": method,
			"preset": "Prototype High",
			"window_client_px": [window_px.x, window_px.y],
			"viewport_texture_px": [int(viewport_px.x), int(viewport_px.y)],
			"render_scale": viewport.scaling_3d_scale,
			"scale_mode": viewport.scaling_3d_mode,
			"cap_fps": Engine.max_fps,
			"vsync_mode": DisplayServer.window_get_vsync_mode(),
		},
		"time_to_city_first_draw_s": _startup_s if _startup_s > 0.0 else null,
		"warmup": _warmup,
		"measured": measured,
		"frame_post_draw_interval_ms": interval,
		"viewport_cpu_ms": _distribution("viewport_cpu_ms"),
		"viewport_gpu_ms": _distribution("viewport_gpu_ms"),
		"draw_calls": _distribution("draw_calls"),
		"primitives": _distribution("primitives"),
		"frames": _samples,
	}
	var file := FileAccess.open(_output_path, FileAccess.WRITE)
	if file == null:
		push_error("Could not open the benchmark result path: " + _output_path)
		get_tree().quit(1)
		return
	file.store_string(JSON.stringify(receipt, "  ") + "\n")
	file.close()
	if not problem.is_empty():
		push_error(problem)
	print("Meridian graphics receipt: ", _output_path)
	get_tree().quit(0 if problem.is_empty() else 1)
