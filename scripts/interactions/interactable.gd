extends Area2D

## 조사 오브젝트. E로 message를 띄우고, 필요하면 아이템·플래그를 준다.
## 재조사(#140): revisit_required_flags를 모두 갖춘 뒤 다시 조사하면 revisit_message로 바뀌고
## revisit_grants_flag를 세운다 — 시우 그림처럼 "나중에 다시 보면 다르게 보이는" 단서에 쓴다.

signal interacted(player: Node)

@export_multiline var message: String = ""
@export var grants_item_id: String = ""
@export var grants_flag: String = ""
@export var required_item_id: String = ""
@export_multiline var locked_message: String = "아직 열 수 없다."
@export var prompt_text: String = "조사"
@export var revisit_required_flags: Array[String] = []
@export_multiline var revisit_message: String = ""
@export var revisit_grants_flag: String = ""


func interact(player: Node) -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")

	if game_state != null and not required_item_id.is_empty() and not game_state.call("has_item", required_item_id):
		game_state.call("request_notice", locked_message)
		return

	if game_state != null and not grants_item_id.is_empty():
		if not game_state.call("add_item", grants_item_id):
			game_state.call("request_notice", "가방이 가득 차서 가져갈 수 없다.")
			return

	if game_state != null:
		game_state.call("set_flag", grants_flag)

		if _is_revisit(game_state):
			game_state.call("set_flag", revisit_grants_flag)
			game_state.call("request_notice", revisit_message)
		else:
			game_state.call("request_notice", message)

	interacted.emit(player)


## 재조사 조건: 별도 메시지가 있고, 요구 플래그를 모두 갖췄을 때.
func _is_revisit(game_state) -> bool:
	if revisit_message.is_empty() or revisit_required_flags.is_empty():
		return false

	return game_state.call("has_all_flags", revisit_required_flags)
