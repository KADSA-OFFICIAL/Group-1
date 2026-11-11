extends Control

## 게임 시작 화면(타이틀). 가운데 제목·시작 버튼, 오른쪽 위 설정(#781), 오른쪽 아래 크레딧(#865).
## 시작을 누르면 화면이 검게 페이드아웃된 뒤 인트로 씬으로 넘어갑니다.

@export_file("*.tscn") var game_scene_path: String = "res://scenes/ui/intro.tscn"
@export var fade_seconds: float = 0.8

@onready var start_button: Button = $Layout/StartButton
@onready var settings_button: Button = $SettingsButton
@onready var settings_panel: Control = $SettingsPanel
@onready var credits_button: Button = $CreditsButton
@onready var credits_panel: Control = $CreditsPanel
@onready var fade_rect: ColorRect = $Fade

const GameStateScript = preload("res://scripts/game/game_state.gd")


func _ready() -> void:
	# 게임오버·엔딩에서 돌아와도 여기서 다시 튼다(#606). 이미 울리고 있으면 그대로 둔다.
	Sfx.play_theme(&"title")
	start_button.pressed.connect(_on_start_pressed)
	# 전체화면은 설정창 안의 옵션이다(#781) — 타이틀 가운데에는 시작만 남는다.
	settings_button.pressed.connect(_on_settings_pressed)
	settings_panel.closed.connect(_on_settings_closed)
	# 크레딧(#865)은 오른쪽 아래 — 설정창과 같은 방식으로 열고 닫는다.
	credits_button.pressed.connect(_on_credits_pressed)
	credits_panel.closed.connect(_on_credits_closed)
	start_button.grab_focus()


func _on_settings_pressed() -> void:
	Sfx.play(&"ui_click")
	# 설정창이 열린 동안 아래 버튼이 포커스·Enter를 받으면 "게임 시작"이 눌린다.
	_set_menu_focusable(false)
	settings_panel.open()


func _on_settings_closed() -> void:
	_set_menu_focusable(true)
	settings_button.grab_focus()


func _on_credits_pressed() -> void:
	Sfx.play(&"ui_click")
	_set_menu_focusable(false)
	credits_panel.open()


func _on_credits_closed() -> void:
	_set_menu_focusable(true)
	credits_button.grab_focus()


func _set_menu_focusable(on: bool) -> void:
	var mode := Control.FOCUS_ALL if on else Control.FOCUS_NONE
	start_button.focus_mode = mode
	settings_button.focus_mode = mode
	credits_button.focus_mode = mode


func _on_start_pressed() -> void:
	Sfx.play(&"ui_click")
	GameStateScript.clear_checkpoint()
	start_button.disabled = true
	settings_button.disabled = true
	credits_button.disabled = true
	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 1.0, fade_seconds)
	tween.tween_callback(_go_to_game)


func _go_to_game() -> void:
	get_tree().change_scene_to_file(game_scene_path)
