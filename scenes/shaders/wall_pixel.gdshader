shader_type canvas_item;

// 8비트 도트 벽 (#172)
// 저해상도 SubViewport에서 그려지므로, 무늬를 "렌더 픽셀 격자"에 스냅해야
// 뭉개지지 않고 진짜 도트 그림처럼 보인다. 단색 슬래브에 3톤 명암 + 줄눈을
// 찍어 NES 시대 벽면 느낌을 낸다.

// 렌더 픽셀 하나가 차지하는 월드 단위.
// SubViewport 400px 폭 · 카메라 가시 폭 1000월드 → 2.5
uniform float world_per_px : hint_range(0.5, 8.0) = 2.5;
uniform float brick_w : hint_range(2.0, 24.0) = 8.0;   // 벽돌 가로(픽셀 수)
uniform float brick_h : hint_range(2.0, 16.0) = 4.0;   // 벽돌 세로(픽셀 수)
uniform float shade_lo : hint_range(0.3, 1.0) = 0.6;   // 줄눈·그림자
uniform float shade_hi : hint_range(1.0, 2.0) = 1.3;   // 윗면 하이라이트
uniform float levels : hint_range(2.0, 8.0) = 4.0;     // 색 단계(팔레트 축소)

varying vec2 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	// 월드 좌표 → 렌더 픽셀 좌표(정수)
	vec2 p = floor(world_pos / world_per_px);

	// 벽돌 배치: 홀수 줄은 반 칸 어긋나게
	float row = floor(p.y / brick_h);
	float offset = mod(row, 2.0) * floor(brick_w * 0.5);
	vec2 inside = vec2(mod(p.x + offset, brick_w), mod(p.y, brick_h));

	vec3 c = COLOR.rgb;
	// 벽돌 윗줄 한 픽셀 = 밝게, 아랫줄 한 픽셀 = 줄눈 그림자
	if (inside.y < 0.5) {
		c *= shade_hi;
	} else if (inside.y > brick_h - 1.5) {
		c *= shade_lo;
	}
	// 세로 줄눈 한 픽셀
	if (inside.x < 0.5) {
		c *= shade_lo;
	}

	// 팔레트 축소 — 중간 톤이 뭉쳐 도트 그림 느낌이 강해진다
	c = floor(c * levels + 0.5) / levels;

	COLOR = vec4(clamp(c, 0.0, 1.0), COLOR.a);
}
