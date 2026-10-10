extends CanvasLayer
## 인게임 일시정지 메뉴(#624). 본편(`main.tscn`)에서 **Esc**(`ui_cancel`)로 연다.
##
## **게임을 통째로 멈춘다**(`get_tree().paused`). 수위·플레이어·미술실 유예·컷신이
## 전부 서야 메뉴를 보는 동안 붙잡히지 않는다. 이 노드만 `PROCESS_MODE_ALWAYS`라
## 멈춘 중에도 입력을 받고 페이드 트윈이 돈다.
##
## 멈춤을 쓰는 곳이 하나 더 있다 — 현관 선택지(`choice_prompt.gd`). 그쪽이 이미
## 멈춰 둔 상태에서 열면 닫을 때 **선택지의 멈춤까지 풀어 버리므로** 열지 않는다.
##
## 트리가 멈춰도 **흐르는 것이 둘** 있다: `create_timer()`의 기본값
## (`process_always = true`)과 `process_frame`을 기다리는 루프다. 멈춤 중에 그것들이
## 흐르면 메뉴를 닫았을 때 연출이 건너뛰어져 있다 — 장면 대기(`art_room_intro._wait`),
## 걷기 루프(`_walk_to`·`floor_link._walk_player`), 자막 머무는 시간(`hud._hold_line`)이
## 그래서 멈춤을 따른다. 새로 대기를 쓸 때도 `create_timer(t, false)`로 쓸 것.

const GameStateScript = preload("res://scripts/game/game_state.gd")

## 처음부터 다시하기 — 게임 오버의 "처음부터 다시하기"와 같은 자리(4층 미술실).
@export_file("*.tscn") var restart_scene_path: String = "res://scenes/main/main.tscn"
@export_file("*.tscn") var title_scene_path: String = "res://scenes/ui/main_menu.tscn"
@export var fade_seconds: float = 0.5

@onready var _root: Control = $Root
@onready var _fade: ColorRect = $Fade
@onready var _resume_button: Button = $Root/Box/Buttons/ResumeButton
@onready var _restart_button: Button = $Root/Box/Buttons/RestartButton
@onready var _title_button: Button = $Root/Box/Buttons/TitleButton

var is_open: bool = false
var _leaving: bool = false


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_root.visible = false
	_fade.color.a = 0.0
	_resume_button.pressed.connect(close)
	_restart_button.pressed.connect(_on_restart_pressed)
	_title_button.pressed.connect(_on_title_pressed)
	# 마우스를 올린 버튼이 포커스를 가져간다 — 테마(menu_button_theme)가 포커스를
	# 붉게 칠하므로, 안 그러면 키보드로 고른 것과 마우스 아래 것이 둘 다 붉다.
	for b in _buttons():
		b.mouse_entered.connect(b.grab_focus)


func _unhandled_input(event: InputEvent) -> void:
	if _leaving:
		return

	if event.is_action_pressed("ui_cancel"):
		if is_open:
			close()
		elif _can_open():
			open()
		else:
			return
		get_viewport().set_input_as_handled()
		return

	if not is_open:
		return

	# 방향키·Enter는 버튼 포커스가 알아서 받는다. 본편 조작키(W/S·E)도 같은 일을
	# 하게 한다 — 손이 이미 거기 있다.
	var step := 0
	if event.is_action_pressed("move_up"):
		step = -1
	elif event.is_action_pressed("move_down"):
		step = 1
	if step != 0:
		_move_focus(step)
		get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("interact"):
		var focused := get_viewport().gui_get_focus_owner() as Button
		if focused != null and _buttons().has(focused):
			focused.pressed.emit()
		get_viewport().set_input_as_handled()


## 열 수 있는 때인가. 이미 멈춘 트리(현관 선택지)와 게임 오버 연출 중은 뺀다.
func _can_open() -> bool:
	if get_tree().paused:
		return false
	var fm := get_tree().get_first_node_in_group("floor_manager")
	if fm != null and bool(fm.get("game_over_active")):
		return false
	return true


func open() -> void:
	if is_open:
		return
	is_open = true
	get_tree().paused = true
	_root.visible = true
	Sfx.play(&"ui_click")
	_resume_button.grab_focus()


func close() -> void:
	if not is_open or _leaving:
		return
	is_open = false
	_root.visible = false
	get_tree().paused = false
	Sfx.play(&"ui_click")


func _on_restart_pressed() -> void:
	# 체크포인트를 남기면 floor_manager가 복원하지 않더라도 게임 오버 화면이
	# "N층에서 재시도"를 띄운다 — 처음부터라면 기록도 처음이어야 한다.
	GameStateScript.clear_checkpoint()
	_leave(restart_scene_path)


func _on_title_pressed() -> void:
	_leave(title_scene_path)


func _leave(scene_path: String) -> void:
	if _leaving:
		return
	_leaving = true
	for b in _buttons():
		b.disabled = true
	Sfx.play(&"ui_click")
	# 본편 음악은 `Sfx`(autoload)에 있어 씬을 바꿔도 남는다. 타이틀은 자기 테마를
	# 틀고, 재시작은 floor_manager가 다시 켠다 — 추격 상태도 같이 비운다.
	Sfx.stop_music()

	var tween := create_tween()
	tween.tween_property(_fade, "color:a", 1.0, fade_seconds)
	tween.tween_callback(func() -> void:
		# **씬을 바꾸기 전에 푼다** — `paused`는 SceneTree에 남으므로 안 풀면
		# 다음 씬이 통째로 멈춘 채 뜬다(choice_prompt.gd와 같은 이유).
		get_tree().paused = false
		get_tree().change_scene_to_file(scene_path))


func _buttons() -> Array[Button]:
	var list: Array[Button] = [_resume_button, _restart_button, _title_button]
	return list


func _move_focus(step: int) -> void:
	var list := _buttons()
	var at := list.find(get_viewport().gui_get_focus_owner() as Button)
	var next := posmod(at + step, list.size()) if at >= 0 else 0
	list[next].grab_focus()
	Sfx.play(&"investigate")
