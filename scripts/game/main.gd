extends Node2D

@onready var game_state: Node = $GameState
@onready var hud: CanvasLayer = $HUD


func _ready() -> void:
	if hud.has_method("set_objective"):
		hud.call("set_objective", "목표: 국어책과 현관 열쇠를 찾아 학교를 탈출하세요.")

	if game_state.has_method("request_notice"):
		game_state.call("request_notice", "E 키로 단서와 물건을 조사할 수 있습니다.")
