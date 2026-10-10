extends Button
## 메뉴 버튼(#624) — 상자 없이 글자만 두고, 고른 버튼 양옆에 붉은 선을 긋는다.
##
## 판·테두리는 테마(`menu_button_theme.tres`)가 전부 비워 두고 글자 색만 바꾼다.
## 선은 스타일박스로 못 낸다(글자 폭에 맞춰야 한다) — Button이 자기 글자를 그린
## **뒤에** `_draw`가 불리므로 여기서 얹는다. 포커스가 바뀌면 Control이 알아서
## 다시 그린다.

@export var line_color: Color = Color(0.72, 0.1, 0.09)
## 글자 끝에서 선이 시작하기까지의 틈(px).
@export var line_gap: float = 18.0
## 선 길이(px). 끝에 마름모가 붙는다.
@export var line_length: float = 56.0
const DIAMOND := 5.0


func _draw() -> void:
	if not has_focus():
		return
	var font := get_theme_font("font")
	var font_size := get_theme_font_size("font_size")
	var text_w := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	var cx := size.x * 0.5
	var cy := roundf(size.y * 0.5)
	for side: float in [-1.0, 1.0]:
		var inner := cx + side * (text_w * 0.5 + line_gap)
		var outer := inner + side * line_length
		draw_line(Vector2(inner, cy), Vector2(outer, cy), line_color, 2.0)
		var d := Vector2(outer + side * DIAMOND, cy)
		draw_colored_polygon(PackedVector2Array([
			d + Vector2(0, -DIAMOND), d + Vector2(DIAMOND, 0),
			d + Vector2(0, DIAMOND), d + Vector2(-DIAMOND, 0)]), line_color)
