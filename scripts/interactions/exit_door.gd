extends Area2D

## 탈출구(현관). required_item_id 아이템이 있으면 E로 탈출해 엔딩 씬으로 전환한다.
## 이때 수집한 플래그로 엔딩 종류를 판정한다(#139) — 판정 결과는 EndingScene.pending_ending으로 넘긴다.

## 숨은 엔딩("쉬는 시간") 조건: 실종 학생 5명의 흔적 + 시우 서사를 전부 모았을 때.
## 송하람 학생증은 프롤로그에서 반드시 줍고, 4층 다산실 메모가 "오해"였음을 보여 준다.
const HIDDEN_ENDING_FLAGS: Array[String] = [
	"found_kangyujin",
	"found_baekseungho",
	"found_imnayeon",
	"found_jominhyuk",
	"found_songharam",
	"read_siwoo_counseling",
	"read_janitor_notebook",
	"revisit_siwoo_painting",
]
## 신고 선택지 조건: 교장실 편지나 수위실 공책 중 하나라도 읽었을 때.
const REPORT_CHOICE_FLAGS: Array[String] = [
	"read_principal_letter",
	"read_janitor_notebook",
]

@export var required_item_id: String = "front_gate_key"
@export_multiline var locked_message: String = "현관이 굳게 잠겨 있다. 열쇠가 필요하다."
@export var prompt_text: String = "현관 열기"
@export_file("*.tscn") var ending_scene_path: String = "res://scenes/ui/ending.tscn"


func interact(_player: Node) -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")

	if game_state != null and not required_item_id.is_empty() and not game_state.call("has_item", required_item_id):
		game_state.call("request_notice", locked_message)
		return

	EndingScene.pending_ending = _decide_ending(game_state)
	get_tree().change_scene_to_file(ending_scene_path)


func _decide_ending(game_state) -> String:
	if game_state == null:
		return EndingScene.ENDING_AFTERSCHOOL

	if game_state.call("has_all_flags", HIDDEN_ENDING_FLAGS):
		return EndingScene.ENDING_RECESS

	if game_state.call("has_any_flag", REPORT_CHOICE_FLAGS):
		return EndingScene.ENDING_CHOICE

	return EndingScene.ENDING_AFTERSCHOOL
