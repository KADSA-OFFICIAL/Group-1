extends Control
## 도트 칸 음량 막대(#783). 설정창의 배경음악·효과음 행이 쓴다.
##
## 매끈한 슬라이더가 아니라 네모 칸 10개다 — 화면이 전부 도트 그림이고(#739에서
## 매끈한 벡터 도형이 전부 거절됐다) 기본 `HSlider`는 어두운 종이 톤 창에서 웹 폼처럼
## 겉돈다. 칸은 정수 좌표의 사각형이라 안티앨리어싱이 없다.
##
## **키보드**: 포커스가 있을 때 ←/→(`ui_left`/`ui_right`)가 한 칸씩 바꾸고, 그 입력을
## 여기서 먹는다 — 안 먹으면 포커스 이웃으로 넘어가 버린다. ↑/↓는 먹지 않아 옵션
## 사이를 돈다. **마우스**: 칸을 누르면 그 칸까지 채우고(끌어도 따라온다), 맨 왼쪽
## 칸이 이미 마지막이면 한 번 더 눌러 0으로 끈다.
##
## 포커스는 붉은 테두리로 알린다(메뉴 버튼의 붉은 선과 같은 색, `menu_button.gd`).

signal value_changed(value: int)

@export var max_value: int = 10
@export var block_size: Vector2i = Vector2i(18, 24)
@export var block_gap: int = 4

@export var filled_color: Color = Color(0.91, 0.86, 0.75)
@export var filled_shade: Color = Color(0.62, 0.55, 0.45)
@export var empty_color: Color = Color(0.17, 0.16, 0.14)
@export var empty_edge: Color = Color(0.30, 0.28, 0.24)
@export var focus_color: Color = Color(0.72, 0.1, 0.09)

var value: int = 0
var _dragging: bool = false


func _init() -> void:
	focus_mode = Control.FOCUS_ALL
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND


func _ready() -> void:
	custom_minimum_size = _bar_size() + Vector2(12, 12)  # 포커스 테두리 여백


## 값을 바꾸고 알린다. 코드에서 맞출 때는 `set_value_silent`.
func set_value(v: int) -> void:
	v = clampi(v, 0, max_value)
	if v == value:
		return
	value = v
	queue_redraw()
	value_changed.emit(value)


func set_value_silent(v: int) -> void:
	value = clampi(v, 0, max_value)
	queue_redraw()


func _bar_size() -> Vector2:
	return Vector2(max_value * block_size.x + (max_value - 1) * block_gap, block_size.y)


## 칸이 놓이는 왼쪽 위(포커스 테두리 여백 6px 안쪽, 세로 가운데).
func _origin() -> Vector2:
	var bar := _bar_size()
	return Vector2(roundf((size.x - bar.x) * 0.5), roundf((size.y - bar.y) * 0.5))


func _draw() -> void:
	var o := _origin()
	for i in max_value:
		var r := Rect2(o + Vector2(i * (block_size.x + block_gap), 0), Vector2(block_size))
		if i < value:
			draw_rect(r, filled_color)
			# 아랫줄을 어둡게 — 납작한 판이 아니라 두께가 보인다(집기 그림과 같은 생각).
			draw_rect(Rect2(r.position + Vector2(0, r.size.y - 4), Vector2(r.size.x, 4)), filled_shade)
		else:
			draw_rect(r, empty_edge)
			draw_rect(r.grow(-2), empty_color)
	if has_focus():
		var bar := Rect2(o, _bar_size()).grow(5)
		draw_rect(bar, focus_color, false, 2.0)


func _gui_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_left", true):
		set_value(value - 1)
		accept_event()
	elif event.is_action_pressed("ui_right", true):
		set_value(value + 1)
		accept_event()
	elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		_dragging = event.pressed
		if event.pressed:
			_set_from_x(event.position.x, true)
			accept_event()
	elif event is InputEventMouseMotion and _dragging:
		_set_from_x(event.position.x, false)
		accept_event()


func _set_from_x(x: float, allow_off: bool) -> void:
	var step := block_size.x + block_gap
	var i := clampi(int(floorf((x - _origin().x) / step)), 0, max_value - 1)
	# 맨 왼쪽 칸이 이미 마지막 칸이면 눌러서 끈다.
	if allow_off and i == 0 and value == 1:
		set_value(0)
	else:
		set_value(i + 1)


func _notification(what: int) -> void:
	if what == NOTIFICATION_FOCUS_ENTER or what == NOTIFICATION_FOCUS_EXIT:
		queue_redraw()
	elif what == NOTIFICATION_RESIZED:
		queue_redraw()
