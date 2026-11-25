extends Node
## Owns one private VTX process and reads the authoritative cockpit snapshots.

signal ready_to_fly(world: Dictionary)
signal view_received(view: Dictionary)
signal fault(message: String)

const PHANTOM := "phantom-a10d"
const ENVIRONMENT := "vaderland-33"
const WORLD_VERSION := "33.1"
const WORLD_HASH := "3333e153ac809f473db60750c57f181207e0378e99e078a872a9a3d854317bed"
const START_TIMEOUT_MSEC := 60_000
const SNAPSHOT_TIMEOUT_MSEC := 12_000
const INPUT_INTERVAL_MSEC := 100

var last_view: Dictionary = {}
var runtime_identity: Dictionary = {}
var session_path := ""

var _pid := -1
var _port := 0
var _token := ""
var _started_msec := 0
var _last_snapshot_msec := 0
var _next_connect_msec := 0
var _next_input_msec := 0
var _ready := false
var _closing := false
var _failed := false
var _world: Dictionary = {}
var _socket: WebSocketPeer
var _command_request: HTTPRequest
var _command_path := ""
var _pending_controls: Dictionary = {}
var _pending_pause: Variant = null


func start() -> void:
	if _pid != -1:
		return
	if OS.get_name() != "Windows":
		_fail("The bundled VTX simulator currently supports Windows x64.")
		return
	var bundle := OS.get_environment("VTX_NATIVE_BUNDLE_ROOT")
	if bundle.is_empty():
		bundle = OS.get_executable_path().get_base_dir()
	var python := bundle.path_join("runtime/pythonw.exe")
	if not FileAccess.file_exists(python):
		python = bundle.path_join("runtime/python.exe")
	var launcher := bundle.path_join("game/launch_backend.py")
	if not FileAccess.file_exists(python) or not FileAccess.file_exists(launcher):
		_fail("The VTX simulator bundle is missing beside the game executable.")
		return
	var data_root := OS.get_environment("VTX_NATIVE_DATA_ROOT")
	if data_root.is_empty():
		data_root = ProjectSettings.globalize_path("user://sessions")
	if not data_root.is_absolute_path():
		_fail("Use an absolute data directory for the native simulator.")
		return
	var session_id := Crypto.new().generate_random_bytes(16).hex_encode()
	session_path = data_root.path_join(session_id)
	if DirAccess.make_dir_recursive_absolute(session_path) != OK:
		_fail("Cannot create a private flight data directory at " + session_path)
		return
	_command_request = _new_request()
	_command_request.request_completed.connect(_on_command)
	_started_msec = Time.get_ticks_msec()
	_pid = OS.create_process(python, PackedStringArray([
		"-B", launcher, "--session", session_path, "--parent-pid", str(OS.get_process_id()),
	]), false)
	if _pid == -1:
		_fail("Windows could not start the bundled VTX simulator.")


func start_flight() -> void:
	if not _ready or _closing or _failed or bool(last_view.get("active", false)):
		return
	var departure: Array = _world.get("default_departure", [])
	var destination: Array = _world.get("default_destination", [])
	if departure.size() != 2 or destination.size() != 2:
		_fail("The selected world did not provide a usable departure.")
		return
	_send("/api/mission", {
		"airframe_variant": PHANTOM,
		"environment": ENVIRONMENT,
		"departure": departure,
		"destination": destination,
		"departure_heading_deg": 90.0,
		"authority": "manual",
		"label": "Native Phantom A10-D flight",
		"phantom": {"start_configuration": "vtol"},
	})


func send_controls(patch: Dictionary) -> void:
	if not _ready or _closing or _failed or not bool(last_view.get("active", false)):
		return
	_pending_controls.merge(patch, true)


func pause(paused: bool) -> void:
	if _ready and not _closing and not _failed and bool(last_view.get("active", false)):
		_pending_pause = paused


func quit() -> void:
	_closing = true
	if _socket != null:
		_socket.close()
	_pending_controls.clear()
	if not session_path.is_empty():
		var stop := FileAccess.open(session_path.path_join("stop-server.flag"), FileAccess.WRITE)
		if stop != null:
			stop.close()


func _exit_tree() -> void:
	quit()


func _process(_delta: float) -> void:
	if _closing or _failed or _pid == -1:
		return
	var now := Time.get_ticks_msec()
	if not _ready and now - _started_msec >= START_TIMEOUT_MSEC:
		_fail("The VTX simulator did not finish starting.")
		return
	if not OS.is_process_running(_pid):
		var error_data := _read_json(session_path.path_join("error.json"))
		_fail(str(error_data.get("message", "The VTX simulator closed unexpectedly.")))
		return
	if _world.is_empty():
		if now >= _next_connect_msec:
			_readiness_check()
		return
	_poll_views(now)
	if _ready and now - _last_snapshot_msec >= SNAPSHOT_TIMEOUT_MSEC:
		_fail("The VTX simulator stopped sending cockpit snapshots.")
		return
	if not _ready or not _command_path.is_empty():
		return
	if _pending_pause != null:
		var request := {"paused": _pending_pause}
		_pending_pause = null
		_send("/api/operator", request)
		return
	if now >= _next_input_msec and not _pending_controls.is_empty():
		if bool(last_view.get("active", false)) and last_view.get("run_id") is String:
			var patch := _pending_controls.duplicate()
			patch["schema"] = "phantom-fbw-1"
			patch["authority"] = "manual"
			patch["expected_run_id"] = last_view["run_id"]
			patch["reason"] = "Native Phantom keyboard controls"
			_next_input_msec = now + INPUT_INTERVAL_MSEC
			_send("/api/action", patch)
		_pending_controls.clear()


