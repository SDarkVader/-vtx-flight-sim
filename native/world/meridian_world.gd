extends Node3D
## Render the canonical world snapshot. Collision and flight remain in the solver.

const MeridianStreets = preload("res://world/meridian_streets.gd")
const TERRAIN_SHADER = preload("res://world/terrain_surface.gdshader")
const BUILDING_SHADER = preload("res://world/building_windows.gdshader")
const LAMP_POOL_SHADER = preload("res://world/lamp_pool.gdshader")
const TILE_CELLS := 80
const ROAD_STEP := 12.0
const TRAFFIC_LIMIT := 814
const LAMP_LIMIT := 1850
const BUILDING_TILE_METRES := 440.0
const STREET_KINDS := ["street", "arterial", "boulevard", "local", "lane", "express", "viaduct"]
const ROAD_COLORS := {
	"street": Color(0.14, 0.16, 0.18),
	"track": Color(0.27, 0.22, 0.17),
	"lane": Color(0.18, 0.16, 0.14),
	"taxi": Color(0.18, 0.195, 0.205),
	"boardwalk": Color(0.30, 0.235, 0.18),
	"viaduct": Color(0.18, 0.19, 0.20),
}


class Triangles:
	var points := PackedVector3Array()
	var normals := PackedVector3Array()
	var colors := PackedColorArray()

	func add(a: Vector3, b: Vector3, c: Vector3, tint: Color) -> void:
		var normal := (b - a).cross(c - a).normalized()
		if normal.length_squared() < 0.01:
			return
		points.append(a)
		points.append(c)
		points.append(b)
		for _corner in range(3):
			normals.append(normal)
			colors.append(tint)

	func quad(a: Vector3, b: Vector3, c: Vector3, d: Vector3, tint: Color) -> void:
		add(a, b, c, tint)
		add(a, c, d, tint)

	func make_mesh(material: Material) -> ArrayMesh:
		return make_surface(points, normals, colors, material)

	static func make_surface(
		vertices: PackedVector3Array, directions: PackedVector3Array, tints: PackedColorArray,
		material: Material, indices := PackedInt32Array()
	) -> ArrayMesh:
		var arrays: Array = []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = vertices
		arrays[Mesh.ARRAY_NORMAL] = directions
		arrays[Mesh.ARRAY_COLOR] = tints
		if not indices.is_empty():
			arrays[Mesh.ARRAY_INDEX] = indices
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		mesh.surface_set_material(0, material)
		return mesh


var stats: Dictionary = {}
var _heights: Array = []
var _grid := 0
var _half := 0.0
var _step := 0.0
var _lamps := PackedVector3Array()
var _traffic: Array[Dictionary] = []
var _vehicles: MultiMesh
var _last_traffic_tick := -1


static func to_scene(xyz: Array) -> Vector3:
	return Vector3(float(xyz[0]), float(xyz[2]), -float(xyz[1]))


func build(world: Dictionary) -> bool:
	if not stats.is_empty():
		return false
	var started := Time.get_ticks_msec()
	_heights = world.get("heights_m", [])
	_grid = _heights.size()
	_half = float(world.get("half_m", 0.0))
	var streets: Dictionary = world.get("vaderland", {})
	var world_sha := str(world.get("displayed_world_sha256", ""))
	if _grid < 2 or _half <= 0.0 or streets.is_empty() or world_sha.length() != 64:
		return false
	for row in _heights:
		if not row is Array or row.size() != _grid:
			return false
	_step = 2.0 * _half / float(_grid - 1)
	stats = {
		"world_id": str(world.get("id", "")),
		"world_version": str(world.get("version", "")),
		"world_sha256": world_sha,
		"terrain_samples": _grid * _grid,
		"terrain_tiles": 0,
		"road_count": 0,
		"structure_count": 0,
		"architecture_batches": 0,
		"traffic_count": 0,
		"lamp_count": 0,
		"market_lots": 0,
		"roof_pad_count": 0,
	}
	_add_environment()
	_build_terrain(world.get("runway", {}))
	_add_water(world.get("harbour", {}))
	_build_runway(world.get("runway", {}))
	_build_streets(streets.get("routes", []))
	_build_structures(world.get("obstacles", []))
	_build_market(streets.get("quarter", {}))
	_build_roof_pads(streets.get("neighbourhoods", {}).get("pads", []))
	_build_city_population()
	stats["build_ms"] = Time.get_ticks_msec() - started
	return true


