shader_type canvas_item;

// 쯔꾸르풍 타일 바닥 (#172)
// 단색 바닥에 타일 눈금(줄눈)과 칸별 미세 명암을 찍어 "타일 깔린 실내"로 보이게 한다.
// 저해상도 SubViewport에서 그려지므로 무늬를 렌더 픽셀 격자에 스냅해야 뭉개지지 않는다.

uniform float world_per_px : hint_range(0.5, 8.0) = 2.5;  // 렌더 픽셀 1개 = 월드 단위
uniform float tile_px : hint_range(4.0, 32.0) = 16.0;     // 타일 한 변(픽셀 수)
uniform float grout : hint_range(0.5, 1.0) = 0.82;        // 줄눈 어둡기
uniform float checker : hint_range(0.0, 0.3) = 0.07;      // 체커 명암 차
uniform float levels : hint_range(2.0, 12.0) = 6.0;

varying vec2 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	vec2 p = floor(world_pos / world_per_px);   // 렌더 픽셀 좌표
	vec2 cell = floor(p / tile_px);
	vec2 inside = mod(p, tile_px);

	vec3 c = COLOR.rgb;

	// 체커: 한 칸 걸러 살짝 밝게 — 학교 리놀륨 바닥 느낌
	float alt = mod(cell.x + cell.y, 2.0);
	c *= 1.0 + (alt - 0.5) * 2.0 * checker;

	// 줄눈: 타일 경계 한 픽셀
	if (inside.x < 0.5 || inside.y < 0.5) {
		c *= grout;
	}

	c = floor(c * levels + 0.5) / levels;
	COLOR = vec4(clamp(c, 0.0, 1.0), COLOR.a);
}
