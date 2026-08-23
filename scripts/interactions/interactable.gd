extends Area2D

## 조사 오브젝트. E로 message를 띄우고, 필요하면 아이템·플래그를 준다.
## 플래그는 조사 기록용 — 층 씬이 재로드돼도 무엇을 봤는지 남는다.

signal interacted(player: Node)

@export_multiline var message: String = ""
@export var grants_item_id: String = ""
@export var grants_flag: String = ""
@export var required_item_id: String = ""
@export_multiline var locked_message: String = "아직 열 수 없다."
@export var prompt_text: String = "조사"
## 겹쳤을 때 누가 이기는가(#301). 단서는 기본값 그대로 두고, 분위기용 조사
## 대상은 씬에서 낮춰 준다 — 안 그러면 책상이 단서를 가로챈다.
@export var interact_priority: int = 15

## 한 번이라도 조사했는가. 상호작용 표시(#301)가 읽은 것을 흐리게 하는 데 쓴다.
var investigated: bool = false


func interact(player: Node) -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")

	if game_state != null and not required_item_id.is_empty() and not game_state.call("has_item", required_item_id):
		game_state.call("request_notice", locked_message)
		Sfx.play(&"door_locked")
		return

	if game_state != null and not grants_item_id.is_empty():
		if not game_state.call("add_item", grants_item_id):
			game_state.call("request_notice", "가방이 가득 차서 가져갈 수 없다.")
			Sfx.play(&"door_locked")
			return

	if game_state != null:
		game_state.call("set_flag", grants_flag)
		game_state.call("request_notice", message)

	# 아이템을 준 조사는 획득음, 읽기만 하는 조사는 조사음.
	Sfx.play(&"pickup" if not grants_item_id.is_empty() else &"investigate")

	investigated = true
	interacted.emit(player)
