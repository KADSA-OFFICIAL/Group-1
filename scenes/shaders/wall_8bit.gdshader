shader_type canvas_item;

// 8비트 도트 벽 (#172)
// 단색 폴리곤인 벽에 굵은 도트 격자 + 벽돌 줄눈을 그려 레트로 질감을 준다.
// 화면이 아니라 월드 좌표 기준이라 카메라가 움직여도 무늬가 흐르지 않는다.

uniform float dot_size : hint_range(2.0, 16.0) = 6.0;    // 도트 한 칸(px)
uniform float brick_w : hint_range(12.0, 96.0) = 36.0;   // 벽돌 가로
uniform float brick_h : hint_range(6.0, 48.0) = 18.0;    // 벽돌 세로
uniform float mortar : hint_range(0.3, 1.0) = 0.62;      // 줄눈 밝기 배수
uniform float shade_jitter : hint_range(0.0, 0.4) = 0.12; // 벽돌별 명암 편차
uniform float levels : hint_range(2.0, 12.0) = 5.0;      // 색 단계

varying vec2 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

float hash21(vec2 p) {
	return fract(sin(dot(p, vec2(41.3, 289.1))) * 43758.5453);
}

void fragment() {
	// 1) 월드 좌표를 도트 격자에 스냅 — 모든 무늬가 도트 단위로 끊긴다
	vec2 p = floor(world_pos / dot_size) * dot_size;

	// 2) 벽돌 배치: 홀수 줄은 반 칸 어긋나게
	float row = floor(p.y / brick_h);
	float offset = mod(row, 2.0) * brick_w * 0.5;
	vec2 cell = vec2(floor((p.x + offset) / brick_w), row);
	vec2 inside = vec2(mod(p.x + offset, brick_w), mod(p.y, brick_h));

	// 3) 줄눈: 벽돌 경계 한 도트를 어둡게
	float is_mortar = step(inside.x, dot_size - 0.5) + step(inside.y, dot_size - 0.5);
	is_mortar = clamp(is_mortar, 0.0, 1.0);

	// 4) 벽돌마다 살짝 다른 명암
	float jitter = (hash21(cell) - 0.5) * 2.0 * shade_jitter;

	vec3 base = COLOR.rgb * (1.0 + jitter);
	base = mix(base, COLOR.rgb * mortar, is_mortar);

	// 5) 색 단계 축소로 8비트 팔레트 느낌
	base = floor(base * levels + 0.5) / levels;

	COLOR = vec4(clamp(base, 0.0, 1.0), COLOR.a);
}
