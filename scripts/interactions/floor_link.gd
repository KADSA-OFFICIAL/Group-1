extends Area2D

## 계단이 아닌 곳에서 다른 층으로 넘어간다(#406) — 지금은 미술실 준비실 창문뿐이다.
##
## **`exit_door.gd`를 쓰지 않는 이유**: 저쪽은 탈출구라 엔딩 판정을 하고
## (`ending_kind`·`clue_score`를 `SceneTree` 메타에 싣고) 음악을 끄고 탈출음을
## 낸다. 도입부에서 3층으로 내려가는 것은 탈출이 아니라 **진행**이다.
##
## 층 전환은 `floor_manager.travel_to()`(#356)가 한다. 계단 트리거와 같은
## 페이드를 타므로 화면 전환이 계단과 똑같이 보인다.

## 이 아이템이 있어야 넘어갈 수 있다. 비우면 조건 없이 열린다.
@export var required_item_id: String = ""
@export_multiline var locked_message: String = "아직 갈 수 없다."
@export var prompt_text: String = "내려가기"
## 넘어가기 직전에 한 줄 띄운다. 층이 바뀌어도 HUD는 그대로라 알림이 살아남는다.
@export_multiline var message: String = ""
## 도착할 층. 음수면 아무것도 하지 않는다.
@export var target_floor: int = -1
## 도착 지점. `Vector2.INF`면 그 층의 기본 자리로 간다.
@export var arrive_at: Vector2 = Vector2.INF
## 겹쳤을 때 누가 이기는가(#301). 진행에 필요한 것이라 잠긴 문과 같은 20이다.
@export var interact_priority: int = 20


func interact(_player: Node) -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")

	if game_state != null and not required_item_id.is_empty() \
			and not game_state.call("has_item", required_item_id):
		game_state.call("request_notice", locked_message)
		Sfx.play(&"door_locked")
		return

	if target_floor < 0:
		return

	# 층 관리자는 조립 씬 루트에 있고 이 노드는 층 씬 안에 있다 — 경로를 알 수
	# 없으므로 그룹으로 찾는다(`exit_door.gd`와 같은 방식).
	var manager := get_tree().get_first_node_in_group("floor_manager")
	if manager == null or not manager.has_method("travel_to"):
		return

	if game_state != null and not message.is_empty():
		game_state.call("request_notice", message)
	Sfx.play(&"stairs")
	manager.call("travel_to", target_floor, arrive_at)