func set_simulation_time(sim_seconds: float) -> void:
	if _vehicles == null or not is_finite(sim_seconds):
		return
	var tick := int(floor(sim_seconds * 15.0))
	if tick == _last_traffic_tick:
		return
	_last_traffic_tick = tick
	for index in range(_traffic.size()):
		var vehicle: Dictionary = _traffic[index]
		var a: Vector2 = vehicle["a"]
		var b: Vector2 = vehicle["b"]
		var progress := fposmod(float(vehicle["phase"]) + sim_seconds * float(vehicle["rate"]), 1.0)
		var xy := a.lerp(b, progress)
		var direction := (b - a).normalized()
		var elevation := _height_at(xy) + 0.77
		if vehicle.has("deck"):
			elevation = float(vehicle["deck"]) + 0.77
		var pose := Transform3D(
			Basis(Vector3.UP, atan2(direction.x, -direction.y)),
			Vector3(xy.x, elevation, -xy.y)
		)
		_vehicles.set_instance_transform(index, pose)


func _add_environment() -> void:
	var sky_material := ProceduralSkyMaterial.new()
	sky_material.sky_top_color = Color(0.12, 0.24, 0.43)
	sky_material.sky_horizon_color = Color(0.57, 0.46, 0.42)
	sky_material.sky_curve = 0.32
	sky_material.ground_bottom_color = Color(0.11, 0.16, 0.22)
	sky_material.ground_horizon_color = Color(0.46, 0.36, 0.33)
	sky_material.sun_angle_max = 8.6
	sky_material.sun_curve = 0.13
	var sky := Sky.new()
	sky.radiance_size = Sky.RADIANCE_SIZE_128
	sky.sky_material = sky_material
	var scene_environment := Environment.new()
	scene_environment.background_mode = Environment.BG_SKY
	scene_environment.sky = sky
	scene_environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	scene_environment.ambient_light_color = Color(0.52, 0.62, 0.84)
	scene_environment.ambient_light_energy = 0.76
	scene_environment.fog_enabled = true
	scene_environment.fog_light_color = Color(0.49, 0.48, 0.58)
	scene_environment.fog_density = 0.000095
	var environment_node := WorldEnvironment.new()
	environment_node.environment = scene_environment
	add_child(environment_node)
	var sun := DirectionalLight3D.new()
	sun.light_color = Color(1.0, 0.76, 0.56)
	sun.light_energy = 1.08
	sun.rotation_degrees = Vector3(-13.0, -64.0, 0.0)
	add_child(sun)


func _build_terrain(runway: Dictionary) -> void:
	var terrain := Node3D.new()
	terrain.name = "Surveyed terrain"
	add_child(terrain)
	var material := _paint()
	var runway_material := ShaderMaterial.new()
	runway_material.shader = TERRAIN_SHADER
	var clip := Rect2()
	if not runway.is_empty():
		var half_width := float(runway["width"]) * 0.5 + float(runway["shoulder_width"])
		clip = Rect2(float(runway["x0"]), float(runway["yc"]) - half_width,
			float(runway["x1"]) - float(runway["x0"]), half_width * 2.0)
		runway_material.set_shader_parameter("runway_bounds", Vector4(clip.position.x, clip.position.y, clip.end.x, clip.end.y))
	for row in range(0, _grid - 1, TILE_CELLS):
		for column in range(0, _grid - 1, TILE_CELLS):
			var bounds := Rect2(float(column) * _step - _half, float(row) * _step - _half,
				float(TILE_CELLS) * _step, float(TILE_CELLS) * _step)
			var chosen: Material = runway_material if bounds.intersects(clip) else material
			var tile := _terrain_tile(column, row, chosen)
			terrain.add_child(tile)
			stats["terrain_tiles"] += 1


