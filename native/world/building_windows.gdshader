shader_type spatial;

varying vec3 site;
varying vec3 wall_normal;

void vertex() {
	site = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wall_normal = normalize(MODEL_NORMAL_MATRIX * NORMAL);
}

void fragment() {
	ALBEDO = COLOR.rgb;
	ROUGHNESS = 0.82;
	float wall = step(abs(wall_normal.y), 0.32) * step(0.6, COLOR.a);
	float longitude = abs(wall_normal.x) > abs(wall_normal.z) ? site.z : site.x;
	vec2 cells = vec2(longitude / 3.4, site.y / 3.25);
	vec2 pixel = fract(cells);
	vec2 smoothness = min(fwidth(cells), vec2(0.28));
	vec2 opening = smoothstep(vec2(0.18, 0.36) - smoothness, vec2(0.18, 0.36) + smoothness, pixel)
		* (1.0 - smoothstep(vec2(0.82, 0.86) - smoothness, vec2(0.82, 0.86) + smoothness, pixel));
	float occupied = step(0.61, fract(sin(dot(floor(cells) + floor(site.xz / 17.0), vec2(13.37, 41.81))) * 43758.5453));
	float intensity = wall * opening.x * opening.y * occupied;
	float narrow = 1.0 - smoothstep(0.1, 0.28, max(smoothness.x, smoothness.y));
	EMISSION = vec3(0.75, 0.39, 0.15) * intensity * narrow * 1.15;
	ALBEDO *= 1.0 - 0.24 * wall * opening.x * opening.y;
}
