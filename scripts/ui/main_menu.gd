extends Control

## 게임 시작 화면(타이틀). 게임 제목과 시작 버튼만 있는 단순 구성.
## 게임 본편 씬 경로는 export로 노출해 다른 진입점으로 바꾸기 쉽게 둡니다.

@export_file("*.tscn") var game_scene_path: String = "res://scenes/main/main.tscn"

@onready var start_button: Button = $Layout/StartButton


func _ready() -> void:
	start_button.pressed.connect(_on_start_pressed)
	start_button.grab_focus()


func _on_start_pressed() -> void:
	get_tree().change_scene_to_file(game_scene_path)
