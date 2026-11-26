shader_type spatial;
render_mode unshaded, blend_add, cull_disabled, depth_draw_never;

void fragment() {
	vec2 offset = UV * 2.0 - 1.0;
	float falloff = 1.0 - smoothstep(0.12, 1.0, length(offset));
	ALBEDO = vec3(0.51, 0.27, 0.075);
	ALPHA = 0.25 * falloff * falloff;
}
