extends Control
## 설정창(#781). 타이틀 오른쪽 위 "설정" 버튼이 연다.
##
## 지금 옵션은 전체화면 하나다. 켜짐/꺼짐은 `DisplayMode`(#778)가 쥐고 있고 이 창은
## 그것을 부르고 글자만 맞춘다 — F11·창 테두리 단추로 바꿔도 글자가 따라오도록
## `changed`를 받고, 열 때도 한 번 다시 읽는다(테두리 단추는 신호가 없다).
##
## 열려 있는 동안 키보드 포커스는 이 창의 버튼 둘 사이만 돈다. 아래 화면의 버튼으로
## 새면 Enter가 "게임 시작"을 눌러 버린다(방향키는 기하상 가장 가까운 버튼을 고른다).
## 아래 화면의 포커스·클릭 차단은 여는 쪽이 맡는다(`main_menu.gd`).

## 닫힐 때 쏜다 — 연 쪽이 포커스를 되돌려 받는다.
signal closed

@onready var _fullscreen_toggle: Button = %FullscreenToggle
@onready var _close_button: Button = %CloseButton

var is_open: bool = false


func _ready() -> void:
	visible = false
	_fullscreen_toggle.pressed.connect(_on_fullscreen_pressed)
	_close_button.pressed.connect(close)
	DisplayMode.changed.connect(_on_display_changed)
	_sync_fullscreen_text()
	# 두 버튼이 서로를 위·아래 이웃으로 삼아 돌고, 좌우로는 못 나간다.
	var toggle_path := _fullscreen_toggle.get_path()
	var close_path := _close_button.get_path()
	_fullscreen_toggle.focus_neighbor_top = close_path
	_fullscreen_toggle.focus_neighbor_bottom = close_path
	_close_button.focus_neighbor_top = toggle_path
	_close_button.focus_neighbor_bottom = toggle_path
	for b: Button in [_fullscreen_toggle, _close_button]:
		b.focus_neighbor_left = b.get_path()
		b.focus_neighbor_right = b.get_path()
		# 마우스를 올린 버튼이 포커스를 가져간다 — 포커스가 곧 붉은 선이라 안 그러면
		# 키보드로 고른 것과 마우스 아래 것이 둘 다 붉다(pause_menu.gd와 같은 이유).
		b.mouse_entered.connect(b.grab_focus)


func _unhandled_input(event: InputEvent) -> void:
	if is_open and event.is_action_pressed("ui_cancel"):
		close()
		get_viewport().set_input_as_handled()


func open() -> void:
	if is_open:
		return
	is_open = true
	visible = true
	_sync_fullscreen_text()
	_fullscreen_toggle.grab_focus()


func close() -> void:
	if not is_open:
		return
	is_open = false
	visible = false
	Sfx.play(&"ui_click")
	closed.emit()


func _on_fullscreen_pressed() -> void:
	Sfx.play(&"ui_click")
	DisplayMode.toggle()


func _on_display_changed(_on: bool) -> void:
	_sync_fullscreen_text()


func _sync_fullscreen_text() -> void:
	_fullscreen_toggle.text = DisplayMode.state_text()
