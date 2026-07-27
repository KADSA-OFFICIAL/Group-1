class_name EndingScene
extends Control

## 엔딩 컷신(#139) — 3종 분기. 현관에서 exit_door가 pending_ending을 채운 뒤 이 씬으로 전환한다.
##   afterschool  기본. 아무것도 들고 나오지 못했을 때
##   choice       편지/공책 보유. "신고한다 / 침묵한다" 선택지 → 어른들의 일 / 방과 후
##   recess       숨은 엔딩. 5명 흔적 + 시우 서사 전부 수집
## 대사 진행 방식은 프롤로그(intro.gd)와 같다 — 한 글자씩 출력, E/Enter로 진행.

## 씬 전환은 노드 상태를 넘기지 못하므로 엔딩 종류는 static으로 전달한다.
const ENDING_AFTERSCHOOL := "afterschool"
const ENDING_CHOICE := "choice"
const ENDING_RECESS := "recess"

static var pending_ending: String = ENDING_AFTERSCHOOL

@export_file("*.tscn") var title_scene_path: String = "res://scenes/ui/main_menu.tscn"

# 엔딩 종류 → 시작 장면 키
const START_NODES: Dictionary = {
	ENDING_AFTERSCHOOL: "escape",
	ENDING_CHOICE: "crossroad",
	ENDING_RECESS: "painting",
}
const DEFAULT_START_NODE := "escape"

# 장면 노드 형식은 intro.gd와 동일: caption, lines([화자, 대사]), next 또는 choice.
# 특수 키: @title(타이틀 복귀)
const SCRIPT_NODES: Dictionary = {
	# ── 공통 탈출 ─────────────────────────────────────────────
	"escape": {
		"caption": "— 학교 현관 —",
		"lines": [
			["", "현관문이 열렸다. 밤공기가 차갑게 목덜미를 스쳤다."],
			["", "이설은 뒤를 돌아보지 않고 운동장을 가로질렀다."],
			["", "등 뒤의 학교는 아무 일도 없었다는 듯 조용했다."],
		],
		"next": "afterschool_home",
	},

	# ── 엔딩 1: 방과 후 ───────────────────────────────────────
	"afterschool_home": {
		"caption": "— 다음 날 아침, 집 —",
		"lines": [
			["", "TV가 켜져 있다."],
			["TV 아나운서", "불암고등학교에서 여섯 번째 학생의 실종 신고가 접수되었습니다—"],
			["엄마", "어제 왜 그렇게 늦었어?"],
			["이설", "…아무것도 아니야."],
			["", "이설은 밥그릇만 내려다봤다."],
		],
		"next": "afterschool_gate",
	},
	"afterschool_gate": {
		"caption": "— 등굣길, 정문 —",
		"lines": [
			["", "정문 앞에서 수위 아저씨가 낙엽을 쓸고 있었다."],
			["수위", "어, 잘 가."],
			["", "이설은 고개를 숙이고 지나쳤다."],
			["", "말해도 아무도 안 들어줄 것 같았으니까. 시우처럼."],
			["", "— 엔딩: 방과 후 —"],
		],
		"next": "@title",
	},

	# ── 엔딩 2: 어른들의 일 (신고 선택지) ─────────────────────
	"crossroad": {
		"caption": "— 학교 현관 —",
		"lines": [
			["", "현관문이 열렸다. 밤공기가 차갑게 목덜미를 스쳤다."],
			["", "손잡이를 잡은 채로, 이설은 한 발을 내딛지 못했다."],
			["", "가방 안에 든 것들이 무겁다. 이 학교에서 가지고 나온 것들이."],
			["이설", "…지금이면, 아직 누군가한테 말할 수 있어."],
		],
		"choice": {
			"prompt": "어떻게 할까?",
			"options": [
				["신고한다", "report_call"],
				["침묵한다", "afterschool_home"],
			],
		},
	},
	"report_call": {
		"caption": "— 학교 앞, 밤 —",
		"lines": [
			["", "이설은 떨리는 손으로 번호를 눌렀다."],
			["이설", "…불암고등학교예요. 학교 안에, 지금… 없어진 애들 물건이 있어요."],
			["", "얼마 지나지 않아 경찰차 불빛이 운동장을 훑고 지나갔다."],
			["", "수위실 문이 열리고, 종태가 천천히 걸어 나왔다."],
			["수위", "…학생이었구나."],
			["", "그는 저항하지 않았다. 손전등을 바닥에 내려놓고, 두 손을 내밀었다."],
		],
		"next": "report_news",
	},
	"report_news": {
		"caption": "— 다음 날 아침, 집 —",
		"lines": [
			["TV 아나운서", "불암고등학교 시설관리사 A씨가 학생 실종 사건 혐의로 체포되었습니다—"],
			["엄마", "너도 이걸 봤어?"],
			["이설", "…응."],
			["", "이제부터는 어른들의 일이었다. 이설이 할 수 있는 건 여기까지였다."],
			["", "그 다음이 제대로 될지는, 아무도 말해 주지 않았다."],
			["", "— 엔딩: 어른들의 일 —"],
		],
		"next": "@title",
	},

	# ── 엔딩 3: 쉬는 시간 (숨은 엔딩) ─────────────────────────
	"painting": {
		"caption": "— 학교 현관 —",
		"lines": [
			["", "현관문을 열기 전에, 이설은 가방에서 사진 한 장을 꺼냈다."],
			["", "미술실 벽에 10년 동안 걸려 있던 그림. 그냥 풍경화라고 생각했었다."],
			["", "나무 그늘 아래, 붓끝으로 눌러 쓴 작은 글씨. — 도와줘."],
			["이설", "…10년 동안 아무도 못 봤구나."],
			["이설", "아니. 아무도 안 본 거야."],
		],
		"next": "recess_letter",
	},
	"recess_letter": {
		"caption": "— 며칠 뒤 —",
		"lines": [
			["", "이설은 이름을 적지 않은 봉투를 보냈다."],
			["", "상담기록 사본, 그림 사진, 공책에 적힌 이름들. 그리고 날짜 다섯 개."],
			["", "학교는 조용히 뒤집혔다. 오래 걸렸지만, 이번에는 덮이지 않았다."],
			["", "박종태는 딸의 이름을 마지막으로 한 번 말했다고 한다."],
		],
		"next": "recess_office",
	},
	"recess_office": {
		"caption": "— 새 학기, 상담실 —",
		"lines": [
			["", "새로 온 상담 선생님 책상에 액자가 하나 놓여 있다."],
			["", "미술실에 걸려 있던 그림. 구석의 글씨는 이제 잘 보인다."],
			["상담교사", "이 그림, 누가 보냈는지는 모르겠지만… 여기 걸어 두려고."],
			["", "복도에서 종이 울렸다. 문 밖이 순식간에 시끄러워진다."],
			["", "쉬는 시간이다. 누군가는 이 문을 두드릴 수 있을 것이다."],
			["", "— 엔딩: 쉬는 시간 —"],
		],
		"next": "@title",
	},
}