func _terrain_tile(first_column: int, first_row: int, material: Material) -> MeshInstance3D:
	var width := mini(TILE_CELLS, _grid - 1 - first_column) + 1
	var depth := mini(TILE_CELLS, _grid - 1 - first_row) + 1
	var origin_x := float(first_column) * _step - _half
	var origin_y := float(first_row) * _step - _half
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var colors := PackedColorArray()
	var indices := PackedInt32Array()
	vertices.resize(width * depth)
	normals.resize(vertices.size())
	colors.resize(vertices.size())
	indices.resize((width - 1) * (depth - 1) * 6)
	var face := 0
	for local_y in range(depth):
		var row := first_row + local_y
		var y0 := maxi(0, row - 1)
		var y1 := mini(_grid - 1, row + 1)
		var values: Array = _heights[row]
		var before: Array = _heights[y0]
		var after: Array = _heights[y1]
		for local_x in range(width):
			var column := first_column + local_x
			var x0 := maxi(0, column - 1)
			var x1 := mini(_grid - 1, column + 1)
			var idx := local_y * width + local_x
			var height := float(values[column])
			var dx := (float(values[x1]) - float(values[x0])) / (float(x1 - x0) * _step)
			var dy := (float(after[column]) - float(before[column])) / (float(y1 - y0) * _step)
			var normal := Vector3(-dx, 1.0, dy).normalized()
			vertices[idx] = Vector3(float(local_x) * _step, height, -float(local_y) * _step)
			normals[idx] = normal
			colors[idx] = _ground_color(origin_x + vertices[idx].x, origin_y - vertices[idx].z, height, normal.y)
			if local_x == width - 1 or local_y == depth - 1:
				continue
			indices[face] = idx
			indices[face + 1] = idx + width + 1
			indices[face + 2] = idx + 1
			indices[face + 3] = idx
			indices[face + 4] = idx + width
			indices[face + 5] = idx + width + 1
			face += 6
	var tile := MeshInstance3D.new()
	tile.mesh = Triangles.make_surface(vertices, normals, colors, material, indices)
	tile.position = Vector3(origin_x, 0.0, -origin_y)
	tile.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return tile


func _ground_color(x: float, y: float, elevation: float, up: float) -> Color:
	var turf := Color(0.18, 0.26, 0.17)
	var shade := 0.88 + 0.12 * sin(x * 0.006 + cos(y * 0.004)) * cos(y * 0.008)
	var bluff := Color(0.31, 0.32, 0.32)
	if elevation < 1.1:
		return Color(0.17, 0.20, 0.19)
	if absf(x) < 3300.0 and y > 700.0 and y < 4750.0 and elevation < 130.0:
		turf = turf.lerp(Color(0.23, 0.25, 0.21), 0.55)
	var terrain := turf.lerp(bluff, clampf((1.0 - up) * 2.6 + elevation / 1850.0, 0.0, 0.9))
	terrain = terrain.lerp(Color(0.64, 0.67, 0.70), clampf((elevation - 1330.0) / 510.0, 0.0, 0.96))
	return Color(terrain.r * shade, terrain.g * shade, terrain.b * shade)


func terrain_height_at(position: Vector3) -> float:
	return _height_at(Vector2(position.x, -position.z))


func _height_at(p: Vector2) -> float:
	var u := clampf((p.x + _half) / _step, 0.0, float(_grid) - 1.000001)
	var v := clampf((p.y + _half) / _step, 0.0, float(_grid) - 1.000001)
	var col := int(u)
	var row := int(v)
	var a := u - float(col)
	var b := v - float(row)
	var first: Array = _heights[row]
	var second: Array = _heights[row + 1]
	if a > b:
		return (1.0 - a) * float(first[col]) + (a - b) * float(first[col + 1]) + b * float(second[col + 1])
	return (1.0 - b) * float(first[col]) + (b - a) * float(second[col]) + a * float(second[col + 1])


