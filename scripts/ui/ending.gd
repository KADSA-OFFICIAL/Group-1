extends Control

## 기본 엔딩(#10) — 탈출 후 연출. 대사를 한 글자씩 출력하고 끝나면 타이틀로 돌아간다.

@export_file("*.tscn") var title_scene_path: String = "res://scenes/ui/main_menu.tscn"

const LINES: Array = [
	["", "이설은 학교를 빠져나왔다. 밤공기가 차갑게 목덜미를 스쳤다."],
	["", "등 뒤, 어둠에 잠긴 학교에서 낮게 웅얼거리는 소리가 들려온 것 같았다."],
	["???", "다시는… 놓고 가지 마라…"],
	["", "다음 날 아침, TV 뉴스."],
	["TV 아나운서", "불암고등학교에서 또 다른 학생의 실종이 접수되었습니다—"],
	["", "— 엔딩: 방과 후 —"],
]
const FADE_SECONDS := 0.8
const TYPING_SECONDS_PER_CHAR := 0.05

@onready var name_label: Label = $DialogueBox/Margin/Rows/NameLabel
@onready var text_label: Label = $DialogueBox/Margin/Rows/TextLabel
@onready var fade_rect: ColorRect = $FadeRect

var line_index: int = -1
var finished: bool = false
var typing: bool = false
var typing_tween: Tween


func _ready() -> void:
	fade_rect.color.a = 1.0
	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 0.0, FADE_SECONDS)
	tween.tween_callback(_next_line)


func _unhandled_input(event: InputEvent) -> void:
	if finished:
		return
	if not (event.is_action_pressed("interact") or event.is_action_pressed("ui_accept")):
		return

	if typing:
		if typing_tween != null:
			typing_tween.kill()
		text_label.visible_characters = -1
		typing = false
	else:
		_next_line()

	get_viewport().set_input_as_handled()


func _next_line() -> void:
	line_index += 1
	if line_index >= LINES.size():
		_finish()
		return

	name_label.text = LINES[line_index][0]
	text_label.text = LINES[line_index][1]

	text_label.visible_characters = 0
	typing = true

	var total_chars := text_label.get_total_character_count()
	if total_chars == 0:
		total_chars = text_label.text.length()

	typing_tween = create_tween()
	typing_tween.tween_property(text_label, "visible_characters", total_chars, total_chars * TYPING_SECONDS_PER_CHAR)
	typing_tween.tween_callback(func() -> void:
		typing = false)


func _finish() -> void:
	if finished:
		return
	finished = true

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 1.0, FADE_SECONDS)
	tween.tween_callback(func() -> void:
		get_tree().change_scene_to_file(title_scene_path))
