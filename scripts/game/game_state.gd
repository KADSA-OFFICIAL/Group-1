extends Node

signal inventory_changed(items: Array[String])
signal notice_requested(message: String)

@export var starting_items: Array[String] = []
@export var max_items: int = 5

var items: Array[String] = []
# 세션 내 진행 상태(문 개방, 아이템 획득 등)를 문자열 플래그로 기록
var flags: Array[String] = []


func _enter_tree() -> void:
	add_to_group("game_state")


func _ready() -> void:
	items = starting_items.duplicate()
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