func _add_water(harbour: Dictionary) -> void:
	if not harbour.has("origin") or not harbour.has("layout"):
		return
	var origin: Array = harbour["origin"]
	var boundary := PackedVector2Array()
	for chart in harbour["layout"].get("outer", []):
		boundary.append(Vector2(float(origin[0]) + float(chart[0]), float(origin[1]) - float(chart[1])))
	var indices := Geometry2D.triangulate_polygon(boundary)
	var water := Triangles.new()
	var height := float(harbour["waterLevelM"])
	for index in range(0, indices.size(), 3):
		var a := boundary[indices[index]]
		var b := boundary[indices[index + 1]]
		var c := boundary[indices[index + 2]]
		if (b - a).cross(c - a) < 0.0:
			var swap := b
			b = c
			c = swap
		water.add(_road_point(a, height, 0.0), _road_point(b, height, 0.0),
			_road_point(c, height, 0.0), Color(0.085, 0.18, 0.24))
	var material := _paint()
	material.metallic = 0.2
	material.roughness = 0.23
	_attach(water, "Coastal water", material)


func _build_runway(runway: Dictionary) -> void:
	if runway.is_empty():
		return
	var start := float(runway["x0"])
	var end := float(runway["x1"])
	var centre := float(runway["yc"])
	var half_width := float(runway["width"]) * 0.5
	var shoulder := float(runway["shoulder_width"])
	var height := float(runway["elevation_m"]) + 0.009
	var slab := Triangles.new()
	_add_strip(slab, Vector2(start, centre), Vector2(end, centre), (half_width + shoulder) * 2.0, Color(0.24, 0.26, 0.27), height)
	_add_strip(slab, Vector2(start, centre), Vector2(end, centre), half_width * 2.0, Color(0.16, 0.18, 0.20), height + 0.013)
	var markings := Color(0.87, 0.89, 0.85)
	for x in range(int(start + 35.0), int(end - 75.0), 60):
		_add_strip(slab, Vector2(float(x), centre), Vector2(float(x) + 31.0, centre), 0.62, markings, height + 0.026)
	for side in [-1.0, 1.0]:
		var edge := centre + float(side) * (half_width - 0.6)
		_add_strip(slab, Vector2(start + 2.0, edge), Vector2(end - 2.0, edge), 0.30, markings, height + 0.024)
		for x in range(int(start + 10.0), int(end - 5.0), 36):
			_lamps.append(Vector3(float(x), height + 0.18, -(centre + float(side) * (half_width + 0.6))))
	_attach(slab, "Runway 08-26", _paint())


func _street_points(route: Dictionary) -> PackedVector2Array:
	var points := PackedVector2Array()
	for item in route.get("points", []):
		points.append(Vector2(float(item[0]), float(item[1])))
	return points


func _build_streets(routes: Array) -> void:
	var surveyed: Array[Dictionary] = []
	for route in routes:
		var name := str(route.get("name", ""))
		if name.begins_with("North street ") and name.trim_prefix("North street ").is_valid_int():
			continue
		if name.begins_with("Terrace ") and name.trim_prefix("Terrace ").is_valid_int():
			continue
		surveyed.append(route)
	for route in MeridianStreets.ROUTES:
		surveyed.append(route)
	var roads := Triangles.new()
	var median_tint := Color(0.46, 0.43, 0.35)
	for road in surveyed:
		var kind := str(road.get("kind", ""))
		if kind in ["tunnel", "indoor", "vertical-loop"]:
			continue
		var width := float(road.get("width_m", 0.0))
		if width <= 0.0:
			continue
		var points := _street_points(road)
		if points.size() < 2:
			continue
		var tint: Color = ROAD_COLORS.get(kind, Color(0.16, 0.18, 0.20))
		var elevated := road.has("deck_z_m")
		var level := float(road.get("deck_z_m", 0.0)) + 0.24 if elevated else INF
		var urban := kind in STREET_KINDS
		var phase := 0.0
		var next_lamp := 8.0
		var next_mark := 0.0
		for segment in range(points.size() - 1):
			var a := points[segment]
			var b := points[segment + 1]
			var length := a.distance_to(b)
			if length < 0.10:
				continue
			var pieces := 1 if elevated else maxi(1, int(ceilf(length / ROAD_STEP)))
			for part in range(pieces):
				var start := a.lerp(b, float(part) / float(pieces))
				var end := a.lerp(b, float(part + 1) / float(pieces))
				_add_strip(roads, start, end, width, tint, level)
			if urban and width >= 12.0:
				var ortho := Vector2(-(b.y - a.y), b.x - a.x).normalized()
				while next_mark <= phase + length:
					var mark_start := a.lerp(b, (next_mark - phase) / length)
					var mark_end := a.lerp(b, minf(1.0, (next_mark - phase + 4.0) / length))
					_add_strip(roads, mark_start, mark_end, 0.23, median_tint, level, 0.19)
					next_mark += 11.0
				while next_lamp <= phase + length:
					var pole := a.lerp(b, (next_lamp - phase) / length)
					var earth := float(road.get("deck_z_m", 0.0)) if elevated else _height_at(pole)
					if absf(pole.x) < 3600.0 and pole.y > 570.0 and pole.y < 4830.0 and _lamps.size() < LAMP_LIMIT:
						pole += ortho * (width * 0.52)
						_lamps.append(Vector3(pole.x, earth + 5.4, -pole.y))
					next_lamp += 42.0
				if length >= 28.0 and absf(a.x) < 3400.0 and a.y > 650.0 and a.y < 4770.0:
					_add_traffic(a, b, ortho * (width * 0.24), elevated, float(road.get("deck_z_m", 0.0)))
			phase += length
		stats["road_count"] += 1
	_attach(roads, "Surveyed streets and bridges", _paint())


