extends Area2D

## 플레이어가 닿으면 자동으로 줍는 아이템.

@export var item_id: String = ""
@export_multiline var message: String = "아이템을 주웠다."


func _ready() -> void:
	body_entered.connect(_on_body_entered)


func _on_body_entered(body: Node) -> void:
	if not body is CharacterBody2D:
		return

	var game_state = get_tree().get_first_node_in_group("game_state")
	if game_state != null:
		if not item_id.is_empty():
			game_state.call("add_item", item_id)
		game_state.call("request_notice", message)

	queue_free()
