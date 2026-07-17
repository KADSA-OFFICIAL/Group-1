extends Control

## 게임 시작 화면(타이틀). 게임 제목과 시작 버튼만 있는 단순 구성.
## 시작을 누르면 화면이 검게 페이드아웃된 뒤 인트로 씬으로 넘어갑니다.

@export_file("*.tscn") var game_scene_path: String = "res://scenes/ui/intro.tscn"
@export var fade_seconds: float = 0.8

@onready var start_button: Button = $Layout/StartButton
@onready var fade_rect: ColorRect = $Fade


func _ready() -> void:
	start_button.pressed.connect(_on_start_pressed)
	start_button.grab_focus()


func _on_start_pressed() -> void:
	start_button.disabled = true
	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 1.0, fade_seconds)
	tween.tween_callback(_go_to_game)


func _go_to_game() -> void:
	get_tree().change_scene_to_file(game_scene_path)
