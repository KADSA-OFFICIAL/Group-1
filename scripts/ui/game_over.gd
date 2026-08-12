class_name GameOverScreen
extends Control

## 실패 화면(#4). 수위아저씨에게 붙잡히면 floor_manager가 이 씬으로 전환한다.

## 씬 전환은 노드 상태를 넘기지 못하므로 사유는 static으로 전달한다.
## floor_manager가 change_scene_to_file 직전에 채운다.
static var pending_reason: String = "caught"

const MESSAGES := {
	"caught": "이설은 수위실에서 아침까지 붙잡혀 있었다.\n다음 날, 야간 무단 침입으로 교무실에 호출되었다.\n이설이 본 것들은 아무에게도 말할 기회가 없었다.",
}
const DEFAULT_MESSAGE := "이설은 학교를 빠져나오지 못했다."

@export_file("*.tscn") var retry_scene_path: String = "res://scenes/main/main.tscn"
@export_file("*.tscn") var title_scene_path: String = "res://scenes/ui/main_menu.tscn"
@export var fade_seconds: float = 1.0

@onready var message_label: Label = $Layout/MessageLabel
@onready var retry_button: Button = $Layout/Buttons/RetryButton
@onready var title_button: Button = $Layout/Buttons/TitleButton
@onready var fade_rect: ColorRect = $Fade

var leaving: bool = false


func _ready() -> void:
	message_label.text = MESSAGES.get(pending_reason, DEFAULT_MESSAGE)

	retry_button.pressed.connect(_on_retry_pressed)
	title_button.pressed.connect(_on_title_pressed)

	fade_rect.color.a = 1.0
	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 0.0, fade_seconds)
	tween.tween_callback(retry_button.grab_focus)


func _on_retry_pressed() -> void:
	_leave(retry_scene_path)


func _on_title_pressed() -> void:
	_leave(title_scene_path)


func _leave(scene_path: String) -> void:
	if leaving:
		return
	leaving = true

	Sfx.play(&"ui_click")
	retry_button.disabled = true
	title_button.disabled = true

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 1.0, fade_seconds)
	tween.tween_callback(func() -> void:
		get_tree().change_scene_to_file(scene_path))
