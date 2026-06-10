extends Area2D

signal interacted(player: Node)

@export_multiline var message: String = ""
@export var grants_item_id: String = ""
@export var required_item_id: String = ""
@export_multiline var locked_message: String = "아직 열 수 없다."


func interact(player: Node) -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")

	if game_state != null and not required_item_id.is_empty() and not game_state.call("has_item", required_item_id):
		game_state.call("request_notice", locked_message)
		return

	if game_state != null and not grants_item_id.is_empty():
		game_state.call("add_item", grants_item_id)

	if game_state != null:
		game_state.call("request_notice", message)

	interacted.emit(player)
