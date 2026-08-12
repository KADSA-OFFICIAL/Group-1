extends Area2D

## 은신처(사물함·청소함·샤워칸 등). E로 숨으면 수위아저씨가 추적하지 않는다(#6).
##
## 나오기는 이 스크립트가 아니라 player_controller가 처리한다. 숨은 동안에는
## 플레이어가 움직이지 않아 상호작용 영역이 그대로 남지만, 숨기 직전 방향에
## 따라 영역이 은신처에서 살짝 벗어날 수 있다. 그 경우 여기서 나오기를 맡으면
## 영원히 갇히므로, 플레이어 쪽에서 E를 먼저 받아 항상 나올 수 있게 한다.

@export var prompt_text: String = "숨기"
@export_multiline var message: String = "몸을 접어 넣고 숨을 죽였다."


func interact(player: Node) -> void:
	if player.get("is_hiding") == true:
		return

	player.call("set_hiding", true)
	Sfx.play(&"hide_in")

	var game_state = get_tree().get_first_node_in_group("game_state")
	if game_state != null:
		game_state.call("request_notice", message)
