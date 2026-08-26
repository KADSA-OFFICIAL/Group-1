extends Control

## 게임 시작 전 프롤로그 컷신 (기획서: street → back_gate → art_room → cabinet → next_room).
## 마지막에 창문으로 외벽을 타고 4층으로 내려가 본편(@game)이 시작된다.
## 대사는 하단 자막(scenes/ui/subtitle_dialogue.tscn)에 한 글자씩 출력, E/Enter로 진행.
## 배경 이미지는 추후 추가.
## 장면 노드는 choice(분기)도 지원한다 — 신고 선택지 등 후속 이슈에서 사용.

@export_file("*.tscn") var game_scene_path: String = "res://scenes/main/main.tscn"
@export_file("*.tscn") var title_scene_path: String = "res://scenes/ui/main_menu.tscn"

# 장면 노드: caption, lines([화자, 대사] 또는 [화자, 대사, 감정]), 그리고 next(다음 장면 키) 또는
# choice({prompt, options: [[라벨, 다음 키]]}). 특수 키: @game(게임 시작), @title(타이틀 복귀)
# 화자가 빈 문자열이면 지문·독백으로 표시된다. 감정 태그는 subtitle_dialogue.gd의 EMOTIONS 참고.
const SCRIPT_NODES: Dictionary = {
	"street": {
		"caption": "— 밤 10시 20분, 학원에서 집으로 —",
		"lines": [
			["", "가방이 가볍다. 이설은 걸음을 멈췄다."],
			["이설", "…국어책."],
			["이설", "아, 미술실에 두고 왔네. 내일 수행평가인데."],
			["", "학교까지는 10분. 뒷문은 늦게까지 열려 있다고 들었다."],
			["이설", "책만 챙겨서 바로 나오면 되지."],
		],
		"next": "back_gate",
	},
	"back_gate": {
		"caption": "— 학교 뒷문 —",
		"lines": [
			["", "뒷문을 밀어 본다. 끼익 — 열렸다."],
			["이설", "역시 안 잠겨 있네."],
			["", "복도 전등은 모두 꺼져 있다. 이설은 핸드폰 손전등을 켰다."],
			["", "빛이 닿는 곳만 세상이고, 그 밖은 아무것도 없다."],
			["이설", "5층까지만. 빨리 다녀오자."],
		],
		"next": "art_room",
	},
	"art_room": {
		"caption": "— 5층 미술실 —",
		"lines": [
			["", "미술실 문은 열려 있었다. 책상 위, 국어책이 그대로 놓여 있다."],
			["이설", "찾았다."],
			["", "그때 복도에서 발소리가 들렸다. 열쇠 꾸러미가 부딪히는 소리."],
			["수위", "이 문 왜 열려 있어?"],
			["", "이설은 생각할 틈도 없이 캐비넷 안으로 몸을 밀어 넣었다."],
		],
		"next": "cabinet",
	},
	"cabinet": {
		"caption": "— 미술실 캐비넷 안 —",
		"lines": [
			["", "숨을 참는다. 손전등도 껐다. 문틈으로 빛이 지나간다."],
			["", "수위는 교실을 천천히 돌았다. 이젤을, 책상을, 벽에 붙은 그림을 하나하나."],
			["수위", "시우 그림은… 괜찮고."],
			["수위", "문단속 다시 해야겠네."],
			["", "철컥. 미술실 문이 잠겼다. 발소리가 멀어진다."],
			["이설", "…잠갔어? 이제 문으로는 못 나가겠네."],
		],
		"next": "next_room",
	},
	"next_room": {
		"caption": "— 미술실 옆, 준비실 —",
		"lines": [
			["", "미술실 문은 잠겼다. 대신 옆 준비실로 통하는 연결문이 열려 있었다."],
			["", "책상 위에 비닐봉투 몇 개. 손전등을 비춰 본다."],
			["", "교복 단추, 이름표, 머리끈, 볼펜. 학생 소지품이다. 하나가 아니다. 여러 명 것이다."],
			["", "벽에는 날짜가 적혀 있었다. 3월 14일. 5월 22일. 8월 9일. 11월 3일. 1월 18일."],
			["이설", "…뉴스에서 들은 실종 시기랑 같아.", "suspicion"],
			["", "복도에서 다시 발소리. 이번엔 이쪽으로 오고 있다."],
			["이설", "(창문…!)"],
			["", "이설은 창문을 열고 외벽 난간으로 몸을 내밀었다. 발밑은 5층 높이."],
			["", "난간을 따라 옆 창문으로, 그리고 아래층으로 — 4층 교실에 발이 닿았다."],
		],
		"next": "@game",
	},
}
const START_NODE := "street"
const SCENE_FADE_SECONDS := 0.5
const SCENE_FADE_IN_SECONDS := 1.7  # 장면 전환 시 새 장면이 드러나는 페이드인
const CHOICE_FADE_SECONDS := 0.4    # 선택창 등장 페이드인