func _add_strip(
	batch: Triangles, a: Vector2, b: Vector2, width: float, tint: Color, level: float,
	extra := 0.0
) -> void:
	var segment := b - a
	if segment.length_squared() < 0.0001:
		return
	var edge := Vector2(-segment.y, segment.x).normalized() * (width * 0.5)
	batch.quad(_road_point(a - edge, level, extra), _road_point(b - edge, level, extra),
		_road_point(b + edge, level, extra), _road_point(a + edge, level, extra), tint)


func _road_point(xy: Vector2, level: float, extra: float) -> Vector3:
	var elevation := _height_at(xy) + 0.17 if is_inf(level) else level
	return Vector3(xy.x, elevation + extra, -xy.y)


func _add_traffic(a: Vector2, b: Vector2, side: Vector2, elevated: bool, deck: float) -> void:
	for direction in [-1.0, 1.0]:
		if _traffic.size() >= TRAFFIC_LIMIT:
			return
		var offset := side * float(direction)
		var start := a + offset if direction > 0.0 else b + offset
		var end := b + offset if direction > 0.0 else a + offset
		var speed := 8.5 + float(_traffic.size() % 9) * 0.45
		var car: Dictionary = {"a": start, "b": end, "phase": fposmod(float(_traffic.size()) * 0.371, 1.0),
			"rate": speed / start.distance_to(end)}
		if elevated:
			car["deck"] = deck
		_traffic.append(car)


func _build_structures(obstacles: Array) -> void:
	var batches: Dictionary = {}
	var trees := PackedVector3Array()
	for obstacle in obstacles:
		var role := str(obstacle.get("role", ""))
		var entry: Array = obstacle.get("center", [])
		var limits: Array = obstacle.get("half", [])
		if entry.size() != 3 or limits.size() != 3:
			continue
		var centre := to_scene(entry)
		var half := Vector3(float(limits[0]), float(limits[2]), float(limits[1]))
		var kind := str(obstacle.get("kind", ""))
		if role == "conifer":
			if trees.size() < 1800:
				trees.append(Vector3(centre.x, centre.y - half.y, centre.z))
			continue
		if kind == "cylinder" and role == "":
			if trees.size() < 1800 and half.y >= 1.1:
				trees.append(Vector3(centre.x, centre.y - half.y, centre.z))
			continue
		if role == "deck" and kind == "cylinder":
			continue
		var key := Vector2i(floori(centre.x / BUILDING_TILE_METRES), floori(centre.z / BUILDING_TILE_METRES))
		if not batches.has(key):
			batches[key] = Triangles.new()
		var batch: Triangles = batches[key]
		var tint := _structure_color(obstacle, half)
		if kind == "mesh":
			var vertices := PackedVector3Array()
			for vertex in obstacle.get("vertices", []):
				vertices.append(centre + to_scene(vertex))
			for face in obstacle.get("faces", []):
				batch.add(vertices[int(face[0])], vertices[int(face[1])], vertices[int(face[2])], tint)
		elif kind == "box":
			_box(batch, centre, half, tint)
		elif kind == "cylinder":
			_cylinder(batch, centre, half, tint)
		else:
			continue
		stats["structure_count"] += 1
	var walls := ShaderMaterial.new()
	walls.shader = BUILDING_SHADER
	for tile in batches:
		var batch: Triangles = batches[tile]
		_attach(batch, "Surveyed buildings %s" % tile, walls)
		stats["architecture_batches"] += 1
	_add_trees(trees)


