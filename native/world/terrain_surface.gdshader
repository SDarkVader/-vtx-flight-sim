shader_type spatial;

uniform vec4 runway_bounds;
varying vec2 world_en;

void vertex() {
	vec3 world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_en = vec2(world.x, -world.z);
}

void fragment() {
	if (world_en.x > runway_bounds.x && world_en.y > runway_bounds.y
		&& world_en.x < runway_bounds.z && world_en.y < runway_bounds.w) {
		discard;
	}
	ALBEDO = COLOR.rgb;
	ROUGHNESS = 0.91;
}
