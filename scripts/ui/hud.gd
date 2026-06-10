extends CanvasLayer

@export var notice_seconds: float = 3.0

@onready var objective_label: Label = $Root/TopLeft/Margin/TextRows/ObjectiveLabel
@onready var inventory_label: Label = $Root/TopLeft/Margin/TextRows/InventoryLabel
@onready var notice_label: Label = $Root/NoticePanel/Margin/NoticeLabel

var notice_token: int = 0


func _ready() -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")

	if game_state != null:
		if game_state.has_signal("notice_requested"):
			game_state.connect("notice_requested", Callable(self, "show_notice"))
		if game_state.has_signal("inventory_changed"):
			game_state.connect("inventory_changed", Callable(self, "set_inventory"))

	set_inventory([])
	notice_label.text = ""
	$Root/NoticePanel.visible = false


func set_objective(text: String) -> void:
	objective_label.text = text


func set_inventory(items: Array[String]) -> void:
	if items.is_empty():
		inventory_label.text = "소지품: 없음"
		return

	var display_names := PackedStringArray()
	for item_id in items:
		display_names.append(_get_item_display_name(item_id))

	inventory_label.text = "소지품: " + ", ".join(display_names)


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
		_:
			return item_id