func _structure_color(obstacle: Dictionary, half: Vector3) -> Color:
	var color := Color.from_string(str(obstacle.get("color", "#40505a")), Color(0.25, 0.30, 0.33))
	var skin := str(obstacle.get("skin", ""))
	var structure := str(obstacle.get("role", "")) == "architecture"
	var enough_wall := half.x > 1.4 and half.z > 1.4 and half.y >= 2.9
	var windows := structure and enough_wall and not skin.to_lower().contains("roof")
	if skin.to_lower().contains("steel"):
		color = color.lerp(Color(0.205, 0.23, 0.25), 0.55)
	elif skin.to_lower().contains("glass"):
		color = color.lerp(Color(0.25, 0.405, 0.49), 0.64)
	elif skin.begins_with("masonry") or skin.begins_with("apartments"):
		color = color.lerp(Color(0.46, 0.35, 0.27), 0.39)
	color.a = 1.0 if windows else 0.0
	return color


func _box(batch: Triangles, centre: Vector3, extent: Vector3, tint: Color) -> void:
	var x := Vector3(extent.x, 0.0, 0.0)
	var y := Vector3(0.0, extent.y, 0.0)
	var z := Vector3(0.0, 0.0, extent.z)
	var a := centre - x - y - z
	var b := centre + x - y - z
	var c := centre + x + y - z
	var d := centre - x + y - z
	var e := centre - x - y + z
	var f := centre + x - y + z
	var g := centre + x + y + z
	var h := centre - x + y + z
	batch.quad(b, a, d, c, tint)
	batch.quad(e, f, g, h, tint)
	batch.quad(a, e, h, d, tint)
	batch.quad(f, b, c, g, tint)
	batch.quad(d, h, g, c, tint)
	batch.quad(a, b, f, e, tint)


func _cylinder(batch: Triangles, centre: Vector3, extent: Vector3, tint: Color) -> void:
	var top := centre + Vector3.UP * extent.y
	var bottom := centre - Vector3.UP * extent.y
	for index in range(10):
		var a := float(index) * TAU / 10.0
		var b := float(index + 1) * TAU / 10.0
		var left := Vector3(cos(a) * extent.x, 0.0, sin(a) * extent.z)
		var right := Vector3(cos(b) * extent.x, 0.0, sin(b) * extent.z)
		batch.quad(bottom + left, top + left, top + right, bottom + right, tint)
		batch.add(top, top + right, top + left, tint)


func _build_market(market: Dictionary) -> void:
	var pavements := Triangles.new()
	for triangle in market.get("paving", []):
		var a := Vector2(float(triangle[0][0]), float(triangle[0][1]))
		var b := Vector2(float(triangle[1][0]), float(triangle[1][1]))
		var c := Vector2(float(triangle[2][0]), float(triangle[2][1]))
		if (b - a).cross(c - a) < 0.0:
			var swap := b
			b = c
			c = swap
		pavements.add(_road_point(a, INF, -0.081), _road_point(b, INF, -0.081),
			_road_point(c, INF, -0.081), Color(0.28, 0.29, 0.30))
	_attach(pavements, "Meridian surveyed footways", _paint())
	var trees := PackedVector3Array()
	for entry in market.get("trees", []):
		var xy: Array = entry["xy"]
		trees.append(Vector3(float(xy[0]), float(entry["z"]), -float(xy[1])))
	_add_trees(trees)
	stats["market_lots"] = market.get("lots", []).size()


