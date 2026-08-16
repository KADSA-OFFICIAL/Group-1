extends CanvasLayer

## 자막이 다 찍힌 뒤 더 남겨 두는 시간(초). 실제 표시 시간은 타이핑 시간 + 이 값이라,
## 긴 조사 서술도 끝까지 읽을 수 있다(#193).
@export var notice_seconds: float = 3.0

## 인벤토리 슬롯에 조작 키를 덧붙일 아이템(#169).
const USABLE_ITEM_KEYS := {
	"ink_can": "[Q] 던지기",
}

@onready var objective_label: Label = $Root/TopLeft/Margin/TextRows/ObjectiveLabel
@onready var inventory_label: Label = $Root/TopLeft/Margin/TextRows/InventoryLabel
## 하단 알림은 프롤로그·엔딩과 같은 자막 표시를 쓴다(#193).
@onready var subtitle: SubtitleDialogue = $Root/Subtitle
@onready var inventory_panel: PanelContainer = $Root/InventoryPanel
@onready var inventory_title: Label = $Root/InventoryPanel/Margin/Rows/InventoryTitle
@onready var slot_labels: Array[Label] = [
	$Root/InventoryPanel/Margin/Rows/Slots/Slot1/ItemLabel,
	$Root/InventoryPanel/Margin/Rows/Slots/Slot2/ItemLabel,
	$Root/InventoryPanel/Margin/Rows/Slots/Slot3/ItemLabel,
	$Root/InventoryPanel/Margin/Rows/Slots/Slot4/ItemLabel,
	$Root/InventoryPanel/Margin/Rows/Slots/Slot5/ItemLabel,
]

var notice_token: int = 0
var current_items: Array[String] = []
var max_items: int = 5


func _ready() -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")

	if game_state != null:
		if game_state.has_signal("notice_requested"):
			game_state.connect("notice_requested", Callable(self, "show_notice"))
		if game_state.has_signal("speech_requested"):
			game_state.connect("speech_requested", Callable(self, "show_speech"))
		if game_state.has_signal("inventory_changed"):
			game_state.connect("inventory_changed", Callable(self, "set_inventory"))
		var limit = game_state.get("max_items")
		if limit != null:
			max_items = limit

	set_inventory([])
	subtitle.clear()
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

	# 슬롯에 아이템 이름 표시 (아이템 이미지는 추후 교체 예정)
	# 쓸 수 있는 아이템은 조작 키를 같이 적는다 — 획득 시 안내는 3초 뒤 사라지지만
	# 정작 필요한 순간은 한참 뒤라, R로 다시 확인할 수 있어야 한다(#169).
	for i in slot_labels.size():
		if i >= current_items.size():
			slot_labels[i].text = ""
			continue

		var item_id := current_items[i]
		var label := _get_item_display_name(item_id)
		if item_id in USABLE_ITEM_KEYS:
			label += "\n" + USABLE_ITEM_KEYS[item_id]
		slot_labels[i].text = label


## 지문·서술. 화자가 없으므로 프롤로그의 독백 배치로 나온다.
func show_notice(text: String) -> void:
	_show_subtitle("", text, "")


## 화자가 있는 대사(수위 등). 이름 줄이 붙고 본문이 크고 밝게 나온다.
func show_speech(speaker: String, text: String, emotion: String = "") -> void:
	_show_subtitle(speaker, text, emotion)


func _show_subtitle(speaker: String, text: String, emotion: String) -> void:
	notice_token += 1
	var current_token := notice_token

	subtitle.show_line(speaker, text, emotion)

	# 컷신과 달리 본편에는 넘기는 입력이 없다 — 다 찍힐 때까지 기다린 뒤 읽는 시간을 준다.
	await get_tree().create_timer(subtitle.last_typing_seconds + notice_seconds).timeout

	# 기다리는 사이 씬이 바뀌었을 수 있다(체포·탈출).
	if current_token == notice_token and is_instance_valid(subtitle):
		subtitle.clear()


func _get_item_display_name(item_id: String) -> String:
	if item_id.begins_with("stair_key_"):
		return item_id.trim_prefix("stair_key_") + "층 계단 열쇠"

	match item_id:
		"korean_book":
			return "국어책"
		"front_gate_key":
			return "현관 열쇠"
		"ink_can":
			return "잉크통"
		_:
			return item_id
