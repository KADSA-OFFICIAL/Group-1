extends Node

signal inventory_changed(items: Array[String])
signal notice_requested(message: String)
## 화자가 있는 대사(#193). 지문인 notice_requested와 나뉘어 있어야 HUD가
## 프롤로그와 같은 두 가지 자막 배치 중 하나를 고를 수 있다.
signal speech_requested(speaker: String, message: String, emotion: String)
signal game_over(reason: String)

@export var starting_items: Array[String] = []
## 시작 시 미리 세워 둘 플래그. 뒤쪽 층을 바로 확인할 때(예: stairs_f4_unlocked) 에디터에서 채워 쓴다.
@export var starting_flags: Array[String] = []
@export var max_items: int = 5

var items: Array[String] = []
# 세션 내 진행 상태(문 개방, 아이템 획득 등)를 문자열 플래그로 기록
var flags: Array[String] = []

# 런이 끝났는지(붙잡힘 등). 끝난 뒤 들어오는 중복 신호를 여기서 흡수한다.
var _is_finished: bool = false


func _enter_tree() -> void:
	add_to_group("game_state")


func _ready() -> void:
	items = starting_items.duplicate()
	flags = starting_flags.duplicate()
	inventory_changed.emit(items)


func has_item(item_id: String) -> bool:
	return item_id.is_empty() or item_id in items


func add_item(item_id: String) -> bool:
	if item_id.is_empty() or item_id in items:
		return true

	if items.size() >= max_items:
		return false

	items.append(item_id)
	inventory_changed.emit(items)
	return true


func remove_item(item_id: String) -> void:
	if item_id in items:
		items.erase(item_id)
		inventory_changed.emit(items)


func set_flag(flag: String) -> void:
	if not flag.is_empty() and flag not in flags:
		flags.append(flag)


func has_flag(flag: String) -> bool:
	return flag in flags


func request_notice(message: String) -> void:
	if message.is_empty():
		return

	notice_requested.emit(message)


## 화자 이름이 붙는 대사를 띄운다. emotion은 subtitle_dialogue.gd의 EMOTIONS 키.
func request_speech(speaker: String, message: String, emotion: String = "") -> void:
	if message.is_empty():
		return

	speech_requested.emit(speaker, message, emotion)


## 런이 실패로 끝났음을 알린다(붙잡힘 등). 접촉 판정은 매 프레임 들어오므로
## _is_finished로 첫 호출만 통과시킨다 — 호출자가 따로 가드할 필요가 없다.
func trigger_game_over(reason: String = "") -> void:
	if _is_finished:
		return

	_is_finished = true
	game_over.emit(reason)


func is_finished() -> bool:
	return _is_finished
