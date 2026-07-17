extends Area2D

## 잠긴 문. required_item_id 아이템이 있으면 E로 열 수 있다.
## 열리면 배리어(barrier_path)와 연동 노드(also_remove_paths), 이 존을 제거한다.
## door_id를 지정하면 개방 상태가 게임 상태에 기록되어 씬을 다시 로드해도 유지된다.

@export var required_item_id: String = ""
@export_multiline var locked_message: String = "문이 잠겨 있다."
@export_multiline var open_message: String = "문이 열렸다."
@export var barrier_path: NodePath
@export var prompt_text: String = "문 열기"
@export var door_id: String = ""
@export var consume_key: bool = false
@export var also_remove_paths: Array[NodePath] = []


func _ready() -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")
	if game_state != null and not door_id.is_empty() and game_state.call("has_flag", door_id):
		_open()


func interact(_player: Node) -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")

	if game_state != null and not required_item_id.is_empty() and not game_state.call("has_item", required_item_id):
		game_state.call("request_notice", locked_message)
		return

	if game_state != null:
		if consume_key and not required_item_id.is_empty():
			game_state.call("remove_item", required_item_id)
		if not door_id.is_empty():
			game_state.call("set_flag", door_id)
		game_state.call("request_notice", open_message)

	_open()


func _open() -> void:
	var barrier = get_node_or_null(barrier_path)
	if barrier != null:
		barrier.queue_free()

	for path in also_remove_paths:
		var node = get_node_or_null(path)
		if node != null:
			node.queue_free()

	queue_free()
