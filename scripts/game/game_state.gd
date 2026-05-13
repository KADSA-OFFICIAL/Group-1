extends Node

signal inventory_changed(items: Array[String])
signal notice_requested(message: String)

@export var starting_items: Array[String] = []

var items: Array[String] = []


func _enter_tree() -> void:
	add_to_group("game_state")


func _ready() -> void:
	items = starting_items.duplicate()
	inventory_changed.emit(items)


func has_item(item_id: String) -> bool:
	return item_id.is_empty() or item_id in items


func add_item(item_id: String) -> void:
	if item_id.is_empty() or item_id in items:
		return

	items.append(item_id)
	inventory_changed.emit(items)


func request_notice(message: String) -> void:
	if message.is_empty():
		return

	notice_requested.emit(message)
