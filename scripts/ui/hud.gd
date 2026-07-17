extends CanvasLayer

@export var notice_seconds: float = 3.0

@onready var objective_label: Label = $Root/TopLeft/Margin/TextRows/ObjectiveLabel
@onready var inventory_label: Label = $Root/TopLeft/Margin/TextRows/InventoryLabel
@onready var notice_label: Label = $Root/NoticePanel/Margin/NoticeLabel
@onready var inventory_panel: PanelContainer = $Root/InventoryPanel
@onready var inventory_title: Label = $Root/InventoryPanel/Margin/Rows/InventoryTitle
@onready var inventory_list: Label = $Root/InventoryPanel/Margin/Rows/InventoryList

var notice_token: int = 0
var current_items: Array[String] = []
var max_items: int = 5


func _ready() -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")

	if game_state != null:
		if game_state.has_signal("notice_requested"):
			game_state.connect("notice_requested", Callable(self, "show_notice"))
		if game_state.has_signal("inventory_changed"):
			game_state.connect("inventory_changed", Callable(self, "set_inventory"))
		var limit = game_state.get("max_items")
		if limit != null:
			max_items = limit

	set_inventory([])
	notice_label.text = ""
	$Root/NoticePanel.visible = false
	inventory_panel.visible = false


func _unhandled_input(event: InputEvent) -> void:
	if not event.is_action_pressed("inventory"):
		return

	inventory_panel.visible = not inventory_panel.visible
	get_viewport().set_input_as_handled()


func set_objective(text: String) -> void:
	objective_label.text = text


func set_inventory(items: Array[String]) -> void:
	current_items = items.duplicate()
	_refresh_inventory_panel()

	if items.is_empty():
		inventory_label.text = "소지품: 없음"
		return

	var display_names := PackedStringArray()
	for item_id in items:
		display_names.append(_get_item_display_name(item_id))

	inventory_label.text = "소지품: " + ", ".join(display_names)


func _refresh_inventory_panel() -> void:
	inventory_title.text = "소지품 (%d/%d)" % [current_items.size(), max_items]

	if current_items.is_empty():
		inventory_list.text = "비어 있음"
		return

	var lines := PackedStringArray()
	for item_id in current_items:
		lines.append("- " + _get_item_display_name(item_id))

	inventory_list.text = "\n".join(lines)


func show_notice(text: String) -> void:
	notice_token += 1
	var current_token := notice_token

	notice_label.text = text
	$Root/NoticePanel.visible = true

	await get_tree().create_timer(notice_seconds).timeout

	if current_token == notice_token:
		$Root/NoticePanel.visible = false


func _get_item_display_name(item_id: String) -> String:
	match item_id:
		"korean_book":
			return "국어책"
		"front_gate_key":
			return "현관 열쇠"
		"art_room_key":
			return "미술실 열쇠"
		_:
			return item_id
