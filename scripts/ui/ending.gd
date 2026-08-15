extends Control

## 엔딩 컷신(#139) — 기획서의 "방과 후" 한 종류. 현관을 열고 나오면 여기로 넘어온다.
## 장면마다 자막(caption)을 바꾸고 대사를 한 글자씩 출력한다 — 표시와 진행 방식은 프롤로그(intro.gd)와
## 같은 하단 자막(scenes/ui/subtitle_dialogue.tscn)을 쓴다.
## 신고 선택지·숨은 엔딩은 러닝타임을 줄이기 위해 넣지 않는다(사용자 결정 2026-07-28).

@export_file("*.tscn") var title_scene_path: String = "res://scenes/ui/main_menu.tscn"

# 장면: caption과 lines([화자, 대사] 또는 [화자, 대사, 감정]). 화자가 빈 문자열이면 지문·독백으로
# 표시된다. 순서대로 재생하고 마지막에 타이틀로 돌아간다.
const SCENES: Array = [
	{
		"caption": "— 학교 현관 —",
		"lines": [
			["", "현관문이 열렸다. 밤공기가 차갑게 목덜미를 스쳤다."],
			["", "이설은 뒤를 돌아보지 않고 운동장을 가로질렀다."],
			["", "등 뒤의 학교는 아무 일도 없었다는 듯 조용했다."],
		],
	},
	{
		"caption": "— 다음 날 아침, 집 —",
		"lines": [
			["", "TV가 켜져 있다."],
			["TV 아나운서", "불암고등학교에서 여섯 번째 학생의 실종 신고가 접수되었습니다—"],
			["엄마", "어제 왜 그렇게 늦었어?"],
			["이설", "…아무것도 아니야."],
			["", "이설은 밥그릇만 내려다봤다."],
		],
	},
	{
		"caption": "— 등굣길, 정문 —",
		"lines": [
			["", "정문 앞에서 수위 아저씨가 낙엽을 쓸고 있었다."],
			["수위", "어, 잘 가."],
			["", "이설은 고개를 숙이고 지나쳤다."],
			["", "말해도 아무도 안 들어줄 것 같았으니까. 시우처럼."],
			["", "— 엔딩: 방과 후 —"],
		],
	},
]

const SCENE_FADE_SECONDS := 0.6
const SCENE_FADE_IN_SECONDS := 1.4

@onready var scene_caption: Label = $SceneCaption
@onready var dialogue: SubtitleDialogue = $Dialogue
@onready var fade_rect: ColorRect = $FadeRect

var scene_index: int = 0
var line_index: int = -1
var transitioning: bool = false
var finished: bool = false


func _ready() -> void:
	fade_rect.color.a = 1.0
	dialogue.apply_font(scene_caption)
	_apply_scene()

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 0.0, SCENE_FADE_SECONDS)
	tween.tween_callback(_next_line)


func _unhandled_input(event: InputEvent) -> void:
	if transitioning or finished:
		return
	if not (event.is_action_pressed("interact") or event.is_action_pressed("ui_accept")):
		return

	# 타이핑 중이면 먼저 남은 글자를 즉시 전부 표시하고, 아니면 다음 줄로
	if not dialogue.skip_typing():
		_next_line()

	get_viewport().set_input_as_handled()


func _apply_scene() -> void:
	scene_caption.text = SCENES[scene_index]["caption"]
	dialogue.clear()


func _next_line() -> void:
	line_index += 1
	var lines: Array = SCENES[scene_index]["lines"]

	if line_index >= lines.size():
		_next_scene()
		return

	var line: Array = lines[line_index]
	var emotion: String = line[2] if line.size() > 2 else ""
	dialogue.show_line(line[0], line[1], emotion)


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
	tween.tween_property(fade_rect, "color:a", 0.0, SCENE_FADE_IN_SECONDS)
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
		get_tree().change_scene_to_file(title_scene_path))
