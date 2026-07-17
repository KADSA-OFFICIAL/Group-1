extends Area2D

## 탈출구(현관). required_item_id 아이템이 있으면 E로 탈출해 엔딩 씬으로 전환한다.

@export var required_item_id: String = "front_gate_key"
@export_multiline var locked_message: String = "현관이 굳게 잠겨 있다. 열쇠가 필요하다."
@export var prompt_text: String = "현관 열기"
@export_file("*.tscn") var ending_scene_path: String = "res://scenes/ui/ending.tscn"


func interact(_player: Node) -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")

	if game_state != null and not required_item_id.is_empty() and not game_state.call("has_item", required_item_id):
		game_state.call("request_notice", locked_message)
		return

	get_tree().change_scene_to_file(ending_scene_path)
