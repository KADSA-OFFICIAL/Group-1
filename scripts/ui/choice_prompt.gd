extends Control
## 두 갈래 선택 패널(#353) — 현관에서 "신고할까"를 묻는다.
##
## 본편에서 플레이어가 **말로 고르는 유일한 자리**다. 그래서 대화 자막
## (`subtitle_dialogue.tscn`)을 쓰지 않는다 — 저쪽은 한 줄씩 흘려보내는 장치라
## 커서를 올렸다 내렸다 할 수 없다.
##
## **게임을 멈춘다.** 안 그러면 고르는 동안 수위가 걸어와 붙잡는다. 이 노드만
## `PROCESS_MODE_ALWAYS`라 멈춘 중에도 입력을 받는다.
##
## 마우스는 쓰지 않는다 — 본편이 키보드 전용이다.

## 고른 뒤 알린다. index는 `options`의 순번.
signal chosen(index: int)

const FONT: FontFile = preload("res://assets/fonts/NotoSansKR-VF.ttf")
const PROMPT_SIZE := 26
const OPTION_SIZE := 30
const IDLE_COLOR := Color(0.62, 0.62, 0.68)
const PICKED_COLOR := Color(0.94, 0.92, 0.86)
## 커서. 고른 줄 앞에만 붙는다.
const CURSOR := "▸ "
const INDENT := "   "
## 페이드 시간(초).
const FADE_IN := 0.35

var _options: Array[String] = []
var _index: int = 0
var _locked: bool = false

## 자식 참조는 `@onready`로 잡지 않는다 — `open()`이 `add_child()` **바로 다음 줄**에서
## 불릴 수 있는데, 그 시점에 `_ready`가 아직 안 돌았으면 전부 null이다(헤드리스
## MainLoop에서 실제로 그랬다). 필요한 곳에서 그때그때 찾는다.
var _prompt: Label = null
var _list: VBoxContainer = null


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS


## 패널을 띄운다. 부모에 붙인 **뒤** 부른다.
func open(prompt: String, options: Array[String]) -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	modulate.a = 0.0
	_prompt = get_node("Box/Prompt") as Label
	_list = get_node("Box/Options") as VBoxContainer
	_options = options
	_index = 0
	_prompt.text = prompt
	_prompt.add_theme_font_override("font", _font(500.0))
	_prompt.add_theme_font_size_override("font_size", PROMPT_SIZE)

	for child in _list.get_children():
		child.queue_free()
	for text in _options:
		var label := Label.new()
		label.add_theme_font_override("font", _font(600.0))
		label.add_theme_font_size_override("font_size", OPTION_SIZE)
		_list.add_child(label)
	_paint()

	get_tree().paused = true
	var tween := create_tween()
	tween.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	tween.tween_property(self, "modulate:a", 1.0, FADE_IN)


func _font(weight: float) -> FontVariation:
	var f := FontVariation.new()
	f.base_font = FONT
	f.variation_opentype = {&"wght": weight}
	return f


func _paint() -> void:
	for i in _list.get_child_count():
		var label := _list.get_child(i) as Label
		var picked := i == _index
		label.text = (CURSOR if picked else INDENT) + _options[i]
		label.add_theme_color_override("font_color", PICKED_COLOR if picked else IDLE_COLOR)


func _unhandled_input(event: InputEvent) -> void:
	if _locked or _options.is_empty():
		return

	var step := 0
	if event.is_action_pressed("move_up") or event.is_action_pressed("ui_up"):
		step = -1
	elif event.is_action_pressed("move_down") or event.is_action_pressed("ui_down"):
		step = 1
	if step != 0:
		_index = posmod(_index + step, _options.size())
		_paint()
		Sfx.play(&"investigate")
		get_viewport().set_input_as_handled()
		return

	if event.is_action_pressed("interact") or event.is_action_pressed("ui_accept"):
		_locked = true
		get_viewport().set_input_as_handled()
		Sfx.play(&"pickup")
		# 멈춘 상태를 여기서 푼다 — 부른 쪽이 씬을 바꾸더라도 `paused`는
		# SceneTree에 남으므로 다음 씬이 통째로 멈춘 채 뜬다.
		get_tree().paused = false
		chosen.emit(_index)
		queue_free()
