class_name EndingResultScreen
extends Control

## 엔딩 결과 화면(#636). 엔딩 컷신(`ending.gd`)이 끝나면 이리로 온다.
##
## 게임 오버 화면("붙잡혔다", `game_over.gd`)과 같은 틀이다 — 탈출에는 그런 화면이
## 없어서 클리어하면 엔딩 이름이 자막 한 줄로 지나가고 곧장 타이틀이었다.
##
## 씬 전환은 노드 상태를 넘기지 못하므로 엔딩 종류와 점수는 static으로 받는다
## (`GameOverScreen.pending_reason`과 같은 방식). `ending.gd`가 전환 직전에 채우고,
## 여기서 읽은 뒤 **바로 비운다** — 남으면 다음 판 결과 화면이 지난 판 점수를 보인다.

static var pending_kind: StringName = &""
## [알아낸 수, 전체 수]. 비어 있으면(에디터에서 엔딩 씬만 실행) 점수 줄을 숨긴다.
static var pending_score: Array = []

## 엔딩 종류(`game_state.gd`의 ENDING_*) → 이름. 컷신 마지막 줄의 "— 엔딩: … —"와 같다.
const ENDING_NAMES := {
	&"after_school": "방과 후",
	&"adults_work": "어른들의 일",
	&"break_time": "쉬는 시간",
}
const DEFAULT_NAME := "방과 후"

const GameStateScript = preload("res://scripts/game/game_state.gd")

@export_file("*.tscn") var restart_scene_path: String = "res://scenes/main/main.tscn"
@export_file("*.tscn") var title_scene_path: String = "res://scenes/ui/main_menu.tscn"
@export var fade_seconds: float = 1.0

@onready var ending_label: Label = $Layout/EndingLabel
@onready var score_label: Label = $Layout/ScoreLabel
@onready var restart_button: Button = $Layout/Buttons/RestartButton
@onready var title_button: Button = $Layout/Buttons/TitleButton
@onready var fade_rect: ColorRect = $Fade

var leaving: bool = false


func _ready() -> void:
	ending_label.text = "엔딩 — %s" % ENDING_NAMES.get(pending_kind, DEFAULT_NAME)
	if pending_score.size() >= 2:
		score_label.text = "알아낸 것 %d / %d" % [pending_score[0], pending_score[1]]
	else:
		score_label.visible = false
	pending_kind = &""
	pending_score = []

	restart_button.pressed.connect(_on_restart_pressed)
	title_button.pressed.connect(_on_title_pressed)
	# 마우스를 올린 버튼이 포커스를 가져간다 — 메뉴 버튼 테마는 포커스를 밝히고
	# 양옆에 선을 긋는데, 안 그러면 키보드로 고른 것과 마우스 아래 것이 둘 다 밝다.
	for b in [restart_button, title_button]:
		b.mouse_entered.connect(b.grab_focus)

	fade_rect.color.a = 1.0
	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 0.0, fade_seconds)
	tween.tween_callback(title_button.grab_focus)


func _on_restart_pressed() -> void:
	# 처음부터 — 체크포인트가 남으면 다음 게임 오버에서 지난 판 층으로 재시도가 뜬다.
	GameStateScript.clear_checkpoint()
	_leave(restart_scene_path)


func _on_title_pressed() -> void:
	_leave(title_scene_path)


func _leave(scene_path: String) -> void:
	if leaving:
		return
	leaving = true

	Sfx.play(&"ui_click")
	restart_button.disabled = true
	title_button.disabled = true

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 1.0, fade_seconds)
	tween.tween_callback(func() -> void:
		get_tree().change_scene_to_file(scene_path))