const SCENE_FADE_SECONDS := 0.6
const SCENE_FADE_IN_SECONDS := 1.4
const CHOICE_FADE_SECONDS := 0.4
const TYPING_SECONDS_PER_CHAR := 0.05

@onready var scene_caption: Label = $SceneCaption
@onready var name_label: Label = $DialogueBox/Margin/Rows/NameLabel
@onready var text_label: Label = $DialogueBox/Margin/Rows/TextLabel
@onready var fade_rect: ColorRect = $FadeRect
@onready var choice_panel: PanelContainer = $ChoicePanel
@onready var choice_box: VBoxContainer = $ChoicePanel/Margin/ChoiceBox
@onready var choice_prompt: Label = $ChoicePanel/Margin/ChoiceBox/ChoicePrompt

var current_node: String = DEFAULT_START_NODE
var line_index: int = -1
var transitioning: bool = false
var finished: bool = false
var choosing: bool = false
var typing: bool = false
var typing_tween: Tween


func _ready() -> void:
	current_node = START_NODES.get(pending_ending, DEFAULT_START_NODE)

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
	if target == "@title":
		_finish(title_scene_path)
		return

	transitioning = true

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 1.0, SCENE_FADE_SECONDS)
	tween.tween_callback(func() -> void:
		current_node = target
		line_index = -1
		_apply_scene())
	tween.tween_property(fade_rect, "color:a", 0.0, SCENE_FADE_IN_SECONDS)
	tween.tween_callback(func() -> void:
		transitioning = false
		_next_line())


func _finish(scene_path: String) -> void:
	if finished:
		return
	finished = true

	# 다음 런이 지난 엔딩을 물려받지 않도록 기본값으로 되돌린다.
	pending_ending = ENDING_AFTERSCHOOL

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 1.0, SCENE_FADE_SECONDS)
	tween.tween_callback(func() -> void:
		get_tree().change_scene_to_file(scene_path))
