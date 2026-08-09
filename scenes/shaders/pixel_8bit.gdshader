shader_type canvas_item;

// 8비트 도트 후처리 (#172)
// 화면을 굵은 도트로 뭉갠 뒤 채널당 색 단계를 줄이고, 4x4 오더드 디더링으로
// 그라디언트를 계단식 밴딩으로 만든다. 월드 레이어 위에만 걸고 UI는 위에 둔다.

uniform sampler2D screen_tex : hint_screen_texture, repeat_disable, filter_nearest;

// 화면 픽셀 몇 개를 한 도트로 묶을지
uniform float pixel_size : hint_range(1.0, 12.0) = 4.0;
// 채널당 색 단계 수 (작을수록 레트로)
uniform float levels : hint_range(2.0, 16.0) = 6.0;
// 디더링 세기
uniform float dither_strength : hint_range(0.0, 2.0) = 1.0;

// 4x4 Bayer 행렬. 배열 선언 대신 삼항 연쇄로 두어 파싱 호환성을 지킨다.
float bayer4x4(vec2 dot_pos) {
	vec2 c = floor(mod(dot_pos, 4.0));
	float i = c.x + c.y * 4.0;
	float m =
		i < 0.5 ? 0.0 : i < 1.5 ? 8.0 : i < 2.5 ? 2.0 : i < 3.5 ? 10.0 :
		i < 4.5 ? 12.0 : i < 5.5 ? 4.0 : i < 6.5 ? 14.0 : i < 7.5 ? 6.0 :
		i < 8.5 ? 3.0 : i < 9.5 ? 11.0 : i < 10.5 ? 1.0 : i < 11.5 ? 9.0 :
		i < 12.5 ? 15.0 : i < 13.5 ? 7.0 : i < 14.5 ? 13.0 : 5.0;
	return m / 16.0 - 0.5;
}

void fragment() {
	vec2 screen_size = vec2(textureSize(screen_tex, 0));
	vec2 block = vec2(pixel_size) / screen_size;

	// 도트 한 칸의 중심 색을 뽑아 그 칸 전체를 같은 색으로 칠한다.
	vec2 snapped = (floor(SCREEN_UV / block) + 0.5) * block;
	vec3 color = texture(screen_tex, snapped).rgb;

	// 도트 좌표 기준으로 디더 임계값을 더한 뒤 단계로 양자화
	vec2 dot_pos = floor(SCREEN_UV * screen_size / pixel_size);
	color += bayer4x4(dot_pos) * dither_strength / levels;
	color = floor(color * levels + 0.5) / levels;

	COLOR = vec4(clamp(color, 0.0, 1.0), 1.0);
}