func _build_roof_pads(pads: Array) -> void:
	var surfaces := Triangles.new()
	for pad in pads:
		var centre: Vector3 = to_scene(pad["center"])
		centre.y += 0.09
		var radius := float(pad["radius_m"])
		var rim := Color.from_string(str(pad.get("colour", "#76daf0")), Color(0.42, 0.64, 0.73))
		for index in range(20):
			var a := float(index) * TAU / 20.0
			var b := float(index + 1) * TAU / 20.0
			var p := Vector3(cos(a), 0.0, sin(a))
			var q := Vector3(cos(b), 0.0, sin(b))
			surfaces.quad(centre + q * radius, centre + p * radius, centre + p * (radius - 0.34),
				centre + q * (radius - 0.34), rim)
		stats["roof_pad_count"] += 1
	_attach(surfaces, "Rooftop landing rings", _paint())


func _add_trees(positions: PackedVector3Array) -> void:
	if positions.is_empty():
		return
	var tree := CylinderMesh.new()
	tree.top_radius = 0.0
	tree.bottom_radius = 1.0
	tree.height = 2.0
	tree.radial_segments = 5
	tree.rings = 0
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.15, 0.23, 0.18)
	material.roughness = 0.96
	tree.material = material
	var batch := _new_instances(tree, positions.size(), "Conifer and canopy silhouettes")
	for i in range(positions.size()):
		var h := 1.7 + float(i % 9) * 0.25
		var pose := Transform3D(Basis.from_scale(Vector3(h * 0.58, h, h * 0.58)),
			positions[i] + Vector3.UP * h)
		batch.set_instance_transform(i, pose)


func _build_city_population() -> void:
	if not _lamps.is_empty():
		var bulb := SphereMesh.new()
		bulb.radius = 0.30
		bulb.height = 0.60
		bulb.radial_segments = 6
		bulb.rings = 3
		var glow := StandardMaterial3D.new()
		glow.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		glow.albedo_color = Color(1.0, 0.66, 0.28)
		bulb.material = glow
		var bulbs := _new_instances(bulb, _lamps.size(), "Street and runway bulbs")
		var pool := PlaneMesh.new()
		pool.size = Vector2(9.0, 13.0)
		var lit := ShaderMaterial.new()
		lit.shader = LAMP_POOL_SHADER
		pool.material = lit
		var pools := _new_instances(pool, _lamps.size(), "Oriented street light pools")
		for index in range(_lamps.size()):
			var p := _lamps[index]
			bulbs.set_instance_transform(index, Transform3D(Basis.IDENTITY, p))
			var ground := Vector3(p.x, _height_at(Vector2(p.x, -p.z)) + 0.27, p.z)
			pools.set_instance_transform(index, Transform3D(Basis.IDENTITY, ground))
		stats["lamp_count"] = _lamps.size()
	if not _traffic.is_empty():
		var body := BoxMesh.new()
		body.size = Vector3(1.9, 1.40, 4.55)
		var paint := _paint()
		paint.albedo_color = Color(0.72, 0.77, 0.78)
		body.material = paint
		_vehicles = _new_instances(body, _traffic.size(), "Moving visual street traffic", true)
		for index in range(_traffic.size()):
			var hue := fposmod(float(index) * 0.269, 1.0)
			_vehicles.set_instance_color(index, Color.from_hsv(hue, 0.22, 0.7))
		stats["traffic_count"] = _traffic.size()
		set_simulation_time(0.0)


func _new_instances(mesh: Mesh, count: int, label: String, colors := false) -> MultiMesh:
	var multimesh := MultiMesh.new()
	multimesh.transform_format = MultiMesh.TRANSFORM_3D
	multimesh.use_colors = colors
	multimesh.mesh = mesh
	multimesh.instance_count = count
	var group := MultiMeshInstance3D.new()
	group.name = label
	group.multimesh = multimesh
	group.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(group)
	return multimesh


func _paint() -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.vertex_color_use_as_albedo = true
	material.roughness = 0.9
	return material


func _attach(batch: Triangles, label: String, material: Material) -> void:
	if batch.points.is_empty():
		return
	var instance := MeshInstance3D.new()
	instance.name = label
	instance.mesh = batch.make_mesh(material)
	instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(instance)
