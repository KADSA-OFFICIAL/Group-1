class_name GameOverScreen
extends Control

## 실패 화면(#4). 수위아저씨에게 붙잡히면 floor_manager가 이 씬으로 전환한다.
##
## **붙잡히면 죽는다**(#412). 예전에는 '수위실에 붙잡혀 있다 교무실 호출'이라
## 아무도 죽지 않았는데, 이 게임의 전제는 학생 다섯이 실종됐다는 것이다 —
## 붙잡힘이 혼나는 일이면 은신·추격·잉크통이 전부 과한 장치가 된다.
## 기본 엔딩의 TV 뉴스가 '여섯 번째 학생의 실종'을 말하는 것도 그 자리다.

## 씬 전환은 노드 상태를 넘기지 못하므로 사유는 static으로 전달한다.
## floor_manager가 change_scene_to_file 직전에 채운다.
static var pending_reason: String = "caught"

const MESSAGES := {
	"caught": "손전등이 얼굴에 닿았다. 그다음은 기억나지 않는다.\n며칠 뒤 뉴스에 여섯 번째 이름이 올랐다.\n학교는 평소처럼 문을 열었다.",
	# 미술실에서 유예를 넘긴 경우(#409). 수위가 열쇠를 들고 돌아온다.
	"artroom": "문이 열렸다. 손전등 빛이 얼굴을 정면으로 비췄다.\n이설은 그 방에서 나오지 못했다.\n다음 날 아침, 학교는 평소처럼 문을 열었다.",
}
const DEFAULT_MESSAGE := "이설은 학교에서 나오지 못했다."

@export_file("*.tscn") var retry_scene_path: String = "res://scenes/main/main.tscn"
@export_file("*.tscn") var title_scene_path: String = "res://scenes/ui/main_menu.tscn"
@export var fade_seconds: float = 1.0

@onready var message_label: Label = $Layout/MessageLabel
@onready var hint_label: Label = $Layout/HintLabel
@onready var retry_button: Button = $Layout/Buttons/RetryButton
@onready var restart_button: Button = $Layout/Buttons/RestartButton
@onready var title_button: Button = $Layout/Buttons/TitleButton
@onready var fade_rect: ColorRect = $Fade

const GameStateScript = preload("res://scripts/game/game_state.gd")

var leaving: bool = false


func _ready() -> void:
	message_label.text = MESSAGES.get(pending_reason, DEFAULT_MESSAGE)

	retry_button.pressed.connect(_on_retry_pressed)
	restart_button.pressed.connect(_on_restart_pressed)
	title_button.pressed.connect(_on_title_pressed)

	if GameStateScript.has_checkpoint():
		var cp := GameStateScript.get_checkpoint()
		var fl: int = int(cp.get("floor", 0))
		var fl_name: String = "%d층" % fl if fl > 0 else "운동장"
		retry_button.text = "%s에서 재시도" % fl_name
		restart_button.visible = true
		hint_label.text = "마지막 체크포인트: %s (소지품 및 단서 유지)" % fl_name
	else:
		retry_button.text = "다시 시작"
		restart_button.visible = false
		hint_label.text = "다시 시작하면 4층부터입니다. 모은 물건은 남지 않습니다."

	fade_rect.color.a = 1.0
	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 0.0, fade_seconds)
	tween.tween_callback(retry_button.grab_focus)


func _on_retry_pressed() -> void:
	if GameStateScript.has_checkpoint():
		GameStateScript.set_pending_restore(true)
	_leave(retry_scene_path)


func _on_restart_pressed() -> void:
	GameStateScript.clear_checkpoint()
	_leave(retry_scene_path)


func _on_title_pressed() -> void:
	_leave(title_scene_path)


func _leave(scene_path: String) -> void:
	if leaving:
		return
	leaving = true

	Sfx.play(&"ui_click")
	retry_button.disabled = true
	restart_button.disabled = true
	title_button.disabled = true

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 1.0, fade_seconds)
	tween.tween_callback(func() -> void:
		get_tree().change_scene_to_file(scene_path))
