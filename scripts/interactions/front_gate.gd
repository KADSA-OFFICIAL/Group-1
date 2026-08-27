extends Area2D

## 운동장 정문(#513, #520) — 플레이어가 접촉하면 E키 없이 자동으로 엔딩 씬으로 전환한다.
##
## 현관(exit_door.gd)이 운동장으로 보내기 **전에** 엔딩 판정(ending_kind)과
## exit_route를 이미 SceneTree 메타에 실어 둔다. 이 스크립트는 그 메타를
## 건드리지 않고 — 씬 전환만 담당한다.

@export_file("*.tscn") var ending_scene_path: String = "res://scenes/ui/ending.tscn"

var _triggered: bool = false


func _ready() -> void:
	body_entered.connect(_on_body_entered)
	area_entered.connect(_on_area_entered)


func _on_body_entered(body: Node) -> void:
	if _triggered:
		return
	if body.is_in_group("player") or body.name == "Player" or (body.get_parent() != null and body.get_parent().name == "Player"):
		_trigger_escape()


func _on_area_entered(area: Area2D) -> void:
	if _triggered:
		return
	if area.name == "InteractionArea" or (area.get_parent() != null and area.get_parent().is_in_group("player")):
		_trigger_escape()


func _trigger_escape() -> void:
	_triggered = true
	Sfx.stop_music()
	Sfx.play(&"escape")
	get_tree().change_scene_to_file(ending_scene_path)
