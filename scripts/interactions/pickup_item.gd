extends Area2D

## 플레이어가 닿으면 자동으로 줍는 아이템.
## pickup_id를 지정하면 획득 상태가 게임 상태에 기록되어 씬을 다시 로드해도 재생성되지 않는다.

@export var item_id: String = ""
@export_multiline var message: String = "아이템을 주웠다."
@export var pickup_id: String = ""


func _ready() -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")
	if game_state != null and not pickup_id.is_empty() and game_state.call("has_flag", pickup_id):
		queue_free()
		return

	body_entered.connect(_on_body_entered)


func _on_body_entered(body: Node) -> void:
	if not body is CharacterBody2D:
		return

	var game_state = get_tree().get_first_node_in_group("game_state")
	if game_state != null:
		if not item_id.is_empty() and not game_state.call("add_item", item_id):
			game_state.call("request_notice", "가방이 가득 차서 주울 수 없다.")
			return
		if not pickup_id.is_empty():
			game_state.call("set_flag", pickup_id)
		game_state.call("request_notice", message)

	queue_free()