@onready var scene_caption: Label = $SceneCaption
@onready var dialogue: SubtitleDialogue = $Dialogue
@onready var fade_rect: ColorRect = $FadeRect
@onready var choice_panel: PanelContainer = $ChoicePanel
@onready var choice_box: VBoxContainer = $ChoicePanel/Margin/ChoiceBox
@onready var choice_prompt: Label = $ChoicePanel/Margin/ChoiceBox/ChoicePrompt
@onready var skip_button: Button = $SkipButton

var current_node: String = START_NODE
var line_index: int = -1
var transitioning: bool = false
var finished: bool = false
var choosing: bool = false
## 장면 전환·시작 페이드에 쓰는 트윈. 건너뛰기가 도중에 끼어들 때 죽여야
## 페이드가 서로 싸우지 않는다.
var scene_tween: Tween = null


func _ready() -> void:
	fade_rect.color.a = 1.0
	choice_panel.visible = false
	dialogue.apply_font(scene_caption)
	_apply_scene()

	# 테스트용 건너뛰기(#231) — 릴리스로 내보낸 빌드에서는 숨긴다.
	# focus_mode는 씬에서 FOCUS_NONE이다. 포커스를 받으면 대사를 넘기려고
	# 누른 Enter/Space가 버튼을 눌러 프롤로그가 통째로 날아간다.
	skip_button.visible = OS.is_debug_build()
	skip_button.pressed.connect(_on_skip_pressed)

	scene_tween = create_tween()
	scene_tween.tween_property(fade_rect, "color:a", 0.0, SCENE_FADE_SECONDS)
	scene_tween.tween_callback(_next_line)


func _unhandled_input(event: InputEvent) -> void:
	if transitioning or finished or choosing:
		return
	if not (event.is_action_pressed("interact") or event.is_action_pressed("ui_accept")):
		return

	# 타이핑 중이면 먼저 남은 글자를 즉시 전부 표시하고, 아니면 다음 줄로
	if not dialogue.skip_typing():
		_next_line()

	get_viewport().set_input_as_handled()


func _apply_scene() -> void:
	var node: Dictionary = SCRIPT_NODES[current_node]
	scene_caption.text = node["caption"]
	dialogue.clear()


func _next_line() -> void:
	line_index += 1
	var node: Dictionary = SCRIPT_NODES[current_node]
	var lines: Array = node["lines"]

	if line_index >= lines.size():
		_end_of_node(node)
		return

	var line: Array = lines[line_index]
	var emotion: String = line[2] if line.size() > 2 else ""
	dialogue.show_line(line[0], line[1], emotion)


func _end_of_node(node: Dictionary) -> void:
	if node.has("choice"):
		_show_choice(node["choice"])
	else:
		_go_to(node["next"])


func _show_choice(choice: Dictionary) -> void:
	choosing = true
	choice_prompt.text = choice["prompt"]

	# 이전 선택 버튼 정리 후 새로 생성
	for child in choice_box.get_children():
		if child is Button:
			child.queue_free()

	var first_button: Button = null
	for option in choice["options"]:
		var button := Button.new()
		button.text = option[0]
		button.custom_minimum_size = Vector2(420, 44)
		button.pressed.connect(_on_choice_selected.bind(option[1]))
		choice_box.add_child(button)
		if first_button == null:
			first_button = button

	choice_panel.modulate.a = 0.0
	choice_panel.visible = true
	var tween := create_tween()
	tween.tween_property(choice_panel, "modulate:a", 1.0, CHOICE_FADE_SECONDS)

	if first_button != null:
		first_button.grab_focus()


func _on_choice_selected(target: String) -> void:
	choice_panel.visible = false
	choosing = false
	_go_to(target)


func _go_to(target: String) -> void:
	if target == "@game":
		_finish(game_scene_path)
		return
	if target == "@title":
		_finish(title_scene_path)
		return

	transitioning = true
	# start_delay: 새 장면이 드러난 뒤 첫 대사까지 두는 시간차
	var start_delay: float = SCRIPT_NODES[target].get("start_delay", 0.0)

	var tween := create_tween()
	scene_tween = tween
	tween.tween_property(fade_rect, "color:a", 1.0, SCENE_FADE_SECONDS)
	tween.tween_callback(func() -> void:
		current_node = target
		line_index = -1
		_apply_scene())
	tween.tween_property(fade_rect, "color:a", 0.0, SCENE_FADE_IN_SECONDS)
	if start_delay > 0.0:
		tween.tween_interval(start_delay)
	tween.tween_callback(func() -> void:
		transitioning = false
		_next_line())


func _finish(scene_path: String) -> void:
	if finished:
		return
	finished = true
	# 장면 전환 도중에 건너뛰면 그 트윈이 계속 돌아 페이드를 도로 걷어낸다.
	if scene_tween != null and scene_tween.is_valid():
		scene_tween.kill()

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 1.0, SCENE_FADE_SECONDS)
	tween.tween_callback(func() -> void:
		get_tree().change_scene_to_file(scene_path))


## 프롤로그를 통째로 건너뛰고 본편으로 간다(#231).
## 마지막 장면의 @game과 같은 경로라 시작 지점·상태가 동일하다.
func _on_skip_pressed() -> void:
	if finished:
		return
	Sfx.play(&"ui_click")
	skip_button.disabled = true
	_finish(game_scene_path)
