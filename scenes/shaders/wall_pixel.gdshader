shader_type canvas_item;

// 쯔꾸르풍 벽 (#172)
// 벽돌 무늬 대신 "입체 블록"으로 간다 — 칸마다 위·왼쪽은 밝고 아래·오른쪽은
// 어둡게 깎아 타일셋 벽면처럼 보이게 한다. 렌더 픽셀 격자에 스냅.

uniform float world_per_px : hint_range(0.5, 8.0) = 2.5;
uniform float block_px : hint_range(4.0, 32.0) = 16.0;   // 블록 한 변(픽셀 수)
uniform float shade_hi : hint_range(1.0, 2.0) = 1.35;    // 위·왼쪽 모서리
uniform float shade_lo : hint_range(0.3, 1.0) = 0.55;    // 아래·오른쪽 모서리
uniform float levels : hint_range(2.0, 8.0) = 5.0;

varying vec2 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	vec2 p = floor(world_pos / world_per_px);
	vec2 inside = mod(p, block_px);

	vec3 c = COLOR.rgb;
	// 베벨: 위/왼쪽 한 픽셀 하이라이트, 아래/오른쪽 한 픽셀 그림자
	if (inside.y < 0.5 || inside.x < 0.5) {
		c *= shade_hi;
	} else if (inside.y > block_px - 1.5 || inside.x > block_px - 1.5) {
		c *= shade_lo;
	}

	c = floor(c * levels + 0.5) / levels;
	COLOR = vec4(clamp(c, 0.0, 1.0), COLOR.a);
}