func _readiness_check() -> void:
	var state := _read_json(session_path.path_join("ready.json"))
	if state.is_empty():
		return
	_port = int(state.get("port", 0))
	_token = str(state.get("token", ""))
	var identity: Dictionary = state.get("identity", {})
	if (
		_port < 1 or _port > 65535 or _token.length() < 32 or int(state.get("pid", -2)) != _pid
		or identity.get("variant") != PHANTOM or identity.get("verified") != true
		or state.get("world_hash") != WORLD_HASH
	):
		_fail("The local simulator reported a mismatched identity.")
		return
	# The local launcher writes the existing API world payload before publishing readiness.
	# This transfers the 27 MB world once without delaying the live snapshot connection.
	var world := _read_json(session_path.path_join("initial-world.json"))
	if (
		world.get("id") != ENVIRONMENT or world.get("version") != WORLD_VERSION
		or world.get("displayed_world_sha256") != WORLD_HASH
	):
		_fail("The cockpit received an unexpected Vaderland world.")
		return
	runtime_identity = identity
	_world = world


func _poll_views(now: int) -> void:
	if _socket == null or _socket.get_ready_state() == WebSocketPeer.STATE_CLOSED:
		if now < _next_connect_msec:
			return
		_next_connect_msec = now + 300
		_socket = WebSocketPeer.new()
		_socket.inbound_buffer_size = 4 * 1024 * 1024
		_socket.handshake_headers = PackedStringArray(["Authorization: Bearer " + _token])
		if _socket.connect_to_url("ws://127.0.0.1:%d/ws" % _port) != OK:
			_socket = null
			return
	_socket.poll()
	if _socket.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return
	# Drop older queued frames rather than replaying stale poses after a client stall.
	var packet := PackedByteArray()
	while _socket.get_available_packet_count() > 0:
		packet = _socket.get_packet()
	if packet.is_empty():
		return
	var value: Variant = JSON.parse_string(packet.get_string_from_utf8())
	if not value is Dictionary:
		_fail("The VTX simulator sent an invalid cockpit snapshot.")
		return
	var truth: Dictionary = value.get("rendering_truth", {})
	var world: Dictionary = value.get("environment", {})
	if truth.get("variant") != PHANTOM or world.get("displayed_world_sha256") != WORLD_HASH:
		_fail("The VTX simulator changed the selected aircraft or world.")
		return
	_last_snapshot_msec = now
	if value.get("run_id") != last_view.get("run_id"):
		_pending_controls.clear()
		_pending_pause = null
	last_view = value
	if not _ready:
		_ready = true
		ready_to_fly.emit(_world)
	view_received.emit(last_view)


func _send(path: String, value: Dictionary) -> void:
	if not _command_path.is_empty():
		return
	_command_path = path
	if _command_request.request(_url(path), _headers(), HTTPClient.METHOD_POST, JSON.stringify(value)) != OK:
		_command_path = ""
		_fail("The cockpit could not send a simulator command.")


func _on_command(result: int, code: int, _headers_received: PackedStringArray, body: PackedByteArray) -> void:
	var path := _command_path
	_command_path = ""
	if _closing or _failed:
		return
	if result == HTTPRequest.RESULT_SUCCESS and code >= 200 and code < 300:
		return
	# An already ended sortie may reject a final keyboard event still in flight.
	if path == "/api/action" and code == 409:
		_pending_controls.clear()
		return
	var value: Variant = JSON.parse_string(body.get_string_from_utf8())
	var detail := ""
	if value is Dictionary:
		detail = str(value.get("detail", ""))
	_fail("Simulator command %s failed (HTTP %d). %s" % [path, code, detail])


func _new_request() -> HTTPRequest:
	var request := HTTPRequest.new()
	request.timeout = 20.0
	request.use_threads = true
	request.max_redirects = 0
	request.body_size_limit = 2 * 1024 * 1024
	add_child(request)
	return request


func _headers() -> PackedStringArray:
	return PackedStringArray(["Authorization: Bearer " + _token, "Content-Type: application/json"])


func _url(path: String) -> String:
	return "http://127.0.0.1:%d%s" % [_port, path]


func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var value: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return value if value is Dictionary else {}


func _fail(message: String) -> void:
	if _failed:
		return
	_failed = true
	quit()
	if not session_path.is_empty():
		message += "\nSimulator log " + session_path.path_join("backend.log")
	fault.emit(message)
