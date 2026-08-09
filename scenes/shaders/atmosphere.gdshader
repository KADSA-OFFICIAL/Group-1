shader_type canvas_item;

// 현대 2D 호러 분위기 후처리 (#172)
// 도트화가 아니라 "공기"를 만든다 — 색 그레이딩(그늘은 차갑게, 빛은 따뜻하게),
// 비네트, 미세 필름 그레인, 가장자리 색수차. 월드 위·UI 아래에만 건다.

uniform sampler2D screen_tex : hint_screen_texture, repeat_disable, filter_linear;

uniform float vignette : hint_range(0.0, 1.0) = 0.55;      // 가장자리 어둡기
uniform float vignette_radius : hint_range(0.3, 1.2) = 0.78;
uniform float grain : hint_range(0.0, 0.15) = 0.035;       // 필름 그레인
uniform float aberration : hint_range(0.0, 6.0) = 1.6;     // 가장자리 색수차(px)
uniform vec3 shadow_tint : source_color = vec3(0.70, 0.80, 1.00);  // 그늘 = 푸른 기
uniform vec3 light_tint : source_color = vec3(1.06, 0.99, 0.88);   // 빛 = 노란 기
uniform float lift : hint_range(0.0, 0.08) = 0.012;        // 완전 검정을 살짝 들어올림

void fragment() {
	vec2 uv = SCREEN_UV;
	vec2 off = uv - vec2(0.5);
	float d = length(off);

	// 색수차: 중심은 멀쩡하고 가장자리로 갈수록 RGB가 어긋난다
	vec2 shift = normalize(off + vec2(1e-6)) * SCREEN_PIXEL_SIZE * aberration * d * 2.0;
	vec3 c;
	c.r = texture(screen_tex, uv + shift).r;
	c.g = texture(screen_tex, uv).g;
	c.b = texture(screen_tex, uv - shift).b;

	// 그레이딩: 어두운 픽셀은 차갑게, 밝은 픽셀은 따뜻하게
	float lum = dot(c, vec3(0.299, 0.587, 0.114));
	c *= mix(shadow_tint, light_tint, smoothstep(0.04, 0.45, lum));

	// 비네트
	float v = smoothstep(vignette_radius, 0.22, d);
	c *= mix(1.0 - vignette, 1.0, v);

	// 필름 그레인 (시간에 따라 흔들리게)
	float n = fract(sin(dot(uv * vec2(1031.0, 771.0) + fract(TIME * 0.7),
		vec2(12.9898, 78.233))) * 43758.5453);
	c += (n - 0.5) * grain;

	// 순수 검정에 살짝 색을 남겨 "먹칠"이 아니라 어둠으로 보이게
	c = max(c, shadow_tint * lift);

	COLOR = vec4(clamp(c, 0.0, 1.0), 1.0);
}
