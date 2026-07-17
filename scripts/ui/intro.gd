extends Control

## 게임 시작 전 프롤로그 — 계획서 도입부.
## 장면 1(집): 이설과 엄마의 대화 → 페이드 전환 → 장면 2(TV): 실종 사건 뉴스.
## 대사는 하단 대화창에 표시되고 E/Enter로 한 줄씩 진행한다.
## 배경 이미지는 추후 추가 예정 — 지금은 상단 장면 표기로 대신한다.

@export_file("*.tscn") var next_scene_path: String = "res://scenes/main/main.tscn"

# [화자, 대사] 목록으로 이루어진 장면들
const SCENES: Array = [
	{
		"caption": "— 이설의 집, 저녁 —",
		"lines": [
			["이설", "아, 낼 수행평가인데 책 놓고 왔네…"],
			["엄마", "너 또 물건 놓고 왔니?"],
			["이설", "다녀오겠습니다!"],
		],
	},
	{
		"caption": "— 거실 TV —",
		"lines": [
			["TV 아나운서", "최근 불암고등학교에서 학생 실종 사건이 발생했습니다."],
			["TV 아나운서", "실종된 학생은 불암고등학교 2학년, 김— …지지직."],
		],
	},
]
const SCENE_FADE_SECONDS := 0.5

@onready var scene_caption: Label = $SceneCaption
@onready var name_label: Label = $DialogueBox/Margin/Rows/NameLabel
@onready var text_label: Label = $DialogueBox/Margin/Rows/TextLabel
@onready var fade_rect: ColorRect = $FadeRect

var scene_index: int = 0
var line_index: int = -1
var transitioning: bool = false
var finished: bool = false


func _ready() -> void:
	fade_rect.color.a = 1.0
	_apply_scene()

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 0.0, SCENE_FADE_SECONDS)
	tween.tween_callback(_next_line)


func _unhandled_input(event: InputEvent) -> void:
	if transitioning or finished:
		return
	if not (event.is_action_pressed("interact") or event.is_action_pressed("ui_accept")):
		return

	_next_line()
	get_viewport().set_input_as_handled()


func _apply_scene() -> void:
	scene_caption.text = SCENES[scene_index]["caption"]
	name_label.text = ""
	text_label.text = ""


func _next_line() -> void:
	line_index += 1
	var lines: Array = SCENES[scene_index]["lines"]

	if line_index >= lines.size():
		_next_scene()
		return

	name_label.text = lines[line_index][0]
	text_label.text = lines[line_index][1]


func _next_scene() -> void:
	if scene_index + 1 >= SCENES.size():
		_finish()
		return

	transitioning = true
	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 1.0, SCENE_FADE_SECONDS)
	tween.tween_callback(func() -> void:
		scene_index += 1
		line_index = -1
		_apply_scene())
	tween.tween_property(fade_rect, "color:a", 0.0, SCENE_FADE_SECONDS)
	tween.tween_callback(func() -> void:
		transitioning = false
		_next_line())


func _finish() -> void:
	if finished:
		return
	finished = true

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 1.0, SCENE_FADE_SECONDS)
	tween.tween_callback(func() -> void:
		get_tree().change_scene_to_file(next_scene_path))
