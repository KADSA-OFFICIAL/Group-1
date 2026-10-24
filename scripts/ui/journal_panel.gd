extends CanvasLayer
## 이설의 수첩 화면(#705). 본편에서 **J**(`journal`)로 열고 J·Esc로 닫는다.
##
## 내용과 해제 규칙은 `scripts/game/journal.gd`에 있다 — 여기는 그리기와 입력만 맡는다.
##
## **열면 게임을 통째로 멈춘다**(`get_tree().paused`). 읽는 동안 수위가 걸어와
## 붙잡으면 수첩을 안 열게 된다 — 이야기를 따라가라고 만든 것이 오히려 위험해진다.
## 일시정지 메뉴(#624)와 같은 규칙이다: 이 노드만 `PROCESS_MODE_ALWAYS`, 이미 멈춘
## 트리(현관 선택지)와 게임 오버 연출 중에는 열지 않는다.
##
## **Esc가 둘(수첩·일시정지 메뉴) 사이에서 꼬이지 않는 이유**: 수첩이 열려 있으면
## 트리가 멈춰 있고, 일시정지 메뉴의 `_can_open()`은 멈춘 트리에서 거절하면서
## 이벤트를 **먹지 않는다** — 그래서 `main.tscn`에서 어느 쪽이 먼저 받든 수첩이
## 닫고 끝난다(두 순서로 스모크를 돌려 확인했다). 반대로 일시정지 메뉴가 열려
## 있으면 이쪽 `_can_open()`이 J를 거절한다.

const Journal = preload("res://scripts/game/journal.gd")

## 새 내용이 적혔다는 알림이 떠 있는 시간(초).
@export var toast_seconds: float = 2.6
## W/S·방향키로 한 번에 넘기는 거리(px).
@export var scroll_step: float = 72.0

@onready var _root: Control = $Root
@onready var _scroll: ScrollContainer = $Root/Paper/Margin/Rows/Scroll
@onready var _text: RichTextLabel = $Root/Paper/Margin/Rows/Scroll/Text
@onready var _toast: Label = $Toast

var is_open: bool = false
## 마지막으로 알린 해제 줄 수. 이보다 늘면 "수첩에 적었다"를 띄운다.
var _seen: int = 0
var _toast_tween: Tween = null


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_root.visible = false
	_toast.modulate.a = 0.0
	# **한 프레임 기다린 뒤 기준을 잡는다.** 체크포인트 재시도는 `floor_manager`
	# (조립 씬 루트 — 자식보다 늦게 `_ready`)가 플래그를 복원하며 `clues_changed`를
	# 쏜다. 그 전에 기준을 잡으면 복원된 단서가 전부 "새 내용"으로 알려진다.
	await get_tree().process_frame
	var gs := _game_state()
	if gs == null:
		return
	_seen = Journal.unlocked_count(_flags())
	gs.connect("clues_changed", _on_clues_changed)


func _game_state() -> Node:
	return get_tree().get_first_node_in_group("game_state")


func _flags() -> Array:
	var gs := _game_state()
	return gs.get("flags") if gs != null else []


func _on_clues_changed(_found: int = 0, _total: int = 0) -> void:
	var n := Journal.unlocked_count(_flags())
	if n > _seen:
		_seen = n
		_show_toast()
	if is_open:
		_refresh()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("journal"):
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

	if event.is_action_pressed("ui_cancel"):
		close()
		get_viewport().set_input_as_handled()
		return
	var step := 0
	if event.is_action_pressed("move_up"):
		step = -1
	elif event.is_action_pressed("move_down"):
		step = 1
	if step != 0:
		_scroll.scroll_vertical += int(step * scroll_step)
	# 열린 동안은 조작키가 게임으로 새지 않게 다 먹는다(트리가 멈춰 있어도
	# `PROCESS_MODE_ALWAYS`인 다른 UI가 받을 수 있다).
	get_viewport().set_input_as_handled()


## 열 수 있는 때인가 — 일시정지 메뉴(#624)와 같은 규칙.
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
	_refresh()
	_root.visible = true
	_scroll.scroll_vertical = 0
	Sfx.play(&"ui_click")


func close() -> void:
	if not is_open:
		return
	is_open = false
	_root.visible = false
	get_tree().paused = false
	Sfx.play(&"ui_click")


func _refresh() -> void:
	_text.text = Journal.render(_flags())


func _show_toast() -> void:
	if _toast_tween != null and _toast_tween.is_valid():
		_toast_tween.kill()
	_toast.modulate.a = 1.0
	_toast_tween = create_tween()
	_toast_tween.tween_interval(toast_seconds)
	_toast_tween.tween_property(_toast, "modulate:a", 0.0, 0.6)
