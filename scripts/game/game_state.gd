extends Node

signal inventory_changed(items: Array[String])
signal notice_requested(message: String)
signal name_tags_changed(name_tags: Array[String])
signal floor_changed(floor: int)
signal clock_changed(hour: int, minute: int)
signal game_over(reason: String)
signal game_cleared(ending_type: String)

@export var starting_items: Array[String] = []
@export var starting_floor: int = 4
@export var total_name_tags: int = 5

# 연출용 게임 내 시계. 밤 11시에서 시작하고, 실제 1초가 게임 내 1분으로 흐른다.
@export var start_hour: int = 23
@export var minutes_per_real_second: float = 1.0

var items: Array[String] = []
var name_tags: Array[String] = []
var current_floor: int = 0

var _is_finished: bool = false
var _clock_minutes: float = 0.0
var _last_emitted_minute: int = -1


func _enter_tree() -> void:
	add_to_group("game_state")


func _ready() -> void:
	items = starting_items.duplicate()
	current_floor = starting_floor
	_clock_minutes = float(start_hour) * 60.0
	_last_emitted_minute = int(_clock_minutes)

	inventory_changed.emit(items)
	floor_changed.emit(current_floor)
	clock_changed.emit(get_clock_hour(), get_clock_minute())


func _process(delta: float) -> void:
	if _is_finished:
		return

	_clock_minutes += delta * minutes_per_real_second

	var minute_now := int(_clock_minutes)
	if minute_now != _last_emitted_minute:
		_last_emitted_minute = minute_now
		clock_changed.emit(get_clock_hour(), get_clock_minute())


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


func has_name_tag(tag_id: String) -> bool:
	return tag_id in name_tags


func add_name_tag(tag_id: String) -> void:
	if tag_id.is_empty() or tag_id in name_tags:
		return

	name_tags.append(tag_id)
	name_tags_changed.emit(name_tags)


func name_tag_count() -> int:
	return name_tags.size()


func has_all_name_tags() -> bool:
	return name_tags.size() >= total_name_tags


func set_floor(new_floor: int) -> void:
	if new_floor == current_floor:
		return

	current_floor = new_floor
	floor_changed.emit(current_floor)


func get_clock_hour() -> int:
	return int(_clock_minutes / 60.0) % 24


func get_clock_minute() -> int:
	return int(_clock_minutes) % 60


func trigger_game_over(reason: String = "") -> void:
	if _is_finished:
		return

	_is_finished = true
	game_over.emit(reason)


func trigger_clear(ending_type: String = "normal") -> void:
	if _is_finished:
		return

	_is_finished = true
	game_cleared.emit(ending_type)


func is_finished() -> bool:
	return _is_finished
