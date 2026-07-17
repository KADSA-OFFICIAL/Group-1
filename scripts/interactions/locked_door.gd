extends Area2D

## 잠긴 문. required_item_id 아이템이 있으면 E로 열 수 있다.
## 열리면 배리어(barrier_path)와 이 상호작용 존을 제거한다.

@export var required_item_id: String = ""
@export_multiline var locked_message: String = "문이 잠겨 있다."
@export_multiline var open_message: String = "문이 열렸다."
@export var barrier_path: NodePath
@export var prompt_text: String = "문 열기"


func interact(_player: Node) -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")

	if game_state != null and not required_item_id.is_empty() and not game_state.call("has_item", required_item_id):
		game_state.call("request_notice", locked_message)
		return

	if game_state != null:
		game_state.call("request_notice", open_message)

	var barrier = get_node_or_null(barrier_path)
	if barrier != null:
		barrier.queue_free()
	queue_free()
