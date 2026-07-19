extends Control

## 게임 시작 전 프롤로그 — 계획서 #1~#4-1, #12.
## 장면(집→TV→앞문→뒷문→미술실)을 진행하고, 미술실에서 분기:
## 빠져나가기(게임 시작) / 말 걸기(#4-1: 창문 도망=게임 시작, 얼어붙기=사망 엔딩).
## 대사는 하단 대화창에 한 글자씩 출력, E/Enter로 진행. 배경 이미지는 추후 추가.

@export_file("*.tscn") var game_scene_path: String = "res://scenes/main/main.tscn"
@export_file("*.tscn") var title_scene_path: String = "res://scenes/ui/main_menu.tscn"

# 장면 노드: caption, lines([화자, 대사]), 그리고 next(다음 장면 키) 또는
# choice({prompt, options: [[라벨, 다음 키]]}). 특수 키: @game(게임 시작), @title(타이틀 복귀)
const SCRIPT_NODES: Dictionary = {
	"home": {
		"caption": "— 이설의 집, 저녁 —",
		"lines": [
			["이설", "아, 낼 수행평가인데 책 놓고 왔네…"],
			["엄마", "너 또 물건 놓고 왔니?"],
			["이설", "다녀오겠습니다!"],
		],
		"next": "tv",
	},
	"tv": {
		"caption": "— 거실 TV —",
		"lines": [
			["TV 아나운서", "최근 불암고등학교에서 학생 실종 사건이 발생했습니다."],
			["TV 아나운서", "실종된 학생은 불암고등학교 2학년, 김— …지지직."],
		],
		"next": "front_gate",
	},
	"front_gate": {
		"caption": "— 밤 10시 30분, 학교 정문 —",
		"lines": [
			["이설", "…잠겼네. 이 시간엔 정문을 잠그는구나."],
			["이설", "뒷문은 열려 있으려나."],
			["", "담장을 따라 돌아가던 그때 — 운동장 구석, 피 묻은 삽을 든 거대한 형체가 무언가를 끌고 간다."],
			["이설", "……?"],
		],
		"next": "back_gate",
	},
	"back_gate": {
		"caption": "— 학교 뒷문 —",
		"lines": [
			["이설", "…뭐지, 방금 그거. 잘못 본 거겠지."],
			["이설", "빨리 책만 챙겨서 나가자."],
		],
		"next": "art_room",
	},
	"art_room": {
		"caption": "— 5층 미술실 —",
		"lines": [
			["이설", "책, 여기 있다. …어?"],
			["", "창밖 — 수위 아저씨가 삽으로 무언가를 묻고 있다. 사람의 형상을 한 무언가를."],
			["", "철컥. 미술실 문이 잠겼다. 창밖 가로등이 하나씩 꺼져 간다."],
			["", "칠판 위로, 피로 쓰인 글씨가 번져 나온다."],
		],
		"next": "rules",
	},
	"rules": {
		"caption": "— 5층 미술실 —",
		"blackboard": true,
		"start_delay": 1.2,
		"lines": [
			["???", "규칙을 어긴 학생이 있군…"],
			["???", "폐기물은 처리한다…"],
			["이설", "……!"],
			["이설", "나가야 해. 지금 당장."],
		],
		"choice": {
			"prompt": "어떻게 할까?",
			"options": [
				["조용히 빠져나갈 길을 찾는다", "@game"],
				["밖에 대고 말을 걸어 본다", "talk"],
			],
		},
	},
	"talk": {
		"caption": "— 5층 미술실 —",
		"blackboard": true,
		"lines": [
			["이설", "저기요! 수위 아저씨! 문 좀 열어 주세요!"],
			["", "쿵— 쿵— 계단을 올라오는 발소리."],
			["", "콰앙! 문 너머에서 삽이 문을 내리친다!"],
		],
		"choice": {
			"prompt": "어떻게 할까?",
			"options": [
				["창문 쪽으로 도망친다", "@game"],
				["그 자리에 얼어붙는다", "death"],
			],
		},
	},
	"death": {
		"caption": "— 엔딩: 폐기물 —",
		"lines": [
			["", "문이 부서졌다. 삽이 허공을 갈랐다."],
			["수위", "…이걸로 여섯 명째인가."],
			["", "수위는 이설의 이름표를 챙겨, 어둠 속으로 사라졌다."],
		],
		"next": "@title",
	},
}
const START_NODE := "home"
const SCENE_FADE_SECONDS := 0.5
const SCENE_FADE_IN_SECONDS := 1.7  # 장면 전환 시 새 장면이 드러나는 페이드인
const CHOICE_FADE_SECONDS := 0.4    # 선택창 등장 페이드인
const TYPING_SECONDS_PER_CHAR := 0.05

@onready var scene_caption: Label = $SceneCaption
@onready var name_label: Label = $DialogueBox/Margin/Rows/NameLabel
@onready var text_label: Label = $DialogueBox/Margin/Rows/TextLabel
@onready var fade_rect: ColorRect = $FadeRect
@onready var choice_panel: PanelContainer = $ChoicePanel
@onready var choice_box: VBoxContainer = $ChoicePanel/Margin/ChoiceBox
@onready var choice_prompt: Label = $ChoicePanel/Margin/ChoiceBox/ChoicePrompt
@onready var blackboard_art: PanelContainer = $BlackboardArt

var current_node: String = START_NODE
var line_index: int = -1
var transitioning: bool = false
var finished: bool = false
var choosing: bool = false
var typing: bool = false
var typing_tween: Tween


func _ready() -> void:
	fade_rect.color.a = 1.0
	choice_panel.visible = false
	_apply_scene()

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 0.0, SCENE_FADE_SECONDS)
	tween.tween_callback(_next_line)


func _unhandled_input(event: InputEvent) -> void:
	if transitioning or finished or choosing:
		return
	if not (event.is_action_pressed("interact") or event.is_action_pressed("ui_accept")):
		return

	if typing:
		# 타이핑 중이면 남은 글자를 즉시 전부 표시
		if typing_tween != null:
			typing_tween.kill()
		text_label.visible_characters = -1
		typing = false
	else:
		_next_line()

	get_viewport().set_input_as_handled()


func _apply_scene() -> void:
	var node: Dictionary = SCRIPT_NODES[current_node]
	scene_caption.text = node["caption"]
	# 배경 칠판(규칙) 표시 여부 — 이미지 에셋이 생기면 BlackboardArt 노드만 교체
	blackboard_art.visible = node.get("blackboard", false)
	name_label.text = ""
	text_label.text = ""


func _next_line() -> void:
	line_index += 1
	var node: Dictionary = SCRIPT_NODES[current_node]
	var lines: Array = node["lines"]

	if line_index >= lines.size():
		_end_of_node(node)
		return

	name_label.text = lines[line_index][0]
	text_label.text = lines[line_index][1]

	# 타이핑 효과: 왼쪽부터 한 글자씩 출력
	text_label.visible_characters = 0
	typing = true

	var total_chars := text_label.get_total_character_count()
	if total_chars == 0:
		total_chars = text_label.text.length()

	typing_tween = create_tween()
	typing_tween.tween_property(text_label, "visible_characters", total_chars, total_chars * TYPING_SECONDS_PER_CHAR)
	typing_tween.tween_callback(func() -> void:
		typing = false)


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

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 1.0, SCENE_FADE_SECONDS)
	tween.tween_callback(func() -> void:
		get_tree().change_scene_to_file(scene_path))
