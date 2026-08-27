extends Area2D

## 운동장 정문(#513) — 플레이어가 접촉하면 E키 없이 자동으로 엔딩 씬으로 전환한다.
##
## 현관(exit_door.gd)이 운동장으로 보내기 **전에** 엔딩 판정(ending_kind)과
## exit_route를 이미 SceneTree 메타에 실어 둔다. 이 스크립트는 그 메타를
## 건드리지 않고 — 씬 전환만 담당한다.
##
## 신고 선택지(choice_prompt)도 이미 현관에서 처리됐다. 이 스크립트는
## 순수하게 "정문을 통과했다"는 순간만 잡는다.

@export_file("*.tscn") var ending_scene_path: String = "res://scenes/ui/ending.tscn"

var _triggered: bool = false


func _ready() -> void:
	body_entered.connect(_on_body_entered)


func _on_body_entered(body: Node) -> void:
	if _triggered:
		return
	# 플레이어만 처리한다(collision_mask = 0이라 충돌 레이어로 못 거르므로 그룹으로 확인).
	if not body.is_in_group("player"):
		return
	_triggered = true
	Sfx.stop_music()
	Sfx.play(&"escape")
	get_tree().change_scene_to_file(ending_scene_path)
