extends Area2D

## 탈출구(현관). required_item_id 아이템이 있으면 E로 탈출해 엔딩 씬으로 전환한다.
##
## **엔딩 분기는 여기서 판정한다**(#353). 판정 자체는 `GameState.ending_kind()`가
## 플래그를 보고 하고, 이 스크립트는 그 결과를 `SceneTree` 메타에 실어 보낸다 —
## `GameState`는 씬 노드라 `change_scene_to_file()` 뒤에 사라지기 때문이다.
## 오토로드를 새로 만들지 않는 이유도 그것뿐이라서다(넘길 값이 문자열 하나다).

const CHOICE_SCENE: PackedScene = preload("res://scenes/ui/choice_prompt.tscn")

@export var required_item_id: String = "front_gate_key"
@export_multiline var locked_message: String = "현관이 굳게 잠겨 있다. 열쇠가 필요하다."
@export var prompt_text: String = "현관 열기"
@export_file("*.tscn") var ending_scene_path: String = "res://scenes/ui/ending.tscn"

## 어른 쪽 은폐를 본 플레이어에게만 묻는다. 아무것도 못 봤으면 신고할 거리가 없다.
const CHOICE_PROMPT := "이대로 나가면 아무도 모른다."
const CHOICE_REPORT := "신고한다"
const CHOICE_LEAVE := "그냥 나간다"


func interact(_player: Node) -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")

	if game_state != null and not required_item_id.is_empty() and not game_state.call("has_item", required_item_id):
		game_state.call("request_notice", locked_message)
		Sfx.play(&"door_locked")
		return

	# 전부 아는 플레이어에게 신고 여부를 다시 묻지 않는다 — 히든이 우선이다.
	if game_state != null and not game_state.call("has_full_truth") \
			and game_state.call("saw_coverup"):
		_ask(game_state)
		return

	_leave(game_state, false)


## 신고 선택지를 띄운다. 고를 때까지 게임은 멈춘다(choice_prompt.gd).
func _ask(game_state) -> void:
	var panel := CHOICE_SCENE.instantiate()
	var host: Node = get_tree().current_scene
	if host == null:
		_leave(game_state, false)
		return
	host.add_child(panel)
	panel.chosen.connect(func(index: int) -> void:
		_leave(game_state, index == 0))
	panel.call("open", CHOICE_PROMPT,
		[CHOICE_REPORT, CHOICE_LEAVE] as Array[String])


func _leave(game_state, reported: bool) -> void:
	var kind := &"after_school"
	if game_state != null:
		kind = game_state.call("ending_kind", reported)
		get_tree().set_meta("clue_score", game_state.call("clue_score"))
	get_tree().set_meta("ending_kind", kind)

	# autoload라 씬이 바뀌어도 소리는 끊기지 않는다.
	Sfx.stop_music()
	Sfx.play(&"escape")
	get_tree().change_scene_to_file(ending_scene_path)
